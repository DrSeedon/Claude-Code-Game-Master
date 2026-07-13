# Wizard handler — streaming + in-process MCP

## What
Rewrote `/ws/wizard` to stream token-by-token like the game handler, and moved the
wizard MCP from a file-polling subprocess to the SDK's in-process MCP.

## Root cause of the 3 reported bugs
1. **No streaming** — the handler did `if event["type"] == "text_delta": continue` (dropped
   every token). Fixed: `text_delta → send({type:"stream", content})`, same as game.
2. **Tool JSON leaked into chat / tools not intercepted** — the MCP ran as a subprocess
   (`uv run python wizard_mcp.py`) writing to a temp file that was polled *after* the turn.
   Fragile: if the subprocess was slow/mismatched, the DM emitted the tool call as plain text.
   Fixed: in-process MCP (`create_sdk_mcp_server`) — tools run in the same process and push to
   an event queue.
3. **Activity blocks** — the provider already emits `activity` for tool_use/tool_result; the
   handler now forwards them (was already partly there; now consistent with the stream path).

## Changes
| File | Change |
|------|--------|
| `backend/wizard_mcp.py` | Replaced file-based FastMCP subprocess with `WizardEvents` (sync push/drain buffer) + `build_wizard_mcp(events)` using SDK `create_sdk_mcp_server` + `tool`. Same 3 tools (show_choices / clear_choices / create_campaign); they push structured events instead of writing a file. Removed `__main__`/stdio entrypoint. |
| `backend/server.py` | `/ws/wizard`: build `WizardEvents()` + `{"wizard": build_wizard_mcp(events)}` (in-process). Loop: `text_delta→stream`, `text/activity/error` forwarded, then `events.drain()` → show_choices/clear_choices/wizard_complete. Deleted the output_file/uuid/subprocess config. Import `WizardEvents, build_wizard_mcp`. |
| `tests/test_wizard.py` | The 2 file-output tests were obsolete (old API). Replaced with: config-shape test, events push/drain test, and real tool-invocation tests (invoke `show_choices`/`clear_choices` via the MCP `CallToolRequest` handler, assert the event landed in `WizardEvents`). |

## Event contract (unchanged for the frontend)
Wizard now emits the SAME events as game: `stream` / `text` / `activity` / `error` / `done`,
plus wizard-only `show_choices` / `clear_choices` / `wizard_complete`. The frontend `handleEvent`
is mode-agnostic and already handles all of these — no frontend change needed.

## Verification
- **187 backend tests pass** (`uv run pytest`, was 185 + 2 new wizard tests; the 2 obsolete
  file-output tests removed). `tests/test_wizard.py`: 24 pass.
- **In-process MCP builds**: `build_wizard_mcp(WizardEvents())` → `{'type':'sdk','name':'wizard',...}`.
- **Real tool invocation** (not a mock): invoked `show_choices` via the server's
  `CallToolRequest` handler → event landed in `WizardEvents.drain()` with the right `step`/`data`.
- **Provider contract**: `claude_sdk.py._stream_events` emits `text_delta` per token
  (`include_partial_messages=True`) — the handler now forwards these as `stream`. Same code path
  the game handler uses for its typewriter.
- `node --check app.js` OK; server imports OK; no file-hack remnants.

## NOT verified (honest gap)
- **No live end-to-end LLM turn was run** (would burn a subscription turn; the run was declined).
  Streaming is verified *mechanically* — the provider emits `text_delta`, the handler forwards it
  as `stream`, and the frontend's proven game typewriter consumes `stream`. But a real "type a
  message → watch tokens appear + choices pop" round-trip has not been executed. Recommend a quick
  manual smoke on the VPS/localhost after merge.

## Bug caught in self-review (would have broken prod)
Building the tool schema with the dict-shorthand (`{"name": str, "genre": str, ...}`) makes the
SDK mark **every** field required. So `create_campaign` rejected any call missing `genre`/`tone`/…
with `Input validation error: 'genre' is a required property` — the DM almost never fills all 10
fields, so campaign creation would fail in prod. Fixed by giving `create_campaign` a full JSON
Schema with `"required": ["name", "character_name"]` and the rest optional. Verified: a minimal
`{name, character_name}` call now succeeds and pushes the event (test `test_create_campaign_optional_fields`).
(`show_choices` keeps the shorthand — its 4 fields genuinely are all required.)

## Adversarial self-review
- **drain() timing** — verified empirically: invoked `show_choices` then `clear_choices` via the
  MCP `CallToolRequest` handler, then `drain()` → both events present, in order, nested data intact.
  In-process tools are `await`ed by the SDK before the turn's `ResultMessage` ends the loop.
- **Concurrent turns on one socket**: wizard is single-connection; `receive_text` serializes turns.
- **events reused across turns**: `drain()` at turn start (clear leftovers) + after (emit). One
  `WizardEvents` per connection.

## Codex review — CLEAN
`codex_review` (bg-40ff1c7461) landed after an initial artifact-write delay. Verdict:
**"No introduced correctness issues were identified in the wizard streaming and in-process MCP
changes."** See `docs/tasks/wizard-streaming/codex-review-impl.md`. The one real bug (optional-fields
schema) was caught and fixed in self-review *before* the commit, so Codex saw the corrected code.
