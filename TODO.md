# TODO — DM System

## Unified Inventory Storage (Refactor)
Move inventory data INTO entity files instead of separate module-data JSONs:
- Player inventory → `character.json` (instead of `module-data/inventory-system.json`)
- NPC party inventory → `npcs.json` per-NPC (instead of `module-data/inventory-party.json`)
- Pros: everything in one place, `dm-npc.sh status` shows inventory inline
- Cons: breaks module isolation, but upstream is dead so lib/ is ours

## Upstream Status
Upstream repo maintainer inactive — 0 activity, PRs not reviewed. `lib/` is ours to modify.

## World Travel
- Encounter auto-spawn — engine rolls category but DM narrates manually. Need auto-generate NPC/monster with stats
