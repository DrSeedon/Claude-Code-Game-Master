# TODO — DM System

## Unified Inventory Storage (Refactor)
Move inventory data INTO entity files instead of separate module-data JSONs:
- Player inventory → `character.json` (instead of `module-data/inventory-system.json`)
- NPC party inventory → `npcs.json` per-NPC (instead of `module-data/inventory-party.json`)
- Pros: everything in one place, `dm-npc.sh status` shows inventory inline
- Cons: breaks module isolation, but upstream is dead so lib/ is ours

## Graph System — long-term
Evolve wiki.json into a full entity graph replacing npcs.json + locations.json + facts.json + wiki.json. All entities as nodes with typed edges (sells, knows, located_at, component_of, etc). Do AFTER wiki.json is battle-tested in multiple campaigns.

## Auto-DC-Mod from Inventory (deferred)
- `--skill "alchemy"` should check if items granting dc_mod are in inventory (via wiki)
- If item not in inventory → dc_mod doesn't apply
- Currently dc_mod is hardcoded in character.json skills — should be dynamic
- Do when we actually lose an item with a bonus

## CORE Encounter System on Move
Configurable encounter engine triggered by `dm-session.sh move --elapsed N`. Settings per campaign in `campaign-overview.json`:
- `encounter_chance`: base % per hour of travel (e.g. 15 = 15% per hour)
- `encounter_types`: weighted table of categories (bandits: 30, beasts: 25, undead: 20, merchants: 15, patrol: 10)
- `encounter_frequency`: min hours between encounters (e.g. 2 = max 1 encounter per 2 hours)
- `encounters_enabled`: true/false toggle
- On trigger: roll category from weighted table, create creature from wiki (if exists) or print type for DM to narrate
- Auto-lookup creature stats from wiki for instant combat setup
- Works with any campaign/setting — zombie hordes, monster hunters, road bandits
