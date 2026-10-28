#!/bin/bash
# The hub master's way to its online table (owner decision 2026-10-28): runs on the hub, calls the VPS gate
# (ops/play/hub-gate.py, the forced command of the key) over ssh. Runbook: ops/play/README.md, "Hub master (play table)".
#
#   hub-vps.sh <table> <ticket> <tool|prompt|status|read> [args...]
#   hub-vps.sh play "$TICKET" dm-roll.sh 1d20+3
#   hub-vps.sh play "$TICKET" dm-screen.sh turn --file - <<'JSON'
#   {...}
#   JSON
#
# stdin is forwarded when it is a pipe or a file (heredocs), else ssh gets -n. Exit code: the tool's, or the gate's
# 2 usage, 3 ticket revoked (stop and wait for the next event), 4 no hub master on that table, 5 timeout; 255 ssh.
# DND_PLAY_VPS (default kesha@158.220.127.161) and DND_PLAY_VPS_KEY (default ~/.ssh/dnd_play_vps) pick the host and key.

if [ "$#" -lt 3 ]; then
    echo "usage: hub-vps.sh <table> <ticket> <tool|prompt|status|read> [args...]" >&2
    exit 2
fi

host="${DND_PLAY_VPS:-kesha@158.220.127.161}"
key="${DND_PLAY_VPS_KEY:-$HOME/.ssh/dnd_play_vps}"
# The gate splits the command with shlex: printf %q writes $'...' for newlines and Cyrillic, which shlex cannot read.
remote="$(python3 -c 'import shlex,sys; print(shlex.join(sys.argv[1:]))' "$@")" || exit 2
opts=(-i "$key" -o IdentitiesOnly=yes -o BatchMode=yes -o ConnectTimeout=15 -o ConnectionAttempts=3
      -o ServerAliveInterval=15 -o ControlMaster=auto -o "ControlPath=$HOME/.ssh/cm-dnd-play-%C" -o ControlPersist=600)

if [ -p /dev/stdin ] || [ -f /dev/stdin ]; then
    exec ssh "${opts[@]}" "$host" "$remote"
fi
exec ssh -n "${opts[@]}" "$host" "$remote"
