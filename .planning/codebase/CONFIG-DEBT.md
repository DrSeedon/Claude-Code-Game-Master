# Configuration Debt Catalog

> Generated: 2026-03-29
> Scope: All `lib/*.py` files
> Total magic values found: ~130 distinct instances across 22 files

## Executive Summary

Hardcoded values are spread across the entire codebase with no centralized configuration. The biggest risks are:
1. **D&D 5e lock-in** -- XP thresholds, proficiency bonus, die sizes, AC defaults are hardcoded, preventing use with other game systems
2. **Duplicated file paths** -- `"active-campaign.txt"`, `"character.json"`, `"wiki.json"` appear in 3+ files each
3. **Campaign-specific defaults baked into code** -- encumbrance, item weights, encounter rates, tone percentages
4. **Display limits scattered everywhere** -- 50+ truncation constants with no consistent strategy

---

## Category 1: XP Thresholds / Level Progression

| File | Line(s) | Value | What It Controls |
|------|---------|-------|------------------|
| `player_manager.py` | 24-45 | `XP_THRESHOLDS = [0, 300, 900, 2700, ...]` | D&D 5e XP per level (20 values) |
| `player_manager.py` | 128, 251, 303 | `level < 20` | Max level cap |
| `dice.py` | 334 | `2 if level < 5 else 3 if level < 9 else ...` | Proficiency bonus by level |
| `dice.py` | 369 | Same chain (truncated at level 9) | Attack proficiency (**BUG: missing levels 13-20**) |
| `dice.py` | 432 | Same chain | Spell attack proficiency |
| `dice.py` | 569 | `8 + spell_mod` | Spell save DC base |

**Risk:** System is locked to D&D 5e. Proficiency bonus is duplicated 3x with one copy buggy.

## Category 2: HP / Health Thresholds

| File | Line(s) | Value | What It Controls |
|------|---------|-------|------------------|
| `player_manager.py` | 358, 368 | `max_hp // 4` | "BLOODIED" threshold (25% HP) |
| `npc_manager.py` | 631 | `hp['max'] // 4` | NPC "[CRITICAL]" HP threshold |
| `colors.py` | 97, 99 | `0.5`, `0.25` | HP bar color breakpoints (green/yellow/red) |
| `inventory_manager.py` | 838, 909 | `0.5`, `0.25` | HP color in status/inventory display |

**Risk:** HP color thresholds duplicated in 3 files. Bloodied threshold hardcoded to 25%.

## Category 3: Similarity Scores / Search Thresholds

| File | Line(s) | Value | What It Controls |
|------|---------|-------|------------------|
| `entity_enhancer.py` | 175 | `0.5` | Fuzzy entity match minimum similarity |
| `entity_enhancer.py` | 305 | `1.5` | RAG passage max distance (skip if exceeded) |
| `wiki_manager.py` | 103-110 | `10, 8, 3, 5` | Search score weights (name/ID/desc/tag) |
| `wiki_manager.py` | 172 | `0.6` | Fuzzy find minimum similarity |

**Risk:** Search quality tuning requires code changes. No way to adjust per-campaign.

## Category 4: File Paths / File Names

Duplicated across multiple files with no single source of truth:

| Filename | Files Using It |
|----------|---------------|
| `"active-campaign.txt"` | `campaign_manager.py`, `dice.py`, `encounter_engine.py` |
| `"campaign-overview.json"` | `player_manager.py`, `encounter_engine.py`, `entity_manager.py` |
| `"character.json"` | `player_manager.py`, `dice.py` |
| `"wiki.json"` | `wiki_manager.py`, `dice.py`, `encounter_engine.py` |
| `"inventory-system.json"` | `inventory_manager.py` |
| `"npcs.json"` | `npc_manager.py` |
| `"locations.json"` | `location_manager.py` |
| `"plots.json"` | `plot_manager.py` |
| `"consequences.json"` | `consequence_manager.py` |
| `"session-log.md"` | `session_manager.py` |
| `"module-data/custom-stats.json"` | `time_manager.py` |

**Risk:** Renaming any file requires hunting through multiple modules. No constants file.

## Category 5: Display Truncation Limits

~50 hardcoded truncation values scattered across 5 files:

| File | Count | Range | Examples |
|------|-------|-------|---------|
| `search.py` | 7 | 60-260 chars | NPC desc (240), location desc (260), trigger (60) |
| `session_manager.py` | 7 | 120-220 chars | Party desc (180), events (120), rules (220) |
| `entity_enhancer.py` | 7 | 100-600 chars | Passage max (600), excerpt (350), dedup key (200) |
| `world_stats.py` | 5 | 3-10 items | NPCs (10), locations (10), plots (5), consequences (3) |
| `plot_manager.py` | 2 | 60 chars | Description truncation |

**Risk:** No consistent truncation strategy. Values seem arbitrary and untested.

## Category 6: Encounter Rates / Dice Defaults

| File | Line(s) | Value | What It Controls |
|------|---------|-------|------------------|
| `encounter_engine.py` | 127 | `15` | Default encounter chance per hour (%) |
| `encounter_engine.py` | 128 | `2` | Minimum hours between encounters |
| `dice.py` | 393, 402 | `'1d4'` | Default damage (no weapon found) |
| `dice.py` | 623 | `'1d6'` | Default creature damage |
| `dice.py` | 548, 631 | `10` | Default AC (creature and player) |
| `npc_manager.py` | 28-29 | `+2`, `'1d6'` | Default party member attack/damage |

**Risk:** Game-system-specific defaults hardcoded. Encounter rates should be per-location.

## Category 7: Validation Limits

| File | Line(s) | Value | What It Controls |
|------|---------|-------|------------------|
| `validators.py` | 25 | `100` | Max name length |
| `validators.py` | 66-67 | `1-100` | Dice count range |
| `validators.py` | 69 | `[4, 6, 8, 10, 12, 20, 100]` | Valid die sizes |
| `wiki_manager.py` | 116 | `5` | Recipe tree max depth |
| `consequence_manager.py` | 41 | `8` | UUID truncation length |

**Risk:** Die sizes locked to D&D standard. Max depth/length limits untested.

## Category 8: Default Campaign Values

| File | Line(s) | Value | What It Controls |
|------|---------|-------|------------------|
| `campaign_manager.py` | 289 | `"Fantasy"` | Default genre |
| `campaign_manager.py` | 291-293 | `horror: 30, comedy: 30, drama: 40` | Default tone mix |
| `campaign_manager.py` | 295 | `"1st of the First Month, Year 1"` | Default start date |
| `campaign_manager.py` | 296 | `"Morning"` | Default time of day |
| `time_manager.py` | 58 | `"08:00"` | Default precise time |
| `npc_manager.py` | 19-34 | `PARTY_MEMBER_DEFAULTS` | Default NPC stats (HP 10, AC 10, all stats 10) |
| `inventory_manager.py` | 64-71 | `DEFAULT_WEIGHTS` | Item weights by category (weapon: 3.0kg, ammo: 0.02kg, etc.) |
| `inventory_manager.py` | 73 | `ENCUMBRANCE_MULTIPLIER = 7` | STR x 7 = carry capacity (kg) |
| `inventory_manager.py` | 75-80 | `ENCUMBRANCE_TIERS` | Load thresholds with speed penalties |
| `inventory_manager.py` | 47-62 | `ITEM_CATEGORIES` | Keyword-based item classification (contains Russian strings) |
| `plot_manager.py` | 521, 523 | `3`, `2` | Stale plot thresholds (sessions) |
| `inventory_manager.py` | 833 | `300` | Fallback XP for next level |

**Risk:** All of these vary by campaign/game-system but require code changes to modify.

## Category 9: Item Categories with Russian Strings

`inventory_manager.py` lines 47-62 contains hardcoded Russian keywords for item classification:

```python
ITEM_CATEGORIES = {
    "ammo": ["arrow", "bolt", "bullet", "стрела", "болт", ...],
    "weapon": ["sword", "axe", "меч", "топор", ...],
    ...
}
```

**Risk:** Language-specific content in code violates module design principles. Should be data-driven from wiki.json or campaign config.

---

## Proposed Centralized Config Strategy

### Tier 1: System Constants (`lib/constants.py`)
Create a single constants file for:
- File name constants (`CAMPAIGN_FILE = "campaign-overview.json"`, etc.)
- ANSI color codes (already in `colors.py`, keep there)
- UUID/format constants

### Tier 2: Game System Config (`campaign-overview.json` -> `"game_system"` section)
Move to campaign config:
- XP thresholds and max level
- Proficiency bonus table
- Valid die sizes
- Default AC, default damage
- Spell save DC formula base

### Tier 3: Display Config (`campaign-overview.json` -> `"display"` section)
Centralize all truncation/limit values:
- HP bar thresholds and width
- Text truncation limits (with sensible grouped defaults)
- List display limits

### Tier 4: Gameplay Tuning (`campaign-overview.json` -> existing sections)
Already partially supported, needs completion:
- Encounter rates (per-location override)
- Encumbrance system (multiplier, tiers, weights)
- Item categories (move to wiki.json or campaign config)
- Stale plot thresholds
- Party member defaults

### Implementation Priority

1. **HIGH** -- `lib/constants.py` for file paths (eliminates duplication, 30 min)
2. **HIGH** -- Fix proficiency bonus bug in `dice.py:369` (5 min)
3. **HIGH** -- Extract `ITEM_CATEGORIES` Russian strings to data file (30 min)
4. **MEDIUM** -- Game system config section in campaign-overview.json (2 hrs)
5. **MEDIUM** -- Centralize display truncation constants (1 hr)
6. **LOW** -- Per-location encounter rate overrides (1 hr)
7. **LOW** -- Full game-system abstraction for non-D&D campaigns (8+ hrs)
