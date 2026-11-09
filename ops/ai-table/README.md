# AI-table: Severin's hub master

Owner decision 2026-11-02 (AI-table ticket V-51): the AI-table's live voice GM, Severin, is played by a T3 thread on
the hub on Claude Sonnet 5.5, because the VPS Claude subscription has been past due since 2026-10-31. It is its own
thread, not one of the online tables' masters (`ops/play/README.md` §12), and the same transport:

```
ai-table-gm.service (VPS, --master hub) --POST {target, turn, ticket, source, message}--> T3 webhook --> Severin's thread
thread --bash ops/ai-table/hub-vps.sh prod <ticket> tool state--> ssh kesha@VPS (key with a forced command)
       --> /usr/local/lib/ai-table/hub-gate prod (root-owned; source ai-table-mvp ops/hub/hub_gate.py)
       --> /run/ai-table-gm/hub.sock --> the GM posts /api/gm/agent/tool (the room) / speaks with TeraTTS (/say)
```

The code lives in the AI-table repository: `server/ai_table_gm/hub.py` (the bridge and the turn), `agent.py` (`--master
hub|sdk`, the shared `Speaker`, `TOOL_SCHEMAS`), `prompt.py` (`hub_prompt`), `ops/hub/hub_gate.py`, the unit
`ops/systemd/ai-table-gm.service`; rules `.orchestra/kb/rules-gm.md` (V-51). This directory holds the hub's side:
- `hub-vps.sh` — the wrapper the thread calls: `hub-vps.sh <prod|staging> <ticket> <op> [args]`;
- `hub-master.md` — the thread's standing instructions (below its line: the first message) and the webhook template.

## Contract
- Ops: `status` (no ticket), `prompt`, `turn`, `tool <name>` (the nine allowlisted tools, JSON arguments on stdin; the
  turn is always the GM's own), `say [--last]` (≤1200 characters a call, ≤2400 a turn), `done`.
- Exit codes: 0 ok, 1 the room refused or is unreachable, 2 usage/refused, 3 ticket revoked or turn closed, 4 no hub
  GM / busy (did NOT run) / a socket that is not the GM's, 5 timeout (the gate's 50 s, or a tool cut at the turn's
  deadline: the call may have run), 255 ssh.
- Deadlines: no call within 45 s (`AI_TABLE_GM_HUB_FIRST_CALL`) → «Ведущий не ответил вовремя»; 90 s
  (`AI_TABLE_GM_HUB_TIMEOUT`) → the turn ends (ok if anything was said); a tool still running then is cut 2 s later
  (exit 5); the voice drains until 112 s; the room's own limit is 120 s. A failed webhook POST → «Ведущий не смог запуститься». No fallback to the VPS CLI.
- Each target has its own key, and the key's forced command fixes the target: `~/.ssh/ai_table_vps` → `hub-gate prod`,
  `~/.ssh/ai_table_vps_stg` → `hub-gate staging` (only for a staging rehearsal; remove its line afterwards). The
  wrapper keeps one ssh master connection per target (`~/.ssh/cm-ait-<target>-%h-%p`): a multiplexed session runs the
  forced command of the key that opened the connection.

## Set up (orchestrator; secrets never on screen or in Git)
1. Keys on the hub (writing `~/.ssh` is outside the project: needs the user's yes):
   `ssh-keygen -t ed25519 -N '' -C ai-table-hub-master -f ~/.ssh/ai_table_vps` (and `_stg` for staging).
2. The gate on the VPS: `sudo install -d -m 755 -o root -g root /usr/local/lib/ai-table && sudo install -m 755 -o root
   -g root <ai-table-mvp>/ops/hub/hub_gate.py /usr/local/lib/ai-table/hub-gate`. Reinstall after every change of
   `hub_gate.py`.
3. The key's line, appended over ssh stdin to `~kesha/.ssh/authorized_keys`:
   `from="178.104.113.18",restrict,command="/usr/local/lib/ai-table/hub-gate prod" ssh-ed25519 <pub> ai-table-hub-master`.
   Check: `ops/ai-table/hub-vps.sh prod x status` exits 4 (no hub GM yet), not 255.
4. The thread: `t3_thread_launch`, `scratch: true`, title «AI-стол: Северин (хаб-мастер)», model Claude Sonnet 5.5,
   runtime full-access (it runs the wrapper). First message: `hub-master.md` below its line with `<WRAPPER>` replaced,
   plus a setup block: create the webhook task (template above, `bindToCurrentThread: true`, `allowEdits: true`,
   `maxDeliveryAgeMinutes: 5`), write `AI_TABLE_GM_HUB_WEBHOOK=<webhookUrl>` into `./webhook.env` under `umask 077`,
   reply with only the task id and the file's absolute path.
5. The env file on the VPS (root, 0600), the URL only through stdin:
   `printf 'AI_TABLE_GM_MASTER=hub\n' | ssh $VPS 'sudo sh -c "umask 077; cat > /etc/ai-table-gm/hub.env"'`, then
   `ssh $VPS 'sudo sh -c "umask 077; cat >> /etc/ai-table-gm/hub.env"' < <path>/webhook.env`; check names only:
   `sudo sed 's/=.*/=/' /etc/ai-table-gm/hub.env`; then ask the thread to `shred -u webhook.env`.
6. Deploy the V-51 build (the AI-table repository's `.orchestra/tasks/V-51/`), then smoke from the hub:
   `hub-vps.sh prod x status` prints `"ticket_ok": false`, `hub-vps.sh prod x tool state` exits 3, and a line said on
   `/table` gets Severin's answer.

## Operating
- **Off at once:** `sudo systemctl stop ai-table-gm` — the table plays with buttons, as without a GM.
- **Cut the hub off:** remove the key's line from `authorized_keys`, delete the webhook task in T3, remove the webhook
  line from `hub.env`. `authorized_keys` is read only at login, and the wrapper's master connection (`ControlPersist=600`,
  renewed by every turn) may stay open, so also close it on the hub:
  `ssh -O exit -o ControlPath=$HOME/.ssh/cm-ait-prod-%h-%p kesha@158.220.127.161` (and `cm-ait-staging-…`). If the
  hub is out of reach, end it on the VPS: `sudo ss -tnp state established '( sport = :22 )' dst 178.104.113.18` lists
  the hub's sshd sessions; kill them by PID (this also drops the orchestrator's own ssh from the hub, which reconnects).
  The online tables' `cm-dnd-play-…` connection has the same property (`ops/play/README.md` §12).
- **Model limits:** `t3_thread_configure` to another model, then send the standing instructions again; nothing changes
  on the VPS. Whether that switch may happen without asking is the owner's decision.
- **Logs:** `sudo grep -E "hub |turn [0-9a-f]{8}:" /var/log/ai-table-gm/gm.log | tail` on the VPS — every call
  (`hub tool state: exit 0, 0.12s`, `hub say: exit 0`), refusals, the webhook and each turn's result; turn ids cut to
  8 characters; never a ticket, the URL or stdin.
- **Back to the CLI master** (only while the VPS subscription works): `AI_TABLE_GM_MASTER=sdk` in `hub.env` and remove
  its webhook line, restart. (A webhook line left there is wiped from the GM's environment at start, but it has no
  use in sdk mode.)

Known limits: the URL stays in the GM's memory (ptrace by a non-descendant is refused by Yama
`kernel.yama.ptrace_scope=1`; no AppArmor profile for the GM yet: the owner's call). Any process of kesha can connect
to the socket, but without the turn's ticket it gets only `status`. The first spoken line's delay is not measured yet
(estimate 10–25 s against about 2 s with the CLI master).
