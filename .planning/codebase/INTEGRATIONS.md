# External Integrations

**Analysis Date:** 2026-03-29

## APIs & External Services

**D&D 5e Reference API:**
- Service: `https://www.dnd5eapi.co/api/2014` (open, no auth)
- SDK/Client: stdlib `urllib.request` — no third-party HTTP client
- Implementation: `features/dnd-api/dnd_api_core.py`
- Consumers: `features/dnd-api/monsters/dnd_monster.py`, `dnd_monsters.py`, `dnd_monsters_api_filter.py`, `dnd_encounter_v2.py`
- Auth: None required
- Purpose: Fetch monster stats, abilities, spells for combat prep

**Anthropic Claude API:**
- SDK: `anthropic>=0.76.0` listed as core dependency
- The SDK is installed but not called directly from `lib/` or `tools/` Python code — all Claude interaction is driven by the Claude Code CLI environment wrapping this tool suite
- No direct API key management in Python files found

**Discord Webhook (optional):**
- Config: `DISCORD_WEBHOOK_URL` in `.env` / `.env.example`
- Implementation: Not found in `lib/` or `tools/` — listed as optional feature in `.env.example` only, not yet implemented in code

## Data Storage

**Databases:**
- None — all state in JSON files on disk
- Primary state file: `world-state/campaigns/<name>/world.json` — unified entity graph (WorldGraph, all entities)
- Campaign metadata: `world-state/campaigns/<name>/campaign-overview.json`
- Active campaign pointer: `world-state/active-campaign.txt`

**Vector Store (RAG, optional):**
- ChromaDB `>=0.4.0` (resolved 1.4.1) — persistent local vector database
- Storage path: `world-state/campaigns/<name>/vectors/` per campaign
- Initialized via `lib/rag/vector_store.py` → `CampaignVectorStore`
- Settings: `anonymized_telemetry=False`, `allow_reset=True`
- Collection: `document_chunks` (default)

**File Storage:**
- Local filesystem only
- Document source material: `source-material/` (user-provided PDFs, DOCX, MD)
- Extracted RAG chunks: `world-state/campaigns/<name>/` (extraction temp dirs)
- Session saves (JSON snapshots): `world-state/campaigns/<name>/saves/`
- Session logs: `world-state/campaigns/<name>/session-log.md`
- Module data: `world-state/campaigns/<name>/module-data/<module-id>.json`

**Caching:**
- None (no Redis, Memcached, or similar)
- Model lazy-loading: `lib/rag/embedder.py` holds `_model` in-process memory after first load

## Authentication & Identity

**Auth Provider:**
- None — local CLI tool, no user accounts, no login
- API keys (if any) are sourced from `.env` via `python-dotenv`

## Monitoring & Observability

**Error Tracking:**
- None (no Sentry, Datadog, etc.)

**Logs:**
- Session narrative log: `world-state/campaigns/<name>/session-log.md` (appended by `lib/session_manager.py`)
- Usage stats directory: `world-state/usage/` (present in filesystem)
- Stderr output from tools — no structured logging framework

## CI/CD & Deployment

**Hosting:**
- Local machine only — not deployed to any cloud/server

**CI Pipeline:**
- None detected (no `.github/workflows/`, no CI config files)

## Webhooks & Callbacks

**Incoming:**
- None

**Outgoing:**
- Discord webhook: `DISCORD_WEBHOOK_URL` env var — scaffolded in `.env.example` but not implemented in current codebase

## Embedding Model

**Local (no network):**
- `sentence-transformers` with `all-MiniLM-L6-v2` model (22MB)
- Model source: HuggingFace Hub (downloaded on first use to local cache)
- Initialized in `lib/rag/embedder.py` → `LocalEmbedder`
- HuggingFace progress bars suppressed via `HF_HUB_DISABLE_PROGRESS_BARS=1`

## Environment Configuration

**Required env vars (none are strictly required for basic operation):**
- `DEFAULT_CAMPAIGN_NAME` — default campaign name for new campaigns
- `DEFAULT_STARTING_LOCATION` — starting location for new campaigns

**Optional env vars:**
- `DISCORD_WEBHOOK_URL` — Discord webhook for session logging (not yet implemented)

**Secrets location:**
- `.env` file at project root (gitignored)
- `.env.example` committed as template

---

*Integration audit: 2026-03-29*
