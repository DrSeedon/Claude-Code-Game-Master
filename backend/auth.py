"""Simple cookie-based auth with a login page (not browser modal).

Set DND_AUTH_PASSWORD in env (or .env). If unset, auth is disabled (local dev).
Cookie: dnd_session=<sha256(password+salt)>, httponly, 30 days.
"""

import hashlib
import os
from fastapi import Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse

AUTH_COOKIE = "dnd_session"
AUTH_MAX_AGE = 30 * 86400  # 30 days
_SALT = "dnd-game-master-2026"


def _get_password() -> str | None:
    return os.environ.get("DND_AUTH_PASSWORD")


def _token(password: str) -> str:
    return hashlib.sha256(f"{_SALT}:{password}".encode()).hexdigest()[:32]


def is_authenticated(request: Request) -> bool:
    password = _get_password()
    if not password:
        return True
    cookie = request.cookies.get(AUTH_COOKIE, "")
    return cookie == _token(password)


def login_page(error: str = "") -> HTMLResponse:
    error_html = f'<div class="error">{error}</div>' if error else ""
    return HTMLResponse(f"""<!doctype html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>DM Game Master — Вход</title>
<style>
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ background: #0a0e17; color: #e2e8f0; font-family: 'Inter', system-ui, sans-serif;
  display: flex; align-items: center; justify-content: center; min-height: 100vh; }}
.card {{ background: #0f172a; border: 1px solid #334155; border-radius: 12px;
  padding: 40px; width: 100%; max-width: 380px; text-align: center; }}
.mark {{ font-size: 48px; margin-bottom: 16px; }}
h1 {{ font-size: 22px; font-weight: 700; margin-bottom: 8px; }}
.sub {{ color: #8595ab; font-size: 14px; margin-bottom: 24px; }}
input {{ width: 100%; padding: 12px 14px; background: #1e293b; border: 1px solid #334155;
  border-radius: 8px; color: #e2e8f0; font-size: 14px; outline: none; margin-bottom: 16px; }}
input:focus {{ border-color: #818cf8; }}
button {{ width: 100%; padding: 12px; background: #818cf8; border: none; border-radius: 8px;
  color: #fff; font-size: 14px; font-weight: 600; cursor: pointer; }}
button:hover {{ filter: brightness(1.1); }}
.error {{ background: rgba(239,68,68,0.12); border: 1px solid rgba(239,68,68,0.4);
  color: #fca5a5; padding: 10px; border-radius: 8px; margin-bottom: 16px; font-size: 13px; }}
</style>
</head>
<body>
<div class="card">
  <div class="mark">🎲</div>
  <h1>DM Game Master</h1>
  <p class="sub">Введите пароль для входа</p>
  {error_html}
  <form method="POST" action="/auth/login">
    <input type="password" name="password" placeholder="Пароль" autofocus required>
    <button type="submit">Войти</button>
  </form>
</div>
</body>
</html>""", status_code=401 if error else 200)


def handle_login(password: str) -> Response:
    expected = _get_password()
    if not expected:
        return RedirectResponse("/", status_code=302)
    if password == expected:
        resp = RedirectResponse("/", status_code=302)
        resp.set_cookie(AUTH_COOKIE, _token(password), max_age=AUTH_MAX_AGE, httponly=True, samesite="lax")
        return resp
    return login_page(error="Неверный пароль")
