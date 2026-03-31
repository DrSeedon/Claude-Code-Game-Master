# Error Handling Audit

## File-by-File Catalog

| File | `except Exception` (broad) | `except:` (bare) | `sys.exit()` | print-based errors | Specific catches | Severity |
|------|---------------------------|-------------------|--------------|-------------------|-----------------|----------|
| `lib/json_ops.py` | 2 | 0 | 6 | 2 (`[ERROR]`) | 2 (JSONDecodeError) | **HIGH** |
| `lib/inventory_manager.py` | 2 | 0 | 0 | 15+ (stderr) | 2 (ValueError) | **HIGH** |
| `lib/content_extractor.py` | 7 | 0 | 0 | 0 | 0 | **HIGH** |
| `lib/agent_extractor.py` | 4 | 0 | 0 | 0 | 1 (JSONDecodeError) | **HIGH** |
| `lib/time_manager.py` | 5 | 0 | 0 | 0 | 1 (ValueError/KeyError) | **HIGH** |
| `lib/dice.py` | 1 | 0 | 0 | 8 (stderr) | 1 (ValueError) | MEDIUM |
| `lib/campaign_manager.py` | 0 | 0 | 0 | 10 (tag_error/warning) | 6 (JSONDecodeError/IOError) | MEDIUM |
| `lib/player_manager.py` | 0 | 0 | 0 | 0 | 8 (JSONDecodeError/IOError/ValueError) | LOW |
| `lib/session_manager.py` | 0 | 0 | 0 | 0 | 3 (JSONDecodeError/IOError/ValueError) | LOW |
| `lib/encounter_engine.py` | 0 | 0 | 1 | 1 (stderr) | 0 | LOW |
| `lib/colors.py` | 0 | 0 | 5 | 0 | 0 | LOW |
| `lib/validators.py` | 0 | 0 | 0 | 1 (`[ERROR]`) | 0 | LOW |
| `lib/calendar.py` | 0 | 0 | 0 | 0 | 1 (JSONDecodeError/IOError) | LOW |
| `lib/currency.py` | 0 | 0 | 0 | 0 | 3 (JSONDecodeError/IOError/ValueError) | LOW |
| `lib/entity_enhancer.py` | 0 | 0 | 0 | 1 (tag_error) | 0 | LOW |
| `lib/entity_manager.py` | 0 | 0 | 0 | 0 | 0 | LOW |
| `lib/extraction_schemas.py` | 0 | 0 | 0 | 1 | 0 | LOW |
| `lib/world_graph.py` | 29 | 0 | 118 | 0 | 0 | **HIGH** |
| **lib/rag/** | | | | | | |
| `lib/rag/__init__.py` | 0 | 0 | 0 | 0 | 2 (ImportError) | LOW |
| `lib/rag/embedder.py` | 0 | 0 | 0 | 0 | 1 (ImportError) | LOW |
| `lib/rag/vector_store.py` | 0 | 0 | 0 | 0 | 1 (ImportError) | LOW |
| `lib/rag/rag_extractor.py` | 0 | 0 | 1 | 0 | 0 | LOW |
| `lib/rag/quote_extractor.py` | 0 | 0 | 1 | 0 | 0 | LOW |
| `lib/rag/semantic_chunker.py` | 0 | 0 | 0 | 0 | 0 | LOW |
| `lib/rag/extraction_queries.py` | 0 | 0 | 0 | 0 | 0 | LOW |

**Totals:** 29 broad `except Exception`, 0 bare `except:`, 118 `sys.exit()`, 38+ print-based errors, 32 specific catches

> **Post-WorldGraph migration note (2026-03-31):** `world_graph.py` (2,481 LOC, 87 methods) absorbed 8 deleted modules: `wiki_manager.py`, `search.py`, `world_stats.py`, `consequence_manager.py`, `npc_manager.py`, `location_manager.py`, `note_manager.py`, `plot_manager.py`. The `sys.exit()` spike (14 → 118) and `except Exception` increase (21 → 29) reflect that `world_graph.py` now contains the CLI entry points and error handling previously spread across those 8 files. `WorldSearcher` (from `search.py`) no longer exists as a class — search is built into `WorldGraph` methods.

## Key Anti-Patterns

### 1. Silent Swallow (`except Exception` + return default)
- **`time_manager.py`** (5 instances): All parsing failures silently return defaults. A corrupt `campaign-overview.json` produces zero diagnostics.
- **`content_extractor.py`** (7 instances): Every extraction step catches `Exception` and continues, masking data corruption.
- **`agent_extractor.py`** (4 instances): JSON extraction failures silently logged, result discarded.

### 2. `sys.exit()` Instead of Exceptions
- **`json_ops.py`** (6 calls), **`colors.py`** (5): CLI entry points use `sys.exit(1)` directly, making these modules untestable as libraries.
- **`encounter_engine.py`** (1), **`rag_extractor.py`** (1), **`quote_extractor.py`** (1): Same pattern.

### 3. Print-to-stderr as Error Reporting
- **`inventory_manager.py`**: 15+ `print(..., file=sys.stderr)` calls with `[ERROR]` prefix — no structured error data.
- **`dice.py`**: 8 `print("Error: ...")` calls to stderr.
- **`campaign_manager.py`**: Mix of `tag_error()` and `tag_warning()` to stdout.

### 4. Inconsistent Error Output
- Some modules use `tag_error()` (colors.py helper) → stdout
- Some use `print(..., file=sys.stderr)` with `[ERROR]` prefix
- Some use plain `print(f"Error: ...")`
- No module raises exceptions for callers to handle

## Proposed Exception Hierarchy

```python
class DMError(Exception):
    """Base exception for all DM system errors."""
    pass

class EntityNotFoundError(DMError):
    """Entity (NPC, location, item, wiki entry) not found."""
    def __init__(self, entity_type: str, name: str):
        self.entity_type = entity_type
        self.name = name
        super().__init__(f"{entity_type} '{name}' not found")

class ValidationError(DMError):
    """Input validation failure (bad args, invalid values, schema mismatch)."""
    def __init__(self, field: str, message: str):
        self.field = field
        super().__init__(f"Validation error on '{field}': {message}")

class ConfigError(DMError):
    """Campaign config missing or corrupt (campaign-overview.json, etc.)."""
    pass

class FileError(DMError):
    """File I/O failure (read/write/missing data files)."""
    def __init__(self, path: str, operation: str, cause: Exception = None):
        self.path = path
        self.operation = operation
        self.cause = cause
        super().__init__(f"Failed to {operation} '{path}'" + (f": {cause}" if cause else ""))

class RAGError(DMError):
    """RAG pipeline failure (embedding, vector store, extraction)."""
    pass

class CurrencyError(ValidationError):
    """Invalid currency string or amount."""
    pass

class DuplicateEntityError(DMError):
    """Attempted to create an entity that already exists."""
    def __init__(self, entity_type: str, name: str):
        self.entity_type = entity_type
        self.name = name
        super().__init__(f"{entity_type} '{name}' already exists")
```

## Modules Needing Most Work (Ranked)

1. **`content_extractor.py`** — 7 broad catches, all silent. Hardest to debug when extraction fails.
2. **`time_manager.py`** — 5 broad catches returning silent defaults. Corrupt time data goes unnoticed.
3. **`inventory_manager.py`** — 2 broad catches + 15 print-based errors. Most user-facing error surface.
4. **`agent_extractor.py`** — 4 broad catches in JSON/LLM extraction pipeline.
5. **`json_ops.py`** — 2 broad catches + 6 sys.exit(). Core utility used by everything.
6. **`dice.py`** — 1 broad catch + 8 print errors. Complex logic with poor error propagation.

## Migration Strategy

1. **Create `lib/exceptions.py`** with the hierarchy above.
2. **Phase 1 — Core utilities:** Refactor `json_ops.py` to raise `FileError`/`ConfigError` instead of `sys.exit()`. All other modules depend on this.
3. **Phase 2 — Data managers:** Refactor `world_graph.py` (118 `sys.exit()` calls, 29 broad catches — highest priority post-migration) and `inventory_manager.py` to raise typed exceptions. Move `sys.exit()` to CLI entry points only.
4. **Phase 3 — Extractors:** Replace broad catches in `content_extractor.py`, `agent_extractor.py` with specific catches + logging.
5. **Phase 4 — CLI boundary:** Each `if __name__ == "__main__"` block catches `DMError` and calls `sys.exit(1)` with formatted output. This is the ONLY place `sys.exit()` should live.
