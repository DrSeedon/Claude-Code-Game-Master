#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"
export PATH="$HOME/.local/bin:$HOME/.npm-global/bin:$PATH"

# Claude SDK traffic must use the shared Orchestra proxy registry. Import only
# the proxy variables so unrelated credentials from that file never enter the
# web server environment.
proxy_registry="/mnt/data/Projects/Python/orchestra/.env"
if [[ -r "$proxy_registry" ]]; then
    while IFS= read -r -d '' assignment; do
        export "$assignment"
    done < <(
        uv run python - "$proxy_registry" <<'PY'
import os
import sys

from dotenv import dotenv_values

values = dotenv_values(sys.argv[1])
for name in ("HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY"):
    value = values.get(name) or os.environ.get(name)
    if value:
        sys.stdout.buffer.write(f"{name}={value}\0".encode())
PY
    )
fi

exec "$PWD/.venv/bin/uvicorn" backend.server:app --host 127.0.0.1 --port 18083
