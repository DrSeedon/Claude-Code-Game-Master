# Dependency Injection Assessment

## Current State: How Each Class Creates Dependencies

### Infrastructure Layer (no domain dependencies)

| Class | Dependencies | Creation Method |
|-------|-------------|----------------|
| `JsonOperations` | None (only `pathlib.Path`) | Standalone |
| `Validators` | None | Standalone, stateless |
| `Colors` | None | Standalone, static methods |
| `DiceRoller` | None | Standalone |
| `CampaignManager` | `pathlib.Path` only | Standalone |

### Base Layer

| Class | Dependencies | Creation Method |
|-------|-------------|----------------|
| `EntityManager` | `JsonOperations`, `Validators`, `CampaignManager` | **Direct construction** in `__init__` |

### Manager Layer (EntityManager subclasses)

All of these inherit from `EntityManager` and call `super().__init__()`, which internally constructs `JsonOperations`, `Validators`, and `CampaignManager`:

- `PlayerManager(EntityManager)`
- `SessionManager(EntityManager)`

### Manager Layer (standalone, non-EntityManager)

| Class | Dependencies Created in `__init__` |
|-------|-----------------------------------|
| `TimeManager` | `CampaignManager`, `JsonOperations` |
| `InventoryManager` | `ModuleDataManager` (direct construction) |
| `EntityEnhancer` | `CampaignManager`, `JsonOperations` |
| `AgentExtractor` | `JsonOperations`, `Validators`, `CampaignManager` |

### Content Extraction Layer

| Class | Dependencies |
|-------|-------------|
| `ContentExtractor` | `PDFExtractor`, `MarkdownExtractor`, `DocxExtractor`, `TextExtractor` — all constructed internally |

## Dependency Graph

```
CampaignManager (standalone)
    │
    ▼
EntityManager ──► JsonOperations (standalone)
    │           ► Validators (standalone)
    │           ► CampaignManager
    │
    ├── PlayerManager
    └── SessionManager

TimeManager ──► CampaignManager, JsonOperations
EntityEnhancer ──► CampaignManager, JsonOperations
AgentExtractor ──► JsonOperations, Validators, CampaignManager

InventoryManager ──► ModuleDataManager (direct construction)
                 ──► InventoryManager (self-creates for NPC/target operations)
```

## Key Problems

1. **Every manager constructs its own `CampaignManager` and `JsonOperations`** — identical bootstrap logic duplicated across multiple classes. Each instance independently resolves the active campaign.

2. **No interfaces/protocols** — all dependencies are concrete classes. Testing requires either real filesystem or the `require_active_campaign=False` escape hatch (only on `EntityManager`).

3. **`EntityManager` has two code paths** in `__init__` (testing vs production) controlled by a boolean flag — a code smell that would be eliminated by proper DI.

4. **Standalone managers duplicate EntityManager's pattern** — `TimeManager`, `EntityEnhancer` (and previously `WorldSearcher`, now merged into `world_graph.py`) all repeat the same `CampaignManager` → `get_active_campaign_dir()` → `JsonOperations` bootstrap. Post-WorldGraph migration, search functionality lives in `WorldGraph` directly — no separate `WorldSearcher` class.

## Proposed DI Strategy

### 1. Protocol Interfaces for Key Services

```python
# lib/protocols.py
from typing import Protocol, Optional, Any
from pathlib import Path

class JsonStore(Protocol):
    """Protocol for JSON persistence operations."""
    def load_json(self, filename: str) -> Optional[dict]: ...
    def save_json(self, filename: str, data: dict) -> bool: ...
    def check_exists(self, filename: str, key: str) -> bool: ...
    def update_json(self, filename: str, updates: dict) -> bool: ...
    def get_timestamp(self) -> str: ...

class CampaignResolver(Protocol):
    """Protocol for resolving the active campaign directory."""
    def get_active_campaign_dir(self) -> Optional[Path]: ...
    def get_active(self) -> Optional[str]: ...
```

`JsonOperations` and `CampaignManager` already satisfy these protocols without modification.

### 2. Constructor Injection Pattern

**Before (current — `EntityManager`):**
```python
class EntityManager:
    def __init__(self, world_state_dir=None, require_active_campaign=True):
        if not require_active_campaign and world_state_dir:
            self.campaign_dir = Path(world_state_dir)
            self.json_ops = JsonOperations(str(self.campaign_dir))
            self.validators = Validators()
            self.campaign_mgr = None
        else:
            base_dir = world_state_dir or "world-state"
            self.campaign_mgr = CampaignManager(base_dir)
            active_dir = self.campaign_mgr.get_active_campaign_dir()
            if active_dir is None:
                raise RuntimeError("No active campaign.")
            self.campaign_dir = active_dir
            self.json_ops = JsonOperations(str(active_dir))
            self.validators = Validators()
```

**After (constructor injection):**
```python
class EntityManager:
    def __init__(self, json_store: JsonStore, validators: Validators, campaign_dir: Path):
        self.json_ops = json_store
        self.validators = validators
        self.campaign_dir = campaign_dir
```

### 3. Factory Functions for Default Wiring

Keep backwards compatibility and eliminate bootstrap duplication with a single factory:

```python
# lib/context.py
from pathlib import Path
from json_ops import JsonOperations
from validators import Validators
from campaign_manager import CampaignManager

class CampaignContext:
    """Resolved campaign context — created once, shared by all managers."""

    def __init__(self, campaign_dir: Path, json_ops: JsonOperations,
                 validators: Validators, campaign_mgr: CampaignManager = None):
        self.campaign_dir = campaign_dir
        self.json_ops = json_ops
        self.validators = validators
        self.campaign_mgr = campaign_mgr

def resolve_campaign(world_state_dir: str = "world-state") -> CampaignContext:
    """Resolve the active campaign and return a shared context."""
    mgr = CampaignManager(world_state_dir)
    active_dir = mgr.get_active_campaign_dir()
    if active_dir is None:
        raise RuntimeError("No active campaign. Run /new-game or /import first.")
    return CampaignContext(
        campaign_dir=active_dir,
        json_ops=JsonOperations(str(active_dir)),
        validators=Validators(),
        campaign_mgr=mgr,
    )

def make_player_manager(ctx: CampaignContext = None) -> "PlayerManager":
    ctx = ctx or resolve_campaign()
    return PlayerManager(json_store=ctx.json_ops, validators=ctx.validators,
                         campaign_dir=ctx.campaign_dir)

def make_session_manager(ctx: CampaignContext = None) -> "SessionManager":
    ctx = ctx or resolve_campaign()
    return SessionManager(json_store=ctx.json_ops, validators=ctx.validators,
                          campaign_dir=ctx.campaign_dir)

def make_time_manager(ctx: CampaignContext = None) -> "TimeManager":
    ctx = ctx or resolve_campaign()
    return TimeManager(json_store=ctx.json_ops, campaign_dir=ctx.campaign_dir)
```

CLI entry points (`if __name__ == "__main__"`) call the factory with no arguments (production default). Tests pass a `CampaignContext` with a temp directory and mock/real `JsonOperations` — no filesystem setup, no `require_active_campaign` flag.

### Migration Path

This can be done incrementally, one manager at a time:

1. **Phase 1:** Add `protocols.py` and `context.py` (zero impact on existing code).
2. **Phase 2:** Update `EntityManager.__init__` to accept optional injected deps; if none provided, fall back to current behavior. Subclasses unchanged.
3. **Phase 3:** Convert standalone managers (`TimeManager`, `EntityEnhancer`, etc.) one by one — add injected constructor, update CLI entry point to use factory. Note: `WorldSearcher` was deleted in WorldGraph migration; search is now handled by `WorldGraph` methods directly.
4. **Phase 4:** Remove `require_active_campaign` flag and legacy constructor paths once all tests use injection.

### Impact on Testability

**Current test setup:**
```python
# Must use escape hatch or create real campaign structure
mgr = PlayerManager(world_state_dir=str(tmp_path), require_active_campaign=False)
```

**After DI:**
```python
# Direct, explicit, no filesystem needed for unit tests
json_store = JsonOperations(str(tmp_path))
mgr = PlayerManager(json_store=json_store, validators=Validators(), campaign_dir=tmp_path)
```

### Risk Assessment

- **Low risk:** All changes are additive (new optional params with fallback).
- **No breaking changes** to CLI entry points or bash wrappers — factories handle wiring.
- **Biggest win:** Eliminating duplicate bootstrap sequences and the `require_active_campaign` testing hack.
