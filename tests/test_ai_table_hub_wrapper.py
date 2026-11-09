"""The AI-table hub master's ssh wrapper (ops/ai-table/hub-vps.sh, AI-table V-51): a fake `ssh` on PATH records what
the wrapper would send, so no network and no key are needed."""

import os
import shlex
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
WRAPPER = REPO / "ops" / "ai-table" / "hub-vps.sh"
FAKE_SSH = """#!/bin/bash
out="$FAKE_SSH_OUT"
for arg in "$@"; do printf '%s\\0' "$arg"; done > "$out.argv"
if [ "$1" = "-n" ]; then : > "$out.stdin"; else cat > "$out.stdin"; fi
exit "${FAKE_SSH_EXIT:-0}"
"""


@pytest.fixture
def fake(tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    ssh = bin_dir / "ssh"
    ssh.write_text(FAKE_SSH, encoding="utf-8")
    ssh.chmod(0o755)
    home = tmp_path / "home"
    home.mkdir()
    env = {"PATH": f"{bin_dir}:{os.environ.get('PATH', '/usr/bin:/bin')}", "HOME": str(home),
           "FAKE_SSH_OUT": str(tmp_path / "ssh")}
    return env, tmp_path / "ssh", home


def wrap(env, args, stdin=None, **extra):
    kwargs = {"input": stdin.encode()} if stdin is not None else {"stdin": subprocess.DEVNULL}
    return subprocess.run(["bash", str(WRAPPER), *args], env={**env, **extra}, capture_output=True, timeout=30, **kwargs)


def sent(out):
    argv = out.with_suffix(".argv").read_bytes().decode().split("\0")[:-1]
    return argv, out.with_suffix(".stdin").read_bytes().decode()


def test_cyrillic_and_newlines_survive_shlex_join_and_the_prod_key_is_used(fake):
    env, out, home = fake
    done = wrap(env, ["prod", "Tk_1-x", "say", "--last", "Тише.\n@Агафья: «Кто там?» Don't"])
    assert done.returncode == 0, done.stderr
    argv, stdin = sent(out)
    assert argv[0] == "-n" and stdin == ""
    assert argv[argv.index("-i") + 1] == f"{home}/.ssh/ai_table_vps"
    assert f"ControlPath={home}/.ssh/cm-ait-prod-%h-%p" in argv
    assert argv[-2] == "kesha@158.220.127.161"
    assert shlex.split(argv[-1]) == ["prod", "Tk_1-x", "say", "--last", "Тише.\n@Агафья: «Кто там?» Don't"]


def test_staging_has_its_own_key_and_master_connection_and_a_heredoc_is_forwarded(fake):
    env, out, home = fake
    done = wrap(env, ["staging", "t", "tool", "hero_options"], stdin='{"hero": "ярина"}\n')
    assert done.returncode == 0, done.stderr
    argv, stdin = sent(out)
    assert argv[0] != "-n" and stdin == '{"hero": "ярина"}\n'
    assert argv[argv.index("-i") + 1] == f"{home}/.ssh/ai_table_vps_stg"
    assert f"ControlPath={home}/.ssh/cm-ait-staging-%h-%p" in argv
    assert shlex.split(argv[-1]) == ["staging", "t", "tool", "hero_options"]


def test_overrides_unknown_targets_usage_and_the_exit_code(fake):
    env, out, home = fake
    done = wrap(env, ["prod", "t", "status"], AI_TABLE_VPS="kesha@10.0.0.9", AI_TABLE_VPS_KEY="/k/key", FAKE_SSH_EXIT="3")
    assert done.returncode == 3
    argv, _ = sent(out)
    assert argv[argv.index("-i") + 1] == "/k/key" and argv[-2] == "kesha@10.0.0.9"
    assert wrap(env, ["demo", "t", "status"]).returncode == 2
    assert wrap(env, ["prod", "t"]).returncode == 2
