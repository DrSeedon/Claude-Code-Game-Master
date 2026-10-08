# V-15 result

Merged the project rules into the root `AGENTS.md`, made root `CLAUDE.md` a relative symlink to it, updated the VPS handoff references, and deleted the obsolete consolidation item from `TODO.md`. The rules-file note records the 2026-10-07 measurements for the bundled and system Claude CLIs. Both 2026-10-07 owner decisions are recorded beside the AI-table execution policy.

Correction (2026-10-08): Orchestra Claude workers use the system CLI (`cli_path=shutil.which("claude")`, 2.1.293) and read `AGENTS.md` alone; see Orchestra KB `.orchestra/kb/agent-control.md`. The `CLAUDE.md` symlink remains for clients that read only that filename.

## Claude injection check

The final check uses Orchestra's Python 3.12 `claude_agent_sdk` and bundled CLI 2.1.205, with `setting_sources=["user", "project", "local"]` and file tools disabled. It asks which two DuckDNS names the project may touch. The symlink fixture returned `dnd-game-master` and `dnd-table`; the AGENTS-only control returned `UNKNOWN`. Both checks passed. Raw outputs and exit codes are in `claude-proof*.txt`.

`git ls-files -s CLAUDE.md` reported mode `120000`. `uv run pytest tests/test_secret_guard.py -q` passed (3 tests), confirming the secret guard reads the symlink target without failing. Final full suite: `uv run pytest --timeout=120 --timeout-method=signal -q` → 570 passed in 33.29s; output is in `pytest-full.txt`.
