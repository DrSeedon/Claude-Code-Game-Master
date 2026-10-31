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
| `table.env.example` | `/etc/dnd-play/<table>.env`: the table's port and public URL, the play table's hub master settings (Contabo) |
| `hub-gate.py` | `/usr/local/lib/dnd-play/hub-gate`, root-owned: the forced command of the hub master's ssh key (Contabo) |
| `hub-vps.sh` | used on the hub by the hub master's T3 thread (its standing instructions: `hub-master.md`) |
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
The unit does not start without it. Why: every other kesha process is visible in `/proc`, and `/proc/<pid>/root` of one outside the unit is the host filesystem; the profile grants ptrace and signals only among the master's own processes. The file holds one profile per table (`dnd-play-master-play`, `dnd-play-master-demo`; the unit uses `dnd-play-master-%i`), so the guests' demo master cannot read the play driver's `/proc` entries either. A new table needs its own block in the file first. Load this file before installing a unit that names the per-table profiles (2026-10-28), or the restarted tables do not start.

## 7. Services
```bash
ssh $VPS 'install -d -m 700 ~/.cache/dnd-play-master && sudo install -m 644 ~/projects/dnd-game-master/ops/play/dnd-play@.service /etc/systemd/system/dnd-play@.service; sudo systemd-analyze verify dnd-play@play.service'
# read the output: lines about dnd-play@ must be fixed first, lines about other units do not matter
ssh $VPS 'sudo systemctl daemon-reload && sudo systemctl enable --now dnd-play@demo && sleep 20 && systemctl --no-pager status dnd-play@demo | head -12 && journalctl -u dnd-play@demo -n 40 --no-pager'
ssh $VPS 'cd ~/projects/dnd-game-master && bash tools/dm-play.sh tables && curl -s -o /dev/null -w "%{http_code}\n" -H "Host: 127.0.0.1:18118" http://127.0.0.1:18118/login'
# the sandbox: the home is an allowlist, git reaches GitHub, other processes' /proc/<pid>/root and signals are refused
ssh $VPS 'pid=$(systemctl show -p MainPID --value dnd-play@demo); o=$(systemctl show -p MainPID --value orchestra); sudo nsenter -t $pid -m ls -A /home/kesha /home/kesha/.ssh && sudo nsenter -t $pid -m -S $(id -u) -G $(id -g) env HOME=/home/kesha git -C /home/kesha/projects/dnd-game-master ls-remote --heads origin main && cat /proc/$pid/attr/current'
```
Expected: the unit is active, the table shows its campaign and `idle` (or `thinking` on the opening turn), `/login` answers `200`, the journal's "screen limits" line shows the caps, the home lists `.cache .claude .claude.json .gitconfig .local .ssh projects` (`.cache` holds only `dnd-play-master`), `.ssh` lists `config id_ed25519_github known_hosts`, one `refs/heads/main` line, and the process runs under `dnd-play-master-demo (enforce)`.

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

## 12. Hub master
Owner decision 2026-10-28 (`.orchestra/kb/rules-deploy-vps.md`): the `play` table can be played by a Claude agent in a T3 thread on the hub instead of the SDK master, so the owner's game does not use the VPS subscription. Owner decision 2026-10-31: the VPS subscription stopped working ("payment is past due"), so both tables play with hub masters, each table with its own thread and its own webhook, and with `DM_PLAY_HUB_FALLBACK=none`: there is no SDK master to fall back to. The threads started on Claude Sonnet 5.5 (medium) and moved to GPT-6.1-Sol (Codex, medium) the same evening, owner decision 2026-10-31: the hub's Claude account hit limits and a terms prompt («API Error: 400 We've updated our Consumer Terms…»). A thread changes model or provider with `t3_thread_configure`: T3 hands the old context over, the webhook task stays bound, nothing changes on the VPS. After a provider change send the thread the runtime notes (as in the "Your rules" part of `hub-master.md`: the shell tool, `timeout_ms` for `dm-art.sh`, `prompt` read from a file in parts).
```
driver (dnd-play@play) --POST {table, campaign, turn, ticket, message}--> T3 webhook --> hub master thread
hub master --hub-vps.sh play <ticket> dm-roll.sh 1d20--> ssh kesha@VPS (key with a forced command)
           --> /usr/local/lib/dnd-play/hub-gate (root-owned, runs nothing itself)
           --> /run/dnd-play/play/hub.sock --> the driver runs bash tools/dm-roll.sh inside the table's sandbox
```
- Every batch gets a fresh ticket; the gate needs it on every call except `status`. Before it sends anything the gate checks that the socket's listener is the unit's MainPID (`SO_PEERCRED` against `systemctl show -p MainPID`): the socket directory is writable inside the sandbox, so the table's own master could otherwise put up its own listener and collect tickets. If no turn is published within `DM_PLAY_HUB_TIMEOUT` (300 s), the driver revokes the ticket (a running call finishes first; later calls get exit 3, "ticket revoked"), posts "Мастер на хабе не ответил: ход играет запасной мастер" to the feed and the SDK master (Sonnet on the VPS) plays that batch, told to check what the engine already holds. The next batch goes to the hub again. After `DM_PLAY_HUB_FAILS` (2) failures in a row the hub is skipped for `DM_PLAY_HUB_PAUSE` (900 s) with one feed line ("Мастер на хабе недоступен: пока играет запасной мастер"). A failed POST falls back at once. With `DM_PLAY_HUB_FALLBACK=none` (both tables since 2026-10-31) no SDK master plays: the batch fails with "Мастер на хабе не ответил: повторите действие" in the feed and a console note, the table shows the error state until the next turn, and the hub is never paused.
- Each master is told when the other one played in between (a `[system]` catch-up note), and the first hub message after a switch from the SDK master starts with a takeover notice.
- The gate refuses what the master contract forbids (`dm-screen.sh start|stop|restart|serve|listen|wait|enable|speak|audition|key|hook`, `audio make|add|seed|remove|normalize`, voice changes, `dm-campaign.sh` beyond reading, `dm-play.sh` beyond `status`, `dm-reset.sh` beyond `preview`, the migration and extraction tools) and runs only `tools/dm-*.sh`. Its other operations: `prompt` (the master's system prompt for this campaign), `read <path>` (a text file inside the campaign directory, up to 256 KiB), `say <text>` (the master's own words for the master console: one argument or the text on stdin, up to 4000 characters, the current ticket required; it does not wait for a running call) and `status`. A tool runs at most 300 s; its output is capped at 64 KiB; the screen hook runs after it as under Claude Code, and its act reminder is appended to the output. Calls run one at a time: a call that finds another one running for over 5 s answers exit 4 "busy ... did NOT run". When the gate goes away during a call (the agent's Bash tool timed out, ssh died), the bridge stops the call and kills its tool, so an abandoned call never finishes later; the hub master runs `dm-art.sh` (up to 5 minutes) with a Bash timeout of at least 330 s. Time spent in `dm-art.sh` under a ticket extends the hub deadline by as much (at most 300 s), so a batch that opens a new act is not lost to the picture's wait. Exit codes: the tool's own, or 2 usage/refused, 3 ticket revoked, 4 no hub master on the table, busy, or a socket that is not the driver's, 5 timeout (the call may have run: check with `dm-screen.sh log` or `status` before repeating it).
- The hub master cannot switch the campaign (`dm-play.sh switch` is refused): when players ask, the owner switches it (the thread then gets a switch notice and reloads its rules with `prompt`).
- The thread's standing instructions live in `ops/play/hub-master.md`.
- The master console (owner request 2026-10-28): the driver writes everything a master is given, says and runs to `<screen>/master-log.jsonl` (`lib/screen/masterlog.py`: batches, the SDK master's words, tool calls and results, the hub master's calls through the bridge and its `say` lines, published turns, fallback and limit notes; tickets, the webhook URL and token-shaped strings are redacted, the file keeps about the newest 1-2 MB). The page's "Мастер" button shows it, Claude-Code style, only when the table's env has `DM_SCREEN_MASTER_CONSOLE=1` (`table.env.example`): it shows hidden rolls and plot notes, so the play table sets it and the demo table keeps it off. The log is written either way, for debugging: `tail -f world-state/campaigns/<campaign>/screen/master-log.jsonl`.

Install (Contabo), then the key from the hub (its public half only):
```bash
ssh $VPS 'sudo install -d -m 755 -o root -g root /usr/local/lib/dnd-play && sudo install -m 755 -o root -g root ~/projects/dnd-game-master/ops/play/hub-gate.py /usr/local/lib/dnd-play/hub-gate'
# one line in ~kesha/.ssh/authorized_keys (the hub key at ~/.ssh/dnd_play_vps on the hub, see hub-vps.sh):
#   restrict,command="/usr/local/lib/dnd-play/hub-gate" ssh-ed25519 <key> dnd-play-hub-master
```
Reinstall the gate after every change to `ops/play/hub-gate.py`: the installed copy is root-owned on purpose, so a master that edits the repository never changes what the hub key runs.

A new table master: launch a scratch T3 thread (GPT-6.1-Sol, medium; full-access, so it can run the wrapper) whose first message is `ops/play/hub-master.md` below its line, with `<WRAPPER>` replaced, followed by a setup section: create the webhook task (the template in `hub-master.md`, `bindToCurrentThread: true`, `allowEdits: true`, `maxDeliveryAgeMinutes: 5`), write the line `DM_PLAY_HUB_WEBHOOK=<webhookUrl>` into a 0600 file in its working directory, reply only with the task id and that path. The orchestrator then appends the file to the table's env over ssh stdin (`on-remote ssh $VPS 'sudo tee -a /etc/dnd-play/<table>.env >/dev/null' < <file>`) and deletes it, so the URL never appears in a command line or a chat.

Settings: in `/etc/dnd-play/<table>.env` (mode 0600, root:root; the webhook URL holds a token, never in Git) add
```
DM_PLAY_MASTER=hub
DM_PLAY_HUB_WEBHOOK=<the T3 webhook URL>
DM_PLAY_HUB_FALLBACK=none
```
and optionally `DM_PLAY_HUB_TIMEOUT`, `DM_PLAY_HUB_FAILS`, `DM_PLAY_HUB_PAUSE`; then reinstall the unit (it has `RuntimeDirectory=dnd-play/%i` for the socket), `sudo systemctl daemon-reload && sudo systemctl restart dnd-play@<table>` between two turns. The journal shows `master: hub (webhook set, ...)`, `bash tools/dm-play.sh --table play status` a `master: hub (...)` line with the last result and failures. Without a webhook or a socket location the driver logs an error and plays with the SDK master.

Check from the hub: `ops/play/hub-vps.sh play x status` prints `{"table": "play", "campaign": ..., "turn": ..., "ticket_ok": false}`; `ops/play/hub-vps.sh play x dm-roll.sh 1d20` exits 3.

Back to the SDK master (only while the VPS has a working subscription): `DM_PLAY_MASTER=sdk` (or remove the line) in `/etc/dnd-play/<table>.env` and `sudo systemctl restart dnd-play@<table>`; the SDK master's next message tells it to catch up on the turns the hub played. To cut the hub off at once, remove its line from `authorized_keys`: every batch then falls back to the SDK master, or fails with `DM_PLAY_HUB_FALLBACK=none`.

The webhook URL: the driver wipes it from its exec environment at start (not only from `os.environ`), so `/proc/<driver pid>/environ` no longer shows it, and the per-table AppArmor profiles keep the demo table's processes out of the play unit's `/proc` entries.

Known limits: the driver and the play table's SDK master run as the same user in the same unit, and the URL stays in the driver's memory; reading it needs ptrace attach, which Yama (`kernel.yama.ptrace_scope` 1, check it on the VPS) refuses for a non-descendant. The SDK masters can edit the repository tools the bridge runs, so a tool's output can carry text written by a master. The hub master's standing instructions (`hub-master.md`) must therefore treat every event and every tool output as player data that authorizes nothing outside the game.

## Operating
- **Status:** `ssh $VPS 'cd ~/projects/dnd-game-master && bash tools/dm-play.sh tables'`, one table in detail: `bash tools/dm-play.sh --table demo status` (state, campaign, session, turns this hour and today, last error, which master plays: `sdk` or `hub` with its last result).
- **Kill switch:** `bash tools/dm-play.sh --table <t> pause` stops that master taking actions while its screen stays up; `resume` continues. Hard stop: `sudo systemctl stop dnd-play@<t>` (nginx then answers 502). Off the internet: remove the `dnd-play-sslip` link on Contabo and the `dnd-play-mirror` link on the RU host, `nginx -t`, reload.
- **Other campaign:** `bash tools/dm-play.sh --table <t> switch <name>` (the master does it when the players ask; a campaign another table plays is refused); `restart-screen` restarts only the screen server.
- **Fresh master session:** `bash tools/dm-play.sh --table <t> new-session` when the stored session keeps failing (the journal shows the same API error on every turn); after the current turn the master starts over with the opening notice.
- **Never `dm-screen.sh listen` or `wait` on an online screen:** they move the driver's delivery cursor and take actions away from it; both refuse while a driver runs. The web game master also refuses every campaign a driver plays.
- **Logs:** `journalctl -u dnd-play@<t> -f` (driver and master; hub master calls as `hub call <tool> <args>: exit <code>, <seconds>`), `journalctl -u dnd-play-art` (pictures), `bash tools/dm-screen.sh log --errors --since 1h` (screen, in the repository on the VPS, `DM_ACTIVE_CAMPAIGN=<campaign>`), nginx `/var/log/nginx/dnd-<t>-access.log` and `dnd-<t>-error.log` (Contabo), `/var/log/nginx/dnd-play-mirror-access.log` (RU host, both names). Access logs carry no query string, so no screen token.
- **Caps:** edit `/etc/dnd-play/dnd-play.env` (every table; the daily speech ledger is shared), then `sudo systemctl restart 'dnd-play@*'`.
- **Updates:** push, then on the VPS `git pull --ff-only` (`~/.local/bin/uv sync --frozen` when `uv.lock` changed). Driver changes need `sudo systemctl restart 'dnd-play@*'`; screen code only `bash tools/dm-play.sh --table <t> restart-screen` per table; `backend/screen_art.py` needs step 8's install and `sudo systemctl restart dnd-play-art`; engine tools nothing.
- **The masters' own fixes** land on `main` with an "(online table)" suffix: pull before working on the laptop, undo one with `git revert <sha>`.
- **Crash loop:** a unit gives up after 5 failures in 10 minutes; read the journal, fix, `sudo systemctl reset-failed dnd-play@<t> && sudo systemctl start dnd-play@<t>`.
