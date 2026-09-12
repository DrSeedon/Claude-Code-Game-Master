# Работа над ошибками: half-graph кампании (clone-wars)

**Date:** 2026-07-27  
**Campaign:** `clone-wars`  
**Symptom:** «движок обновился, Star Wars / Clone Wars на старом формате»

## TL;DR

`clone-wars` **уже был WorldGraph schema v2** (`meta.version=2`).  
`tools/dm-migrate-worldgraph.sh` / `legacy_migration.py` **не помогли бы** — flat-файлов (`character.json`, `npcs.json`…) уже нет.

Проблема другая: **half-graph** — граф есть, а gameplay-критичные данные ещё лежат в `module-data/` эпохи inventory-as-module.

## Что ломалось в play

| Симптом | Причина |
|---------|---------|
| `Gold 0` при `data.gold: 250` | Движок читает **`money`**, не `gold` |
| Пустой `dm-inventory.sh show` | Инвентарь только в `module-data/inventory-system.json` |
| Firearms `Weapon not found` | Нет nodes `weapon:*` (только строки + JSON config) |
| Attack bonus кривой | Firearms module читает `abilities`, в player было только `stats` |
| Party «на зоне высадки», сцена в Кирахне | `at` edges не обновлялись после move |
| Fire modes weird / incomplete | `firearms-combat.json` со старым `penalty_per_shot` без `duration_seconds` |
| Автобой без дроидов | 0 `creature` nodes в графе |

Schema migration ≠ content migration. **«world.json есть» ≠ «кампания playable на новом CORE».**

## Backup (сделано)

```
world-state/backups/clone-wars-pre-migrate-20260727T144914Z/   # full tree
world-state/campaigns/clone-wars/saves/20260727-144915-pre-migrate-….json
```

Откат:

```bash
# full tree
rm -rf world-state/campaigns/clone-wars   # NEVER: use trash
# prefer:
trash world-state/campaigns/clone-wars
cp -a world-state/backups/clone-wars-pre-migrate-YYYYMMDDTHHMMSSZ \
      world-state/campaigns/clone-wars
```

или restore из `dm-session.sh` save, если snapshot полный.

## Что сделали

Скрипт: `tools/migrate_half_graph_campaign.py`

1. `gold` → `money`
2. `stats` → `abilities` (+ `proficiency_bonus`)
3. embed `inventory-system.json` → `player:active.inventory`
4. embed `inventory-party.json` → NPC `inventory` (match by name)
5. `weapon:*` + `armor:*` nodes из `firearms-combat.json` + `ammo_type`
6. `data.equipment` (DC-15A, DC-17, Фаза I)
7. creature templates: B1, B2, Droideka, AAT
8. party `at` → `current_location` (Кирахн)
9. overview: `play_mode`, `cinematic_visuals`, `currency` credits, normalize `time_of_day`
10. upgrade `fire_modes` to duration/salvo schema
11. archive legacy inv dumps → `module-data/archived-pre-embed/*.migrated`

## Smoke (passed)

| Check | Result |
|-------|--------|
| `dm-player.sh show` | HP 31/31, **Gold 250**, inventory listed |
| `dm-inventory.sh show player:active` | stackables + uniques, weight |
| `dm-roll.sh --skill Perception --dc 12` | OK |
| `dm-npc.sh party` | 5 members |
| `dm-location.sh show Кирахн` | party `at` edges present |
| `dm-combat.sh resolve … --weapon DC-15A --target "B1 Battle Droid" --test` | HIT, PEN/PROT, ammo would deduct |

## Ошибки процесса (чтобы не повторять)

1. **Путать legacy flat→graph с half-graph.**  
   Если нет `character.json`, не гони `dm-migrate-worldgraph.sh` и не жди чуда.

2. **Не проверять money vs gold.**  
   Любая кампания с только `gold` → Gold 0 в UI/tools.

3. **Не проверять firearms на dry-run.**  
   Config в module-data ≠ weapon nodes. Resolve падает только в бою.

4. **Party location drift.**  
   `player_position.current_location` и `at` edges — два источника; half-migrated часто рассинхрон.

5. **TODO.md врёт.**  
   Старый пункт «inventory → character.json» устарел; правда = embed в WorldGraph node.

6. **Не архивировать module-data.**  
   После embed оставь `archived-pre-embed/` — иначе audit trail мёртв.

## Чеклист: half-graph vs modern

Считать кампанию **modern playable**, если:

- [ ] `player:active.data.money` задан (или currency pipeline ок)
- [ ] `player:active.inventory` (stackable/unique) не пуст, когда у героя есть лут
- [ ] Firearms-кампании: есть `weapon:*` nodes с `damage/pen/rpm/magazine/ammo_type`
- [ ] Есть `data.equipment` или иной documented equip path
- [ ] Есть `creature` templates для типовых врагов
- [ ] Party `at` == `player_position.current_location`
- [ ] Overview: `play_mode`, `schema_version`, modules dict
- [ ] `dm-combat.sh resolve --test` проходит на equipped weapon

## Другие подозрительные кампании

Ищи:

```bash
find world-state/campaigns -name 'inventory-system.json'
```

Если файл есть, а `player:active.inventory` пуст — кандидат на half-graph migrate.

## Batch migrate (2026-07-27)

Backup: `world-state/backups/batch-half-graph-20260727T160641Z/`

| Campaign | Done | Notes |
|----------|------|-------|
| clone-wars | ✅ earlier | full firearms + SW creatures |
| blood-arena | ✅ | money+inventory; D&D currency; no SW pollution |
| pratchett-dungeon | ✅ | money+inventory; D&D currency |
| quest-for-the-holy-ale | ✅ | money only (no module inventory) |
| stalker-zone | ✅ | inv+party+10 weapons+armor; fire_modes; **no** SW droids |
| scp-foundation | ⚠️ partial | money+abilities; **no** weapon nodes (empty firearms config) |
| star-wars-roguelike | ⚠️ shell | empty world; money 0; no location/weapons |
| dragon-quest | ❌ | no `world.json` |

**Migrator guardrails added after dry-run oops:**
- SW creature templates only if weapon names look like DC-15 / E-5 / Z-6
- credits currency only when firearms module on; else D&D cp/sp/gp
- do not invent empty `equipment` or rewrite firearms JSON when module off

## Related

- Skill: `.grok/skills/dm-migrate-campaign/SKILL.md`
- Tool: `tools/migrate_half_graph_campaign.py`
- Flat→graph (другой кейс): `tools/dm-migrate-worldgraph.sh` + `lib/legacy_migration.py`
- Reference modern sci-fi: `starcraft-terran-command`
