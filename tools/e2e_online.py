#!/usr/bin/env python3
"""Smoke test of a public online table: gate, page, state, live stream and (optionally) one real action.

    DM_E2E_PASSWORD=... uv run python tools/e2e_online.py --url https://table.example.org
    DM_E2E_PASSWORD=... uv run python tools/e2e_online.py --url ... --action "I look around" --who Aria --expect-act-change

Standard library only. The password comes from the environment (never printed). A summary goes to stdout as one JSON
object; the exit code is 1 when any check failed, 2 when the run could not start. With --action the table's master
plays a turn, which costs real model time and possibly credits: use it on purpose. --local is for a screen server
without nginx in front of it (no sign-in redirect to check).
"""

import argparse
import http.cookiejar
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

TOKEN = re.compile(r'data-token="([^"]+)"')


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


class Client:
    def __init__(self, base, timeout=20):
        self.base, self.timeout = base.rstrip("/"), timeout
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(NoRedirect, urllib.request.HTTPCookieProcessor(self.jar))

    def request(self, method, path, data=None, headers=None, timeout=None):
        """(status, headers, body bytes); a redirect or an error status is an answer here, not an exception."""
        request = urllib.request.Request(self.base + path, data=data, method=method, headers=headers or {})
        try:
            with self.opener.open(request, timeout=timeout or self.timeout) as response:
                return response.status, response.headers, response.read()
        except urllib.error.HTTPError as err:
            return err.code, err.headers, err.read()

    def cookie_names(self):
        return {c.name for c in self.jar}


class Report:
    def __init__(self):
        self.checks, self.extra = [], {}

    def check(self, name, ok, detail=""):
        self.checks.append({"name": name, "ok": bool(ok), "detail": str(detail)[:300]})
        return bool(ok)

    @property
    def ok(self):
        return all(c["ok"] for c in self.checks)

    def finish(self):
        print(json.dumps({"ok": self.ok, "checks": self.checks, **self.extra}, ensure_ascii=False))
        return 0 if self.ok else 1


def json_body(body):
    """A JSON object, or {} for anything else (a proxy's HTML error page must not end the run with a traceback)."""
    try:
        data = json.loads(body)
    except (ValueError, UnicodeDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def read_state(client, token):
    status, _, body = client.request("GET", "/api/state", headers={"X-Screen-Token": token})
    return status, (json_body(body) if status == 200 else {})


def first_state_event(client, token, seconds):
    """True when the live stream sends an 'event: state' within `seconds`."""
    deadline = time.monotonic() + seconds
    request = urllib.request.Request(client.base + "/api/events?token=" + urllib.parse.quote(token), headers={"Accept": "text/event-stream"})
    try:
        with client.opener.open(request, timeout=seconds) as stream:
            while time.monotonic() < deadline:
                line = stream.readline()
                if not line:
                    return False
                if line.startswith(b"event: state"):
                    return True
    except (OSError, urllib.error.URLError):
        return False
    return False


def wait_for_answer(client, token, action_id, timeout):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        status, state = read_state(client, token)
        if status == 200 and (state.get("turn") or {}).get("answered", 0) >= action_id:
            return state
        time.sleep(2)
    return None


def run(args, password):
    report = Report()
    client = Client(args.url)
    if not args.local:
        status, headers, _ = client.request("GET", "/")
        report.check("signed out: redirect to /login", status in (301, 302, 303, 307) and "/login" in (headers.get("Location") or ""), f"status {status}")
    form = {"Content-Type": "application/x-www-form-urlencoded"}
    # one wrong try and one right one: nginx rate-limits /login, so never loop here
    status, _, _ = client.request("POST", "/login", urllib.parse.urlencode({"password": "wrong-" + str(int(time.time()))}).encode(), form)
    report.check("wrong password: 401", status == 401, f"status {status}")
    status, headers, _ = client.request("POST", "/login", urllib.parse.urlencode({"password": password}).encode(), form)
    cookie = "screen_login=" in (headers.get("Set-Cookie") or "")
    if not report.check("right password: 303 and cookie", status == 303 and cookie, f"status {status}, cookie {cookie}"):
        return report
    status, _, body = client.request("GET", "/")
    found = TOKEN.search(body.decode("utf-8", "replace"))
    if not report.check("page has data-token", status == 200 and found, f"status {status}"):
        return report
    token = found.group(1)
    status, state = read_state(client, token)
    report.check("/api/state has act and turn", status == 200 and bool(state.get("act")) and bool(state.get("turn")), f"status {status}")
    report.check("/api/events delivers 'event: state'", first_state_event(client, token, 20))
    if not args.action:
        return report

    before = (state.get("act") or {}).get("id")
    body = json.dumps({"who": args.who, "source": "text", "text": args.action}).encode()
    status, _, answer = client.request("POST", "/api/action", body, {"X-Screen-Token": token, "Content-Type": "application/json"})
    action_id = json_body(answer).get("id") if status == 200 else None
    if not report.check("action accepted", action_id, f"status {status}"):
        return report
    started = time.monotonic()
    final = wait_for_answer(client, token, action_id, args.timeout)
    if not report.check("master answered", final is not None, f"within {args.timeout} s"):
        return report
    turn, act = final["turn"], final.get("act") or {}
    report.extra["answer"] = {"action_id": action_id, "turn_id": turn.get("id"), "seconds": round(time.monotonic() - started, 1),
                              "question": turn.get("question"), "options": len(turn.get("options") or []), "act_title": act.get("title"),
                              "music": bool(((turn.get("audio") or {}).get("music")))}
    if args.expect_act_change:
        report.check("act changed", act.get("id") != before, f"act id {before} -> {act.get('id')}")
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description="Smoke test of a public online table (password in DM_E2E_PASSWORD).")
    parser.add_argument("--url", required=True, help="the table's address, https://...")
    parser.add_argument("--action", help="post this player action (source text) and wait for the master's turn")
    parser.add_argument("--who", default="Everyone", help="who acts (default Everyone)")
    parser.add_argument("--timeout", type=float, default=240, help="seconds to wait for the master's answer (default 240)")
    parser.add_argument("--expect-act-change", action="store_true", help="with --action: the act must be a new one afterwards")
    parser.add_argument("--local", action="store_true", help="a screen server without nginx: skip the sign-in redirect check")
    args = parser.parse_args(argv)
    password = os.environ.get("DM_E2E_PASSWORD", "")
    if not password:
        print(json.dumps({"ok": False, "error": "set DM_E2E_PASSWORD"}))
        return 2
    if args.expect_act_change and not args.action:
        parser.error("--expect-act-change needs --action")
    return run(args, password).finish()


if __name__ == "__main__":
    sys.exit(main())
