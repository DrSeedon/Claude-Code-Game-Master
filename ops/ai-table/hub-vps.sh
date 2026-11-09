#!/bin/bash
# The AI-table hub master's way to the table's GM (AI-table V-51, owner decision 2026-11-02): runs on the hub, calls
# the VPS gate (ai-table-mvp ops/hub/hub_gate.py, installed as /usr/local/lib/ai-table/hub-gate, the forced command
# of the key) over ssh. Standing instructions: ops/ai-table/hub-master.md; runbook: ops/ai-table/README.md.
#
#   hub-vps.sh <prod|staging> <ticket> <status|prompt|turn|tool|say|done> [args...]
#   hub-vps.sh prod "$TICKET" tool state
#   hub-vps.sh prod "$TICKET" tool propose_move <<'JSON'
#   {"token_id": "fury", "to": [3, 4]}
#   JSON
#   hub-vps.sh prod "$TICKET" say --last <<'TEXT'
#   @Агафья: Кто там?
#   Болото чавкает.
#   TEXT
#
# stdin is forwarded when it is a pipe or a file (heredocs), else ssh gets -n. Exit code: the bridge's (0 ok, 1 the
# room refused), or 2 usage/refused, 3 ticket revoked or turn closed (stop), 4 no hub GM / busy, 5 timeout; 255 ssh.
# Each target has its own key (the key's forced command fixes the target): ~/.ssh/ai_table_vps (prod),
# ~/.ssh/ai_table_vps_stg (staging); AI_TABLE_VPS_KEY overrides it, AI_TABLE_VPS (default kesha@158.220.127.161) the host.

if [ "$#" -lt 3 ]; then
    echo "usage: hub-vps.sh <prod|staging> <ticket> <status|prompt|turn|tool|say|done> [args...]" >&2
    exit 2
fi

target="$1"
case "$target" in
    prod) default_key="$HOME/.ssh/ai_table_vps" ;;
    staging) default_key="$HOME/.ssh/ai_table_vps_stg" ;;
    *) echo "hub-vps.sh: unknown target '$target' (prod or staging)" >&2; exit 2 ;;
esac
host="${AI_TABLE_VPS:-kesha@158.220.127.161}"
key="${AI_TABLE_VPS_KEY:-$default_key}"
# The gate splits the command with shlex: printf %q writes $'...' for newlines and Cyrillic, which shlex cannot read.
remote="$(python3 -c 'import shlex,sys; print(shlex.join(sys.argv[1:]))' "$@")" || exit 2
# One master connection per target: a multiplexed session runs the forced command of the key that opened the
# connection, so prod and staging must never share one. A short ControlPath: a unix socket path has 108 bytes.
opts=(-i "$key" -o IdentitiesOnly=yes -o BatchMode=yes -o ConnectTimeout=15 -o ConnectionAttempts=3
      -o ServerAliveInterval=15 -o ControlMaster=auto -o "ControlPath=$HOME/.ssh/cm-ait-$target-%h-%p"
      -o ControlPersist=600)

if [ -p /dev/stdin ] || [ -f /dev/stdin ]; then
    exec ssh "${opts[@]}" "$host" "$remote"
fi
exec ssh -n "${opts[@]}" "$host" "$remote"
