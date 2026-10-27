# Online table runbook: dnd-play.seedon.ru

The HTML screen online behind a password: one shared table, campaign `pratchett-dungeon`, a Claude Agent SDK master on Sonnet 5.5 (owner decisions 2026-10-26, `.orchestra/kb/rules-deploy-vps.md`).

```
guest -> dnd-play.seedon.ru (RU host 89.23.102.244, vhost dnd-play-mirror)
      -> play-158-220-127-161.sslip.io (Contabo 158.220.127.161, vhost dnd-play-sslip: password gate, limits, headers)
      -> 127.0.0.1:18116 (dnd-play.service: backend.screen_driver = screen server + master)
```

| File | Installed as |
|---|---|
| `dnd-play.service` | `/etc/systemd/system/dnd-play.service` (Contabo) |
| `dnd-play.env.example` | `/etc/dnd-play/dnd-play.env` (Contabo) |
| `nginx-dnd-play-sslip` | `/etc/nginx/sites-available/dnd-play-sslip` + link in `sites-enabled` (Contabo) |
| `nginx-dnd-play-mirror` | `/etc/nginx/sites-available/dnd-play-mirror` + link in `sites-enabled` (RU host) |
| `.claude/additional/infrastructure/screen-driver-contract.md` | the master's contract prompt (in the repository) |

## Rules for whoever runs this
- The install is owner-approved (2026-10-26); still tell the owner when it starts and when it is done.
- Never restart Orchestra on the VPS. Reload nginx, never restart it.
- On the RU host touch only `dnd-play-mirror` (its file and its link). Never a seedon.ru record at 158.220.127.161, never `dnd.seedon.ru`.
- Git on the VPS only as `kesha`, never root. `sudo` works through a fresh SSH session (`ssh kesha@158.220.127.161 'sudo ...'`; from an Orchestra agent on the VPS use `ssh kesha@localhost`).
- Keys are checked by name only; never print a value. The site password lives only in the laptop `.env` (`DND_PLAY_PASSWORD`); the servers keep its hash.
- The password is typed into the screen's own login page (owner 2026-10-27), never a browser basic-auth box: nginx asks the screen `GET /_auth` before every request (`lib/screen/gate.py`) and fails closed.
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

## 3. Campaign copy (with a backup)
The VPS copy becomes the live one; do not play `pratchett-dungeon` on the laptop afterwards.
```bash
bash tools/dm-screen.sh stop
bash tools/dm-campaign.sh path        # must end with pratchett-dungeon
# refresh the html-screen rule embedded in campaign-rules.md (it gains the online-driver note)
bash .claude/additional/infrastructure/dm-campaign-custom-rules.sh remove html-screen
bash .claude/additional/infrastructure/dm-campaign-custom-rules.sh apply html-screen
# backup of whatever the VPS has now, in world-state/campaign-backups/ (ignored by Git; world-state/backups/ is tracked)
ssh $VPS 'cd ~/projects/dnd-game-master/world-state && ts=$(date +%F-%H%M) && mkdir -p campaign-backups && for d in campaigns/pratchett-dungeon audio-library; do [ ! -d "$d" ] || tar czf "campaign-backups/online-before-$(basename "$d")-$ts.tgz" "$d" || exit 1; done && ls -la campaign-backups | tail -3'
# copy without the laptop's runtime files
tar czf - -C world-state \
  --exclude='campaigns/pratchett-dungeon/screen/chrome-profile' \
  --exclude='campaigns/pratchett-dungeon/screen/server.json' \
  --exclude='campaigns/pratchett-dungeon/screen/server.log' \
  --exclude='campaigns/pratchett-dungeon/screen/log' \
  --exclude='campaigns/pratchett-dungeon/screen/inbox.jsonl' \
  --exclude='campaigns/pratchett-dungeon/screen/wait-cursor.json' \
  --exclude='campaigns/pratchett-dungeon/screen/gm-session.json' \
  --exclude='campaigns/pratchett-dungeon/screen/gm-system-prompt.md' \
  --exclude='.runtime-session.json' \
  campaigns/pratchett-dungeon audio-library \
| ssh $VPS 'set -e; cd ~/projects/dnd-game-master/world-state; rm -rf .incoming; mkdir .incoming; tar xzf - -C .incoming; rm -rf campaigns/pratchett-dungeon audio-library; mv .incoming/campaigns/pratchett-dungeon campaigns/; mv .incoming/audio-library .; rm -rf .incoming; ls campaigns/pratchett-dungeon/screen'
```

## 4. Table state
```bash
ssh $VPS 'cat > ~/projects/dnd-game-master/world-state/online-play.json' <<'EOF'
{"campaign": "pratchett-dungeon", "port": 18116, "paused": false, "screen_restart": 0}
EOF
```

## 5. Caps and model
```bash
ssh $VPS 'sudo install -d -m 755 /etc/dnd-play && sudo install -m 644 ~/projects/dnd-game-master/ops/play/dnd-play.env.example /etc/dnd-play/dnd-play.env'
```

## 6. Service
```bash
ssh $VPS 'sudo install -m 644 ~/projects/dnd-game-master/ops/play/dnd-play.service /etc/systemd/system/dnd-play.service; sudo systemd-analyze verify /etc/systemd/system/dnd-play.service'
# read the output: lines about dnd-play.service must be fixed first, lines about other units do not matter
ssh $VPS 'sudo systemctl daemon-reload && sudo systemctl enable --now dnd-play && sleep 20 && systemctl --no-pager status dnd-play | head -12 && journalctl -u dnd-play -n 40 --no-pager'
ssh $VPS 'cd ~/projects/dnd-game-master && bash tools/dm-play.sh status && curl -s -o /dev/null -w "%{http_code}\n" -H "Host: 127.0.0.1:18116" http://127.0.0.1:18116/'
# the sandbox: ~/.ssh holds only what git push needs, git reaches GitHub, ssh to kesha@localhost is refused
ssh $VPS 'pid=$(systemctl show -p MainPID --value dnd-play) && sudo nsenter -t $pid -m ls -A /home/kesha/.ssh && sudo nsenter -t $pid -m -S $(id -u) -G $(id -g) env HOME=/home/kesha git -C /home/kesha/projects/dnd-game-master ls-remote --heads origin main && ! sudo nsenter -t $pid -m -S $(id -u) -G $(id -g) env HOME=/home/kesha ssh -o BatchMode=yes -o ConnectTimeout=5 kesha@localhost true && echo sandbox ok'
```
Expected: the unit is active, the status shows the campaign and a state of `idle` (or `thinking` on the opening turn), the page answers `200`, the journal's "screen limits" line shows the caps, and the sandbox check lists `config id_ed25519_github known_hosts`, one `refs/heads/main` line and `sandbox ok`. If git cannot reach GitHub, compare the github.com entry of `~/.ssh/config` with the unit's BindReadOnlyPaths before anything else.

## 7. Password (hash only on the server)
```bash
grep -q '^DND_PLAY_PASSWORD=' .env || printf '\nDND_PLAY_PASSWORD=%s\n' "$(openssl rand -base64 32 | tr -dc 'A-Za-z0-9' | head -c 24)" >> .env
uv run python -c 'from dotenv import dotenv_values; print(dotenv_values(".env")["DND_PLAY_PASSWORD"])' \
| uv run python -m lib.screen.gate config \
| ssh $VPS 'sudo sh -c "umask 027; cat > /etc/dnd-play/login.json.new && chgrp kesha /etc/dnd-play/login.json.new && mv /etc/dnd-play/login.json.new /etc/dnd-play/login.json" && sudo stat -c "%U:%G %a" /etc/dnd-play/login.json'
```
Expected: `root:kesha 640`. The gate file (`DM_SCREEN_LOGIN_FILE` in the unit) holds the password's scrypt hash and the key that signs the 30-day login cookie; the screen server reads it as `kesha`, so the master can read it too (it is already inside). The screen reads it on every request: to rotate, change `DND_PLAY_PASSWORD` and run this step again; the new key signs every device out. Until the file exists the gate answers 500 and nobody gets in.

## 8. Contabo vhost: port 80, certificate, then 443
```bash
# phase 1: the file without the 443 server
ssh $VPS "sed '/^# ---- 443 BEGIN/,/^# ---- 443 END/d' ~/projects/dnd-game-master/ops/play/nginx-dnd-play-sslip | sudo tee /etc/nginx/sites-available/dnd-play-sslip >/dev/null && sudo ln -sfn /etc/nginx/sites-available/dnd-play-sslip /etc/nginx/sites-enabled/dnd-play-sslip && sudo nginx -t && sudo systemctl reload nginx"
# certificate: webroot, like table-158-220-127-161.sslip.io (the existing deploy hook reloads nginx on renewal)
ssh $VPS 'sudo certbot certonly --webroot -w /var/www/html -d play-158-220-127-161.sslip.io --non-interactive --agree-tos --keep-until-expiring && sudo ls /etc/letsencrypt/live/play-158-220-127-161.sslip.io/'
# phase 2: the whole file
ssh $VPS 'sudo install -m 644 ~/projects/dnd-game-master/ops/play/nginx-dnd-play-sslip /etc/nginx/sites-available/dnd-play-sslip && sudo nginx -t && sudo systemctl reload nginx'
```
If `nginx -t` fails, remove the link (`sudo rm /etc/nginx/sites-enabled/dnd-play-sslip`) before anything else.

## 9. RU mirror
```bash
ssh $RU 'getent hosts dnd-play.seedon.ru'       # 89.23.102.244 (the company wildcard)
ssh $RU 'cat > /etc/nginx/sites-available/dnd-play-mirror' < ops/play/nginx-dnd-play-mirror
ssh $RU 'ln -sfn /etc/nginx/sites-available/dnd-play-mirror /etc/nginx/sites-enabled/dnd-play-mirror && nginx -t && systemctl reload nginx'
```
If `nginx -t` fails, `rm /etc/nginx/sites-enabled/dnd-play-mirror` at once: every other site on that host shares the reload.

## 10. Checks
```bash
PW=$(uv run python -c 'from dotenv import dotenv_values; print(dotenv_values(".env")["DND_PLAY_PASSWORD"])')
JAR=$(mktemp)
for u in https://play-158-220-127-161.sslip.io https://dnd-play.seedon.ru; do
  curl -s -o /dev/null -w "$u/ signed out -> %{http_code} %{redirect_url}\n" "$u/"                  # 302 $u/login
  curl -s -o /dev/null -w "$u/api/state signed out -> %{http_code}\n" "$u/api/state"               # 401
  curl -s -o /dev/null -w "$u/_auth -> %{http_code}\n" "$u/_auth"                                  # 404 (internal)
  curl -s -o /dev/null -w "$u wrong password -> %{http_code}\n" --data-urlencode password=wrong "$u/login"   # 401
  printf '%s' "$PW" | curl -s -o /dev/null -c "$JAR" -w "$u password -> %{http_code}\n" --data-urlencode password@- "$u/login"   # 303
  curl -s -o /dev/null -b "$JAR" -w "$u/ signed in -> %{http_code}\n" "$u/"                        # 200
done
curl -s -o /dev/null -w '%{http_code}\n' http://dnd-play.seedon.ru/   # 301
# the form proves the answer came from the screen behind the play vhost, not from a wildcard
curl -s https://dnd-play.seedon.ru/login | grep -c 'action="/login"'   # 1
curl -s -b "$JAR" -D - -o /dev/null https://dnd-play.seedon.ru/ | grep -iE '^(content-security-policy|x-robots-tag)'
# Server-Sent Events through both hops: "event: state" at once, ": ping" every 15 s (curl stops after 40 s)
TOKEN=$(curl -s -b "$JAR" https://dnd-play.seedon.ru/ | grep -o 'data-token="[^"]*"' | cut -d'"' -f2)
curl -s -b "$JAR" -N --max-time 40 "https://dnd-play.seedon.ru/api/events?token=$TOKEN" | grep -E '^(event: state|: ping)'
rm -f "$JAR"; unset PW TOKEN JAR
```
Last, in a browser: open https://dnd-play.seedon.ru/, sign in on the login page, press an option. The page shows the Master thinking, a turn arrives, and `bash tools/dm-play.sh status` on the VPS counts it.

## Operating
- **Status:** `ssh $VPS 'cd ~/projects/dnd-game-master && bash tools/dm-play.sh status'` (state, campaign, session, turns this hour and today, last error).
- **Kill switch:** `bash tools/dm-play.sh pause` stops the master taking actions while the screen stays up; `resume` continues. Hard stop: `sudo systemctl stop dnd-play` (nginx then answers 502). Off the internet: remove the `dnd-play-sslip` link on Contabo and the `dnd-play-mirror` link on the RU host, `nginx -t`, reload.
- **Other campaign:** `bash tools/dm-play.sh switch <name>` (the master does it when the players ask); `restart-screen` restarts only the screen server.
- **Fresh master session:** `bash tools/dm-play.sh new-session` when the stored session keeps failing (the journal shows the same API error on every turn); after the current turn the master starts over with the opening notice.
- **Never `dm-screen.sh listen` or `wait` on the online screen:** they move the driver's delivery cursor and take actions away from it; both refuse while the driver runs. The web game master also refuses the campaign the driver plays.
- **Logs:** `journalctl -u dnd-play -f` (driver and master), `bash tools/dm-screen.sh log --errors --since 1h` (screen, in the repository on the VPS), nginx `/var/log/nginx/dnd-play-access.log` and `dnd-play-error.log` (Contabo), `/var/log/nginx/dnd-play-mirror-access.log` (RU host). Access logs carry no query string, so no screen token.
- **Caps:** edit `/etc/dnd-play/dnd-play.env`, then `sudo systemctl restart dnd-play`.
- **Updates:** push, then on the VPS `git pull --ff-only` (`~/.local/bin/uv sync --frozen` when `uv.lock` changed). Driver changes need `sudo systemctl restart dnd-play`; screen code only `bash tools/dm-play.sh restart-screen`; engine tools nothing.
- **The master's own fixes** land on `main` with an "(online table)" suffix: pull before working on the laptop, undo one with `git revert <sha>`.
- **Crash loop:** the unit gives up after 5 failures in 10 minutes; read the journal, fix, `sudo systemctl reset-failed dnd-play && sudo systemctl start dnd-play`.
