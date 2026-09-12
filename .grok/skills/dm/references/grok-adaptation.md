# Grok Build adaptation map

Shared command/specialist references under `codex-skills/dm/references/` were
written for Claude and Codex. When wording conflicts with Grok tools, use this
table. Prefer this file + `.grok/skills/dm/SKILL.md` + compiled `/tmp/dm-rules.md`
over stale tool names in copied references.

| Wording in references | Grok Build behavior |
|---|---|
| `AskUserQuestion` | `ask_user_question` for short menus; otherwise ask in chat |
| `Read` / `Read tool` | `read_file` on the exact path |
| `Write` / `Edit` / `apply_patch` | `write` / `search_replace` only when tools cannot do the job |
| `Bash` / shell | `run_terminal_command` from the **project root** |
| `WebFetch` / web search | `web_search` / `web_fetch` / MCP websearch as available |
| `Task(agent)` / subagent | `spawn_subagent` only for independent parallel work |
| `TodoWrite` | `todo_write` for multi-step non-play tasks; skip during pure play |
| Claude `UserPromptSubmit` hooks | **Do not rely on them.** Run `bash codex-skills/dm/scripts/prepare_session.sh` once at gameplay startup (and after compaction if `/tmp/dm-rules.md` is missing) |
| Codex app-server / Claude Agent SDK | Not used in Grok CLI play. Grok **is** the DM; state changes go through `tools/*.sh` |
| Image generation / cinematic skill | Grok `image_gen` / `image_edit`; aspect `16:9` for cinematic beats. Show the returned `images/N.jpg` path |
| Persistent Claude memory / shadow memory | Forbidden. Campaign state only under `world-state/campaigns/<name>/` |
| Paths under `.claude/additional/` | Intentional shared runtime for all clients — keep using them |

## Session prepare contract

```bash
cd <project-root>
export UV_CACHE_DIR="${UV_CACHE_DIR:-/tmp/dm-uv-cache}"
bash codex-skills/dm/scripts/prepare_session.sh
# then read /tmp/dm-rules.md completely
```

`prepare_session.sh` compiles rules, starts the session, and prints campaign
context. After it succeeds, do not re-run `dm-overview.sh`, `dm-player.sh show`,
`dm-plot.sh list`, `dm-consequence.sh check`, `dm-npc.sh party`, or re-cat
session/handoff files unless investigating a mismatch.

## Tool invocation style

- Always call tools from the repository root (or with paths relative to it).
- Prefer one mechanical tool call that matches the beat over a spray of partial updates.
- Narrate only after tools report success (or an explicit failure to play through).

## Priority when sources disagree

1. `.grok/skills/dm/SKILL.md`
2. Compiled `/tmp/dm-rules.md`
3. This adaptation map
4. `codex-skills/dm/references/...`
5. Legacy `.claude/commands/...`

Report stale references instead of silently inventing new procedures.
