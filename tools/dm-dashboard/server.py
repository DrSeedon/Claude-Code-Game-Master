import importlib
import json
import sys
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import renderer

PORT = 8766
ROOT = Path(__file__).parent.parent.parent
PACKAGE_DIR = Path(__file__).parent


def _json_response(handler, data: dict) -> None:
    body = json.dumps(data, ensure_ascii=False).encode("utf-8")
    handler.send_response(200)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
    handler.end_headers()
    handler.wfile.write(body)


class DashboardServer(HTTPServer):
    allow_reuse_address = True


class DashboardHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = self.path.split("?")[0]
        if path in ("/", "/index.html"):
            try:
                css = (PACKAGE_DIR / "style.css").read_text(encoding="utf-8")
                html = (PACKAGE_DIR / "shell.html").read_text(encoding="utf-8")
                html = html.replace("{{CSS_PLACEHOLDER}}", css)
                body = html.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            except Exception as e:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(f"Internal error: {e}".encode())
        elif path == "/data":
            try:
                importlib.reload(renderer)
                inner_html = renderer.render_inner_html()
                ts = datetime.now().strftime("%H:%M:%S")
                _json_response(self, {"html": inner_html, "ts": ts})
            except Exception as e:
                _json_response(self, {"html": f'<div class="no-campaign">Error: {e}</div>', "ts": ""})
        elif path == "/wiki":
            try:
                importlib.reload(renderer)
                wiki_html = renderer.render_wiki_html()
                _json_response(self, {"html": wiki_html})
            except Exception as e:
                _json_response(self, {"html": f'<div class="empty-state">Error: {e}</div>'})
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass


def main():
    server = DashboardServer(("localhost", PORT), DashboardHandler)
    print(f"Dashboard running at http://localhost:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.server_close()
        sys.exit(0)
