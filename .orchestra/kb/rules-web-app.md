# Models, web application map, wizard and security

Moved verbatim from the root AGENTS.md on 2026-10-17 (task V-47, owner's rules-structure decision). Edit here when a rule changes.

## Models and Claude CLI
- Selectable Claude models are defined in `backend/runtime/registry.py`: Sonnet 5, Sonnet 5.5, Opus 5, Opus 5.5, and Fable 5.1. The default remains `claude-sonnet-5`. Per-turn usage and model prices are in `backend/usage_log.py`; usage is persisted in `world-state/usage/game-turns.jsonl` and exposed by `GET /api/usage`.
- **`claude-agent-sdk` ships a Claude Code CLI inside its wheel and may select it before the system CLI.** That bundled CLI is frozen at the SDK release date and can reject a newer model while the system CLI supports it. Measured 2026-09-18: bundled 2.1.191 rejected `claude-fable-5-1`, while system CLI 2.1.263 ran it. `ClaudeSDKProvider` passes `options.cli_path = shutil.which("claude")`; keep this selection.

## Web application map
```text
Browser → nginx/TLS → FastAPI (`backend/server.py`)
  /ws/game   → GameSession registry → ClaudeSDKProvider → Claude CLI
  /ws/wizard → ephemeral provider + WizardMCP UI tools + dm-*.sh tools
  /api/*     → campaign, status, model, and health endpoints
  /          → static frontend
```

Important files: `backend/server.py` (HTTP and WebSocket routes); `backend/game_session.py`
(session registry and turn lifecycle); `backend/live_broker.py` (pub/sub); `backend/event_log.py`
(append-only log); `backend/providers/claude_sdk.py` (SDK and streaming); `backend/claude_dm.py`
(prompt assembly); `backend/wizard_mcp.py` and `backend/wizard_prompt.py` (wizard); `backend/auth.py`
(cookie authentication); `backend/config.py` (environment configuration); `backend/campaign_api.py`
(campaign endpoints); `backend/usage_log.py` (turn usage); `frontend/js/app.js` (client application).

## Wizard and SDK integration
- The wizard creates campaign data through CLI tools (`dm-campaign.sh`, `dm-location.sh`, `dm-npc.sh`, `dm-plot.sh`, `dm-player.sh`), not a JSON blueprint. Wizard MCP has exactly three UI tools: `show_choices`, `clear_choices`, and `wizard_complete`. `pendingWizardMsg` queues a message sent while generation is in progress and sends it when generation completes.
- Do not set the Claude SDK `allowed_tools` option. Under `bypassPermissions`, the tools are already permitted; the old allowlist blocked Bash tools in both wizard and game mode (measured 2026-07-20).

## Web application security rules
- Campaign names are validated against path traversal such as `../`; session IDs must match `^[A-Za-z0-9_-]{1,64}$`.
- `bypassPermissions` is acceptable only for this password-protected site. Authentication middleware skips only `/auth/*` and static assets.

