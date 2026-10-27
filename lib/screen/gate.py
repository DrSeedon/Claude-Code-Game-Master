"""Password gate of the online screen: a login page in the act's design instead of the browser's basic-auth box.

On only when DM_SCREEN_LOGIN_FILE names a JSON file {"password": "scrypt$...", "key": "<hex>"} (the online table;
the laptop screen has no gate). nginx asks GET /_auth before every request (auth_request) and passes it on 204; the
login page POSTs the password to /login and gets a signed cookie for 30 days. The file holds only the password's
scrypt hash and the cookie key; a new key signs everyone out.

    python -m lib.screen.gate config < password-file   # prints a new gate file for that password (and a new key)
"""

import base64
import hashlib
import hmac
import html
import io
import json
import re
import secrets
import sys
import time
from functools import lru_cache
from pathlib import Path

COOKIE = "screen_login"
TTL = 30 * 24 * 3600
LOGIN_PAGE = Path(__file__).with_name("login.html")
_SCRYPT = (2 ** 14, 8, 1)              # n, r, p: 16 MiB and about 50 ms a try
_EXPIRES = re.compile(r"[0-9]{1,12}")
_KEY = re.compile(r"[0-9a-f]{64,}")

TEXTS = {
    "ru": {"kicker": "ОНЛАЙН-СТОЛ", "lead": "Стол накрыт, мастер на месте. Назовите пароль, чтобы сесть.",
           "label": "Пароль стола", "button": "Сесть за стол", "note": "Это устройство мы запомним на 30 дней.",
           "wrong": "Пароль не подошёл. Попробуйте ещё раз.",
           "broken": "Вход сейчас не работает. Напишите хозяину стола."},
    "en": {"kicker": "ONLINE TABLE", "lead": "The table is set and the Master is in. Say the password to take a seat.",
           "label": "Table password", "button": "Take a seat", "note": "This device stays signed in for 30 days.",
           "wrong": "Wrong password. Try again.",
           "broken": "Signing in does not work right now. Tell the table's host."},
}


def _b64(raw):
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _unb64(text):
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def hash_password(password, salt=None):
    n, r, p = _SCRYPT
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=n, r=r, p=p, dklen=32)
    return f"scrypt${n}${r}${p}${_b64(salt)}${_b64(digest)}"


def verify_password(password, encoded):
    try:
        kind, n, r, p, salt, digest = str(encoded).split("$")
        if kind != "scrypt" or (int(n), int(r), int(p)) != _SCRYPT:   # never let the file pick the memory cost
            return False
        expected = _unb64(digest)
        got = hashlib.scrypt(password.encode(), salt=_unb64(salt), n=int(n), r=int(r), p=int(p), dklen=len(expected))
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(got, expected)


def load(path):
    """The gate file, or None when it is missing or broken: the gate then lets nobody in."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if _KEY.fullmatch(data["key"]) and str(data["password"]).startswith("scrypt$"):
            return data
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return None


def _sign(key, expires):
    return hmac.new(bytes.fromhex(key), f"screen-login:{expires}".encode(), hashlib.sha256).hexdigest()


def make_cookie(key, now=None, ttl=TTL):
    expires = int((time.time() if now is None else now) + ttl)
    return f"{expires}.{_sign(key, expires)}"


def cookie_ok(key, value, now=None):
    expires, _, signature = (value or "").partition(".")
    if not _EXPIRES.fullmatch(expires) or int(expires) <= (time.time() if now is None else now):
        return False
    return hmac.compare_digest(signature, _sign(key, int(expires)))


def read_cookie(header):
    """The gate cookie's value from a Cookie header, or ''."""
    for part in (header or "").split(";"):
        name, _, value = part.strip().partition("=")
        if name == COOKIE:
            return value
    return ""


def set_cookie(key):
    return f"{COOKIE}={make_cookie(key)}; Path=/; Max-Age={TTL}; HttpOnly; Secure; SameSite=Lax"


@lru_cache(maxsize=4)
def _backdrop(path, _mtime_ns, _size):
    """A tiny copy of the act's art, blurred by the page: the scene's colors without its details."""
    try:
        from PIL import Image
        with Image.open(path) as image:
            image = image.convert("RGB")
            image.thumbnail((64, 36))
            buffer = io.BytesIO()
            image.save(buffer, "JPEG", quality=70)
    except Exception:
        return ""
    return "data:image/jpeg;base64," + base64.b64encode(buffer.getvalue()).decode()


def login_page(screen_dir, error=None):
    """The login form in the current act's theme (colors, font, title) over its blurred art."""
    screen_dir = Path(screen_dir)
    try:
        act = json.loads((screen_dir / "act.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        act = {}
    act = act if isinstance(act, dict) else {}
    texts = TEXTS.get(act.get("lang"), TEXTS["ru"])
    art = screen_dir / "art.png"
    try:
        st = art.stat()
        backdrop = _backdrop(str(art), st.st_mtime_ns, st.st_size)
    except OSError:
        backdrop = ""
    values = {
        "LANG": act.get("lang") if act.get("lang") in TEXTS else "ru",
        "THEME_CSS": str(act.get("theme_css", "")).replace("<", ""),   # public page: the theme cannot close <style>
        "TITLE": html.escape(str(act.get("title") or texts["kicker"].capitalize())),
        "BG_STYLE": f"background-image:url({backdrop})" if backdrop else "",
        "CARD_CLASS": " shake" if error == "wrong" else "",
        "ERROR": html.escape(texts[error]) if error else "",
        **{name.upper(): html.escape(texts[name]) for name in ("kicker", "lead", "label", "button", "note")},
    }
    page = LOGIN_PAGE.read_text(encoding="utf-8")
    for name, value in values.items():
        page = page.replace("{{" + name + "}}", value)
    return page.encode()


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv != ["config"]:
        print(__doc__.strip().splitlines()[-1].strip(), file=sys.stderr)
        return 2
    password = sys.stdin.read().rstrip("\r\n")
    if not password:
        print("no password on stdin", file=sys.stderr)
        return 1
    print(json.dumps({"password": hash_password(password), "key": secrets.token_hex(32)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
