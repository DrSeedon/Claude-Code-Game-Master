import http.client
import io
import json
from urllib.parse import urlencode

import pytest
from PIL import Image

from lib.screen import gate, server

KEY = "ab" * 32


def call(port, method, path, body=None, headers=None, host=None):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    conn.request(method, path, body=body, headers={**(headers or {}), **({"Host": host} if host else {})})
    response = conn.getresponse()
    data = response.read()
    conn.close()
    return response.status, data


def test_password_hash_round_trip_and_refusals():
    encoded = gate.hash_password("стол-42")

    assert encoded.startswith("scrypt$16384$8$1$") and "стол-42" not in encoded
    assert gate.verify_password("стол-42", encoded)
    assert not gate.verify_password("стол-43", encoded)
    assert not gate.verify_password("стол-42", encoded.replace("$16384$", "$1048576$"))   # the file cannot raise the cost
    for broken in ("", "plain", "scrypt$x$8$1$aa$bb", "bcrypt$16384$8$1$aa$bb", None):
        assert not gate.verify_password("стол-42", broken)


def test_cookie_signature_and_expiry():
    value = gate.make_cookie(KEY, now=1000, ttl=60)

    assert gate.cookie_ok(KEY, value, now=1059)
    assert not gate.cookie_ok(KEY, value, now=1060)                       # expired
    assert not gate.cookie_ok("cd" * 32, value, now=1000)                 # another key (rotated)
    expires, sig = value.split(".")
    assert not gate.cookie_ok(KEY, f"{int(expires) + 999}.{sig}", now=1000)   # a longer life is not signed
    for junk in ("", ".", "²³.x", f"{expires}.", "1e9." + sig, None):
        assert not gate.cookie_ok(KEY, junk, now=1000)


def test_read_cookie_picks_the_gate_cookie():
    assert gate.read_cookie("a=1; screen_login=v.s; b=2") == "v.s"
    assert gate.read_cookie("screen_loginx=1; a=2") == ""
    assert gate.read_cookie(None) == ""


def test_load_refuses_broken_files(tmp_path):
    good = tmp_path / "good.json"
    good.write_text(json.dumps({"password": gate.hash_password("x"), "key": KEY}))
    assert gate.load(good)["key"] == KEY
    for name, content in (("short", {"password": "scrypt$1", "key": "ab"}), ("plain", {"password": "x", "key": KEY}),
                          ("list", [1]), ("text", "not json")):
        path = tmp_path / f"{name}.json"
        path.write_text(content if isinstance(content, str) else json.dumps(content))
        assert gate.load(path) is None
    assert gate.load(tmp_path / "missing.json") is None


def test_config_command_writes_a_working_file(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO("секрет\n"))

    assert gate.main(["config"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert gate.verify_password("секрет", data["password"]) and len(data["key"]) == 64
    monkeypatch.setattr("sys.stdin", io.StringIO("\n"))
    assert gate.main(["config"]) == 1


def test_login_page_wears_the_act_theme(tmp_path):
    Image.new("RGB", (160, 90), (200, 40, 40)).save(tmp_path / "art.png")
    (tmp_path / "act.json").write_text(json.dumps({"title": "Хроники <b>", "lang": "ru",
                                                   "theme_css": ":root{--accent:#123456}</style><script>x()</script>"}))

    page = gate.login_page(tmp_path, "wrong").decode()

    assert "--accent:#123456" in page and "</style><script>" not in page
    assert "Хроники &lt;b&gt;" in page and "Пароль не подошёл" in page and "card shake" in page
    assert "background-image:url(data:image/jpeg;base64," in page
    assert "{{" not in page


def test_login_page_without_an_act(tmp_path):
    page = gate.login_page(tmp_path).decode()

    assert "Сесть за стол" in page and "{{" not in page and 'style=""' in page


@pytest.fixture
def gated(tmp_path, monkeypatch):
    login = tmp_path / "login.json"
    login.write_text(json.dumps({"password": gate.hash_password("пароль"), "key": KEY}))
    monkeypatch.setenv("DM_SCREEN_LOGIN_FILE", str(login))
    (tmp_path / "act.json").write_text(json.dumps({"title": "Стол", "lang": "ru"}))
    httpd, _ = server.make_server(tmp_path, port=0, token="T", views_provider=dict)
    server.serve_in_thread(httpd)
    yield httpd.server_port, login
    httpd.shutdown()
    httpd.server_close()


def login(port, password):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    conn.request("POST", "/login", body=urlencode({"username": "guest", "password": password}),
                 headers={"Content-Type": "application/x-www-form-urlencoded"})
    response = conn.getresponse()
    body = response.read()
    conn.close()
    return response.status, response.getheader("Set-Cookie"), response.getheader("Location"), body


def test_auth_answers_401_without_a_cookie_and_204_after_login(gated):
    port, _ = gated

    assert call(port, "GET", "/_auth")[0] == 401
    status, cookie, location, _ = login(port, "пароль")
    assert status == 303 and location == "/"
    assert "HttpOnly" in cookie and "Secure" in cookie and "SameSite=Lax" in cookie
    pair = cookie.split(";")[0]
    assert call(port, "GET", "/_auth", headers={"Cookie": pair})[0] == 204
    assert call(port, "GET", "/_auth", headers={"Cookie": pair + "0"})[0] == 401
    status, _ = call(port, "GET", "/login", headers={"Cookie": pair})
    assert status == 303                                                    # signed in: straight to the table


def test_wrong_password_gets_the_form_again_without_a_cookie(gated):
    port, _ = gated

    status, cookie, _, body = login(port, "не тот")

    assert status == 401 and cookie is None and "Пароль не подошёл" in body.decode()
    assert login(port, "")[0] == 401


def test_broken_gate_file_lets_nobody_in(gated):
    port, login_file = gated
    login_file.write_text("{}")

    assert call(port, "GET", "/_auth")[0] == 500                          # nginx turns any non-2xx/401/403 into 500
    status, cookie, _, body = login(port, "пароль")
    assert status == 500 and cookie is None and "не работает" in body.decode()
    status, body = call(port, "GET", "/login")
    assert status == 500 and "не работает" in body.decode()


def test_gate_keeps_the_host_check(gated):
    port, _ = gated

    assert call(port, "GET", "/_auth", host="evil.example")[0] == 403
    assert call(port, "GET", "/login", host="evil.example")[0] == 403
    assert call(port, "POST", "/login", body="password=x", host="evil.example",
                headers={"Content-Length": "10"})[0] == 403


def test_login_body_size_is_capped(gated):
    port, _ = gated

    assert call(port, "POST", "/login", body="password=" + "x" * 5000)[0] == 413


def test_no_gate_without_the_login_file(tmp_path, monkeypatch):
    monkeypatch.delenv("DM_SCREEN_LOGIN_FILE", raising=False)
    httpd, _ = server.make_server(tmp_path, port=0, token="T", views_provider=dict)
    server.serve_in_thread(httpd)
    try:
        assert call(httpd.server_port, "GET", "/_auth")[0] == 403           # never 204: nginx stays closed
        assert call(httpd.server_port, "POST", "/login", body="password=x")[0] == 403
    finally:
        httpd.shutdown()
        httpd.server_close()
