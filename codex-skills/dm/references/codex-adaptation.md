# Codex adaptation map

This file overrides Claude-specific tool wording that remains in copied workflow references.

| Claude wording | Codex behavior |
|---|---|
| `AskUserQuestion` | Ask directly, or use the current structured-input tool when available. |
| `Read` / `Read tool` | Read the exact file with the available filesystem tool. |
| `Write` / `Edit` | Use `apply_patch` for manual file changes. |
| `Bash` | Use the shell execution tool from the repository root. |
| `WebFetch` | Use current web tools and authoritative sources. |
| `Task(agent)` | Read the matching specialist reference and execute locally; use a subagent only when permitted and useful. |
| `TodoWrite` | Use the current planning tool for substantial work. |
| `UserPromptSubmit` hooks | Run `scripts/prepare_session.sh` explicitly once at gameplay startup. |
| Claude persistent memory | Do not use shadow memory; campaign state remains in `world-state/campaigns/<name>/`. |

Paths under `.claude/additional/` are intentional. They contain the shared rules compiler, modules, styles, and campaign templates used by both clients.

If a copied reference conflicts with `SKILL.md`, compiled `/tmp/dm-rules.md`, or current repository behavior, prefer those sources in that order and report the stale reference for repair.
