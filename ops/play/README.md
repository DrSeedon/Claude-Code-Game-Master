# Online tables runbook: dnd-play.seedon.ru and dnd-demo.seedon.ru

The HTML screen online behind a password, played by a Claude Agent SDK master on Sonnet 5.5 (owner decisions 2026-10-26 and 2026-10-27, `.orchestra/kb/rules-deploy-vps.md`). One table per systemd instance:

| Table | Public name | Campaign | Unit | Port |
|---|---|---|---|---|
| `play` | https://dnd-play.seedon.ru | the owner's (`pratchett-dungeon`) | `dnd-play@play` | 18116 |
| `demo` | https://dnd-demo.seedon.ru | a copy for guests (`pratchett-demo`) | `dnd-play@demo` | 18118 |

```
guest -> dnd-<table>.seedon.ru (RU host 89.23.102.244, vhost dnd-play-mirror)
      -> <table>-158-220-127-161.sslip.io (Contabo 158.220.127.161, vhost dnd-play-sslip + snippet dnd-play-table.conf:
         password gate, limits, headers)
      -> 127.0.0.1:<port> (dnd-play@<table>: backend.screen_driver = screen server + master)
master -> bash tools/dm-art.sh -> 127.0.0.1:18117 (dnd-play-art: act art through the MultiCode hub)
```

| File | Installed as |
|---|---|
| `dnd-play@.service` | `/etc/systemd/system/dnd-play@.service` (Contabo) |
| `apparmor-dnd-play-master` | `/etc/apparmor.d/dnd-play-master` (Contabo) |
| `dnd-play.env.example` | `/etc/dnd-play/dnd-play.env`: caps and model of every table (Contabo) |
| `table.env.example` | `/etc/dnd-play/<table>.env`: the table's port and public URL (Contabo) |
| `dnd-play-art.service` | `/etc/systemd/system/dnd-play-art.service`, code copy `/opt/dnd-play-art/screen_art.py` (Contabo) |
| `nginx-dnd-play-sslip` | `/etc/nginx/sites-available/dnd-play-sslip` + link in `sites-enabled` (Contabo) |
| `nginx-dnd-play-table.conf` | `/etc/nginx/snippets/dnd-play-table.conf` (Contabo) |
| `nginx-dnd-play-mirror` | `/etc/nginx/sites-available/dnd-play-mirror` + link in `sites-enabled` (RU host) |
| `.claude/additional/infrastructure/screen-driver-contract.md` | the master's contract prompt (in the repository) |

## Rules for whoever runs this
- The install is owner-approved (2026-10-26, the second table and hub images 2026-10-27); still tell the owner when it starts and when it is done.
- Never restart Orchestra on the VPS. Reload nginx, never restart it.
- On the RU host touch only `dnd-play-mirror` (its file and its link). Never a seedon.ru record at 158.220.127.161, never `dnd.seedon.ru`.
- Git on the VPS only as `kesha`, never root. `sudo` works through a fresh SSH session (`ssh kesha@158.220.127.161 'sudo ...'`; from an Orchestra agent on the VPS use `ssh kesha@localhost`).
- Keys are checked by name only; never print a value. Each table's password lives only in the laptop `.env` (`DND_PLAY_PASSWORD` for `play`, `DND_DEMO_PASSWORD` for `demo`); the servers keep their hashes.
- The password is typed into the screen's own login page (owner 2026-10-27), never a browser basic-auth box: nginx asks the screen `GET /_auth` before every request (`lib/screen/gate.py`) and fails closed.
- Two tables never share a campaign: `dm-play.sh switch` and the driver refuse a campaign another table plays. Give a new table a copy.
- Commands below run from the laptop repository root. `VPS=kesha@158.220.127.161`, `RU=root@89.23.102.244`.

## 1. Code on the VPS
```bash
git push origin main
ssh $VPS 'cd ~/projects/dnd-game-master && find . ! -user kesha -print -quit && git status --porcelain && git pull --ff-only && ~/.local/bin/uv sync --frozen && .venv/bin/python -c "import backend.screen_driver, lib.screen.online" && /usr/bin/claude --version'
```
`find` and `git status` must print nothing.

## 2. Keys (by name only)
```bash
ssh $VPS 'cd ~/projects/dnd-game-master && grep -oE "^[A-Za-z_][A-Za-z0-9_]*=" .env | tr -d = | sort'
```
Needed: `ELEVENLABS_API_KEY`, `DEEPGRAM_API_KEY` (`FREESOUND_API_KEY` is optional and free). Missing ones are copied from the laptop without being shown; the backup name matches the `.env.*.local` ignore rule:
```bash
grep -E '^(ELEVENLABS_API_KEY|DEEPGRAM_API_KEY|FREESOUND_API_KEY)=' .env | ssh $VPS 'cd ~/projects/dnd-game-master && cp -p .env ".env.$(date +%F-%H%M).local" && { grep -vE "^(ELEVENLABS_API_KEY|DEEPGRAM_API_KEY|FREESOUND_API_KEY)=" .env; cat; } > .env.new.local && chmod 600 .env.new.local && mv .env.new.local .env'
```
Run the name check again. If it lists `ANTHROPIC_API_KEY`, stop and ask the owner: the master must think on kesha's subscription, and the CLI bills an API key instead when one reaches its environment.

## 3. Campaigns
The `play` table's campaign was moved from the laptop on 2026-10-26 (a tar copy without the laptop's runtime files: `chrome-profile`, `server.json`, `server.log`, `log/`, `gm-session.json`, `gm-system-prompt.md`, `.runtime-session.json`; the VPS copy is the live one, do not play it on the laptop).

A table for guests plays a copy, made on the VPS. Keep `inbox.jsonl` and `wait-cursor.json`: `turn.json` remembers the last answered action id, and a fresh inbox would number new actions from 1 and count them as answered.
```bash
ssh $VPS 'set -e; cd ~/projects/dnd-game-master/world-state/campaigns; test ! -e pratchett-demo; cp -a pratchett-dungeon pratchett-demo; cd pratchett-demo; rm -rf screen/chrome-profile screen/log screen/art-incoming .runtime-session.json .turn.lock; rm -f screen/server.json screen/server.log screen/gm-session.json screen/gm-system-prompt.md screen/spend.json'
```

## 4. Settings per table
```bash
ssh $VPS 'sudo install -d -m 755 /etc/dnd-play && sudo install -m 644 ~/projects/dnd-game-master/ops/play/dnd-play.env.example /etc/dnd-play/dnd-play.env'
ssh $VPS 'printf "DM_PLAY_PORT=18116\nDM_SCREEN_PUBLIC_URL=https://dnd-play.seedon.ru/\n" | sudo tee /etc/dnd-play/play.env >/dev/null; printf "DM_PLAY_PORT=18118\nDM_SCREEN_PUBLIC_URL=https://dnd-demo.seedon.ru/\n" | sudo tee /etc/dnd-play/demo.env >/dev/null'
# a new table's config with its campaign and port (the play table's exists since 2026-10-26)
ssh $VPS 'cd ~/projects/dnd-game-master && DM_PLAY_PORT=18118 bash tools/dm-play.sh --table demo switch pratchett-demo && bash tools/dm-play.sh tables'
```

## 5. Passwords (hashes only on the server)
One per table: `DND_PLAY_PASSWORD` → `/etc/dnd-play/play-login.json`, `DND_DEMO_PASSWORD` → `/etc/dnd-play/demo-login.json`.
```bash
T=demo; VAR=DND_DEMO_PASSWORD
grep -q "^$VAR=" .env || printf '\n%s=%s\n' "$VAR" "$(openssl rand -base64 48 | tr -dc 'A-Za-z0-9' | head -c 24)" >> .env
uv run python -c "from dotenv import dotenv_values; print(dotenv_values('.env')['$VAR'])" \
| uv run python -m lib.screen.gate config \
| ssh $VPS "sudo sh -c 'umask 027; cat > /etc/dnd-play/$T-login.json.new && chgrp kesha /etc/dnd-play/$T-login.json.new && mv /etc/dnd-play/$T-login.json.new /etc/dnd-play/$T-login.json' && sudo stat -c '%U:%G %a' /etc/dnd-play/$T-login.json"
```
Expected: `root:kesha 640`. The gate file (`DM_SCREEN_LOGIN_FILE` in the unit) holds the password's scrypt hash and the key that signs the 30-day login cookie; the screen server reads it as `kesha`, so the master can read it too (it is already inside). The screen reads it on every request: to rotate, change the password in `.env` and run this step again; the new key signs every device out. Until the file exists the gate answers 500 and nobody gets in.

## 6. Master sandbox: AppArmor profile
```bash
ssh $VPS 'sudo tee /etc/apparmor.d/dnd-play-master >/dev/null && sudo apparmor_parser -r /etc/apparmor.d/dnd-play-master && sudo aa-status | grep dnd-play-master' < ops/play/apparmor-dnd-play-master
```
The unit does not start without it. Why: every other kesha process is visible in `/proc`, and `/proc/<pid>/root` of one outside the unit is the host filesystem; the profile grants ptrace and signals only among the master's own processes.

## 7. Services
```bash
ssh $VPS 'install -d -m 700 ~/.cache/dnd-play-master && sudo install -m 644 ~/projects/dnd-game-master/ops/play/dnd-play@.service /etc/systemd/system/dnd-play@.service; sudo systemd-analyze verify dnd-play@play.service'
# read the output: lines about dnd-play@ must be fixed first, lines about other units do not matter
ssh $VPS 'sudo systemctl daemon-reload && sudo systemctl enable --now dnd-play@demo && sleep 20 && systemctl --no-pager status dnd-play@demo | head -12 && journalctl -u dnd-play@demo -n 40 --no-pager'
ssh $VPS 'cd ~/projects/dnd-game-master && bash tools/dm-play.sh tables && curl -s -o /dev/null -w "%{http_code}\n" -H "Host: 127.0.0.1:18118" http://127.0.0.1:18118/login'
# the sandbox: the home is an allowlist, git reaches GitHub, other processes' /proc/<pid>/root and signals are refused
ssh $VPS 'pid=$(systemctl show -p MainPID --value dnd-play@demo); o=$(systemctl show -p MainPID --value orchestra); sudo nsenter -t $pid -m ls -A /home/kesha /home/kesha/.ssh && sudo nsenter -t $pid -m -S $(id -u) -G $(id -g) env HOME=/home/kesha git -C /home/kesha/projects/dnd-game-master ls-remote --heads origin main && cat /proc/$pid/attr/current'
```
Expected: the unit is active, the table shows its campaign and `idle` (or `thinking` on the opening turn), `/login` answers `200`, the journal's "screen limits" line shows the caps, the home lists `.cache .claude .claude.json .gitconfig .local .ssh projects` (`.cache` holds only `dnd-play-master`), `.ssh` lists `config id_ed25519_github known_hosts`, one `refs/heads/main` line, and the process runs under `dnd-play-master (enforce)`.

Moving the first table from the old `dnd-play.service` (2026-10-27): rename its gate file, then swap the units between two turns.
```bash
ssh $VPS 'sudo mv /etc/dnd-play/login.json /etc/dnd-play/play-login.json; cd ~/projects/dnd-game-master && bash tools/dm-play.sh status | sed -n 2p'   # idle
ssh $VPS 'sudo systemctl disable --now dnd-play && sudo rm /etc/systemd/system/dnd-play.service && sudo systemctl daemon-reload && sudo systemctl enable --now dnd-play@play'
```

## 8. Act art: the hub picture service
The master never holds the hub ssh key or the MultiCode token: `dnd-play-art` holds them and only takes a prompt (`bash tools/dm-art.sh --prompt "..."`). It runs a root-owned copy of its code, so a change the master makes in the repository never runs with the key; reinstall the copy after every change to `backend/screen_art.py`.
```bash
ssh $VPS 'sudo install -D -m 644 -o root -g root ~/projects/dnd-game-master/backend/screen_art.py /opt/dnd-play-art/screen_art.py && sudo install -m 644 ~/projects/dnd-game-master/ops/play/dnd-play-art.service /etc/systemd/system/dnd-play-art.service && sudo systemctl daemon-reload && sudo systemctl enable --now dnd-play-art && sleep 3 && systemctl --no-pager status dnd-play-art | head -8'
```
One real picture proves the route (it uses the hub's Codex subscription, about one to five minutes):
```bash
ssh $VPS 'cd ~/projects/dnd-game-master && DM_ACTIVE_CAMPAIGN=pratchett-demo bash tools/dm-art.sh --prompt "A crooked medieval tavern at dusk, warm lantern light, rain on the street"'
```
It prints a PNG path under `world-state/campaigns/pratchett-demo/screen/art-incoming/`. The daily cap is `DM_ART_DAILY_LIMIT` (the unit), counted in `/var/lib/dnd-play-art/art-spend.json`.

## 9. Contabo vhost: port 80, certificate, then 443
The shared server part is a snippet; each table has its own 443 server and certificate.
```bash
ssh $VPS 'sudo install -m 644 ~/projects/dnd-game-master/ops/play/nginx-dnd-play-table.conf /etc/nginx/snippets/dnd-play-table.conf'
# a new table: first the file without its 443 server (the demo one here)
ssh $VPS "sed '/^# ---- demo 443 BEGIN/,/^# ---- demo 443 END/d' ~/projects/dnd-game-master/ops/play/nginx-dnd-play-sslip | sudo tee /etc/nginx/sites-available/dnd-play-sslip >/dev/null && sudo ln -sfn /etc/nginx/sites-available/dnd-play-sslip /etc/nginx/sites-enabled/dnd-play-sslip && sudo nginx -t && sudo systemctl reload nginx"
# certificate: webroot, like table-158-220-127-161.sslip.io (the existing deploy hook reloads nginx on renewal)
ssh $VPS 'sudo certbot certonly --webroot -w /var/www/html -d demo-158-220-127-161.sslip.io --non-interactive --agree-tos --keep-until-expiring && sudo ls /etc/letsencrypt/live/demo-158-220-127-161.sslip.io/'
# then the whole file
ssh $VPS 'sudo install -m 644 ~/projects/dnd-game-master/ops/play/nginx-dnd-play-sslip /etc/nginx/sites-available/dnd-play-sslip && sudo nginx -t && sudo systemctl reload nginx'
```
If `nginx -t` fails, put the previous file back (or remove the link) before anything else. The map `$dnd_play_port` in the vhost and the port in `/etc/dnd-play/<table>.env` must agree.

## 10. RU mirror
```bash
ssh $RU 'getent hosts dnd-demo.seedon.ru'       # 89.23.102.244 (the company wildcard)
ssh $RU 'cat > /etc/nginx/sites-available/dnd-play-mirror.new' < ops/play/nginx-dnd-play-mirror
ssh $RU 'cd /etc/nginx/sites-available && cp -p dnd-play-mirror dnd-play-mirror.bak && mv dnd-play-mirror.new dnd-play-mirror && ln -sfn /etc/nginx/sites-available/dnd-play-mirror /etc/nginx/sites-enabled/dnd-play-mirror && nginx -t && systemctl reload nginx'
```
If `nginx -t` fails, put `dnd-play-mirror.bak` back at once: every other site on that host shares the reload.

## 11. Checks
Per table, with its password (`DND_PLAY_PASSWORD` or `DND_DEMO_PASSWORD`). The smoke script never prints it; `--action` sends one action and waits for the master's turn (it spends one master turn, so only on a table where that is fine).
```bash
for t in play demo; do
  VAR=$([ $t = play ] && echo DND_PLAY_PASSWORD || echo DND_DEMO_PASSWORD)
  DM_E2E_PASSWORD=$(uv run python -c "from dotenv import dotenv_values; print(dotenv_values('.env')['$VAR'])") \
    uv run python tools/e2e_online.py --url https://dnd-$t.seedon.ru
done
curl -s -o /dev/null -w '%{http_code}\n' http://dnd-demo.seedon.ru/   # 301
curl -s -o /dev/null -w '%{http_code}\n' https://demo-158-220-127-161.sslip.io/login   # 200 (direct name)
```
The summary is one JSON line per table, `"ok": true`. The local browser test of the page itself: `on-remote env DM_SCREEN_E2E=1 uv run --group e2e pytest -q tests/e2e`.

Last, in a browser: open the table, sign in on the login page, press an option. The page shows the Master thinking, a turn arrives, and `bash tools/dm-play.sh --table <t> status` on the VPS counts it.

## Operating
- **Status:** `ssh $VPS 'cd ~/projects/dnd-game-master && bash tools/dm-play.sh tables'`, one table in detail: `bash tools/dm-play.sh --table demo status` (state, campaign, session, turns this hour and today, last error).
- **Kill switch:** `bash tools/dm-play.sh --table <t> pause` stops that master taking actions while its screen stays up; `resume` continues. Hard stop: `sudo systemctl stop dnd-play@<t>` (nginx then answers 502). Off the internet: remove the `dnd-play-sslip` link on Contabo and the `dnd-play-mirror` link on the RU host, `nginx -t`, reload.
- **Other campaign:** `bash tools/dm-play.sh --table <t> switch <name>` (the master does it when the players ask; a campaign another table plays is refused); `restart-screen` restarts only the screen server.
- **Fresh master session:** `bash tools/dm-play.sh --table <t> new-session` when the stored session keeps failing (the journal shows the same API error on every turn); after the current turn the master starts over with the opening notice.
- **Never `dm-screen.sh listen` or `wait` on an online screen:** they move the driver's delivery cursor and take actions away from it; both refuse while a driver runs. The web game master also refuses every campaign a driver plays.
- **Logs:** `journalctl -u dnd-play@<t> -f` (driver and master), `journalctl -u dnd-play-art` (pictures), `bash tools/dm-screen.sh log --errors --since 1h` (screen, in the repository on the VPS, `DM_ACTIVE_CAMPAIGN=<campaign>`), nginx `/var/log/nginx/dnd-<t>-access.log` and `dnd-<t>-error.log` (Contabo), `/var/log/nginx/dnd-play-mirror-access.log` (RU host, both names). Access logs carry no query string, so no screen token.
- **Caps:** edit `/etc/dnd-play/dnd-play.env` (every table; the daily speech ledger is shared), then `sudo systemctl restart 'dnd-play@*'`.
- **Updates:** push, then on the VPS `git pull --ff-only` (`~/.local/bin/uv sync --frozen` when `uv.lock` changed). Driver changes need `sudo systemctl restart 'dnd-play@*'`; screen code only `bash tools/dm-play.sh --table <t> restart-screen` per table; `backend/screen_art.py` needs step 8's install and `sudo systemctl restart dnd-play-art`; engine tools nothing.
- **The masters' own fixes** land on `main` with an "(online table)" suffix: pull before working on the laptop, undo one with `git revert <sha>`.
- **Crash loop:** a unit gives up after 5 failures in 10 minutes; read the journal, fix, `sudo systemctl reset-failed dnd-play@<t> && sudo systemctl start dnd-play@<t>`.
