# Technology Stack

**Analysis Date:** 2026-03-28

## Languages

**Primary:**
- Python 3.11+ — All core logic in `lib/`, module libs in `.claude/additional/modules/*/lib/`
- Bash — All CLI wrappers in `tools/`, module middleware in `.claude/additional/modules/*/middleware/`

**Secondary:**
- JSON — Configuration and state files (`world.json`, `campaign-overview.json`, `module.json`)
- Markdown — DM rules slots in `.claude/additional/dm-slots/`, campaign rules in `campaign-rules.md`

## Runtime

**Environment:**
- Python 3.11+ (target), tested on 3.13.7
- macOS and Linux (POSIX) — `classifiers` explicitly lists both

**Package Manager:**
- `uv` 0.9.28 — mandatory for all Python execution (`uv run python`, never `python3` directly)
- Lockfile: `uv.lock` present, revision 3

## Frameworks

**Core:**
- No web framework — pure CLI Python + Bash wrappers
- `setuptools>=68.0.0` + `wheel` — build backend for package `dm-claude`

**Testing:**
- `pytest` — test runner, config in `pyproject.toml` `[tool.pytest.ini_options]`
- `pytest-cov>=7.0.0` — coverage (dev dependency)
- Test root: `tests/` and `.claude/additional/modules/` (both scanned)

**Build/Dev:**
- `black>=23.0.0` — formatter, line length 100, targets py311+py312
- `ruff>=0.1.0` — linter, mirrors black line length, ignores E501
- `mypy>=1.5.0` — type checker, `ignore_missing_imports=true`
- `pre-commit>=3.4.0` — git hooks

## Key Dependencies

**Critical (always installed):**
- `anthropic>=0.76.0` (resolved 0.76.0) — Anthropic SDK; listed as core dep but actual API calls are driven by Claude Code, not direct SDK calls in `lib/`
- `python-dotenv>=1.0.0` (resolved 1.1.1) — env config loading via `.env`
- `requests>=2.31.0` (resolved 2.32.4) — HTTP; used by `features/dnd-api/dnd_api_core.py` (via `urllib.request`, not `requests` directly — `requests` available for future/optional use)
- `matplotlib>=3.10.8` (resolved 3.10.8) — map/dashboard rendering in `tools/dm-dashboard` and firearms-combat module Monte Carlo dashboards

**Document parsing:**
- `pdfplumber>=0.11.9` (resolved 0.11.9) — primary PDF extraction in `lib/content_extractor.py`
- `pypdf2>=3.0.1` (resolved 3.0.1) — fallback PDF extraction in `lib/content_extractor.py`
- `python-docx>=1.2.0` (resolved 1.2.0) — Word document extraction in `lib/content_extractor.py`

**Optional — Voice (`dm-claude[voice]`):**
- `elevenlabs>=2.8.1` (resolved 2.8.1) — TTS voice output

**Optional — RAG (`dm-claude[rag]`):**
- `sentence-transformers>=2.2.0` (resolved 5.2.2) — local embeddings in `lib/rag/embedder.py`, model `all-MiniLM-L6-v2`
- `chromadb>=0.4.0` (resolved 1.4.1) — vector store in `lib/rag/vector_store.py`, persistent per-campaign in `world-state/campaigns/<name>/vectors/`

**Not in pyproject but used by modules:**
- `pygame` — optional, `world-travel` module GUI map (`dm-map.sh --gui`), not in lockfile (install separately)

**System tools (external, not Python):**
- `jq` — JSON processor used in `tools/dm-extract.sh` for metadata parsing
- `uv` — Python runtime manager, installed by `install.sh`

## Configuration

**Environment:**
- `.env` file at project root (`.env.example` present as template)
- Key config: `DEFAULT_CAMPAIGN_NAME`, `DEFAULT_STARTING_LOCATION`, optional `DISCORD_WEBHOOK_URL`
- Loaded via `python-dotenv` at runtime

**Build:**
- `pyproject.toml` — single source of truth for project metadata, dependencies, tool config
- `uv.lock` — pinned dependency tree

**Campaign config:**
- `world-state/campaigns/<name>/campaign-overview.json` — active campaign metadata (time, date, calendar, modules list, currency, narrator style, genre)
- `world-state/active-campaign.txt` — pointer to active campaign name

## Platform Requirements

**Development:**
- Python 3.11+, `uv`, `jq`, Bash (zsh/bash)
- macOS or Linux (POSIX)
- `install.sh` handles bootstrapping: Homebrew (macOS), Python, uv, jq, Claude Code (npm)

**Production:**
- Same as dev — this is a local CLI tool, no server deployment
- Claude Code (npm package) required for AI-driven DM session gameplay

---

*Stack analysis: 2026-03-28*
