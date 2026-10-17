# Deployment and VPS operations

Moved verbatim from the root AGENTS.md on 2026-10-17 (task V-47, owner's rules-structure decision). Edit here when a rule changes.

## Deployment and VPS operations

### Deploy
- The public site is `https://dnd-game-master.duckdns.org`; the service is `dnd-game-master.service`. Its site password is held only in the VPS `.env` as `DND_AUTH_PASSWORD`. This is a public repository: never put a password, token, or key in a tracked file.
- Do not restore `https://dnd.seedon.ru`: it was removed on 2026-08-07 because the domain belongs to a company that needed to remove the German-server association; the name now resolves through that company's Moscow wildcard.
- The DuckDNS account token is account-wide. This project may update only `dnd-game-master`; `dnd-table` belongs to the AI-table project and is the only other permitted name. Always pass the intended domain explicitly; never iterate over account domains.
- A wildcard can answer for names that were never configured. Probe with a deliberately nonexistent name and compare results: matching responses can come from the wildcard rather than the intended virtual host. A `404` or `200` from that wildcard probe says nothing about the target host.
- **A `200` is transport, not meaning.** DuckDNS can return HTTP 200 with body `KO` for a revoked token. Compare the response body with the expected value and test the failure branch with a deliberately wrong value; `curl -f` alone is insufficient.
- Deploy by pushing to `origin/main`, then pulling with `git pull --ff-only` in the VPS clone. The VPS pulls from GitHub, not from a developer machine. Do not use rsync: the VPS is a real Git clone. Run Git as `kesha`, never root; root-owned files break writes under the service user. `su -s /bin/bash kesha` works; `su - kesha` hangs in the configured environment. Check ownership before deploy with `find /home/kesha/projects/dnd-game-master ! -user kesha`.
- Live `world-state/campaigns`, `world-state/usage`, and `.env` are not in Git and exist only on the VPS. Never run `git clean` or reclone over them without a backup. Do not treat an empty Git directory as evidence that live data is absent.
- `sudo` from an agent process fails because `orchestra.service` sets `NoNewPrivileges=yes`. A fresh SSH process to `kesha@localhost` leaves that unit and can use kesha's configured NOPASSWD sudo: `ssh kesha@localhost 'sudo ...'`. Check the actual remote operation and its result.
- The DuckDNS token file is `.duckdns_token` in the project directory, gitignored; do not print or copy its contents. The keep-alive job may repoint DNS after an address change. A denied `crontab -l` under `NoNewPrivileges` means cron state is unknown, not absent.
- The service listens on port `18083`; a direct proxy is not needed for the current VPS deployment. Tell the owner before a production install.

### Orchestrator on the VPS
- The project orchestrator runs on the VPS. Read `docs/vps-handoff.md` before migration or handoff; it preserves the migration state and environment-specific traps.
- Use Orchestra's `scripts/migrate_agent.py` to migrate a session with its transcript, logs, inbox, and worktrees. Do not hand-write database `INSERT` or `UPDATE` statements: the live server keeps session state in memory and `save_session()` supplies defaults. The migration tool uses an upsert and its idle check prevents the orchestrator from migrating itself; an external actor must launch it.
- Never restart Orchestra on the VPS yourself. It interrupts active turns across projects; the Orchestra orchestrator owns that restart.
- MCP servers are per-session in the `mcp_servers_custom` database column, not in `~/.claude.json`. Orchestra MCP is injected automatically. Ask the Orchestra orchestrator to provision other servers.
- The dashboard's internal port is firewalled; use the configured public dashboard hostname externally or loopback on the VPS.
- Skills copied from a laptop may contain `/mnt/data/...` paths. Search for those paths before trusting a copied skill and replace machine-specific paths with a configurable environment variable and a suitable default.
- A configured MCP entry proves nothing about the executable: verify that the binary exists and invoke it. A server-wide `mcp-pandoc` entry once existed while `pandoc` was missing.

