# TODO — DM System

## Unified Inventory Storage (Refactor)
Move inventory data INTO entity files instead of separate module-data JSONs:
- Player inventory → `character.json` (instead of `module-data/inventory-system.json`)
- NPC party inventory → `npcs.json` per-NPC (instead of `module-data/inventory-party.json`)
- Pros: everything in one place, `dm-npc.sh status` shows inventory inline
- Cons: breaks module isolation, but upstream is dead so lib/ is ours

## Upstream Status
Upstream repo maintainer inactive — 0 activity, PRs not reviewed. `lib/` is ours to modify.

## Graph System (Вариант В) — после обкатки Wiki
Эволюция wiki.json в полный граф: единая система заменяющая npcs.json + locations.json + facts.json + wiki.json. Все сущности — nodes с typed edges (связи: sells, knows, located_at, component_of, etc). NPC, локации, предметы, события — один формат. Требует:
- Миграция всех существующих файлов в единый граф
- Переписать все tools (dm-npc, dm-location, dm-note, dm-wiki → dm-entity)
- Визуализация графа (опционально)
- Делать ПОСЛЕ того как wiki.json (вариант Б) покажет себя в игре

## ~~Auto-Combat in dm-roll.sh~~ ✅ DONE
- `--target "creature"` → weapon from character.json + AC from wiki + auto-damage on hit
- `--defend --from "creature"` → creature attack_bonus+damage from wiki + player AC from character.json
- Creatures in wiki.json as type `creature` with mechanics: hp, ac, attack_bonus, damage
- Crits double damage dice. Fumbles skip damage

## Saves as Structured Format (like skills)
- Convert saves from flat `{"инт": 7}` to `{"инт": {"total": 7, "breakdown": {"INT": 4, "proficiency": 3}}}`
- Store save proficiency list separately (which saves are proficient)
- Auto-calculate: stat mod + proficiency + equipment bonuses
- Equipment bonuses from items (Cloak of Protection +1, Ring of WIS save +2)
- `dm-roll.sh --save` reads breakdown, not just total
- Update on level up automatically when proficiency changes

## Auto-DC-Mod from Inventory
- `--skill "алхимия"` should check if items granting dc_mod are in inventory (via wiki `use.dc_mod` field)
- If item not in inventory → dc_mod doesn't apply
- Currently dc_mod is hardcoded in character.json skills — should be dynamic

## World Travel
- Encounter auto-spawn — engine rolls category but DM narrates manually. Need auto-generate NPC/monster with stats
