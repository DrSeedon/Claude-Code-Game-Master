---
name: dm-migrate-campaign
description: >
  Diagnose and migrate DM campaigns after engine upgrades. Use when a campaign
  fails inventory/gold/firearms/party location tools, shows empty gear, Gold 0
  with gold in JSON, Weapon not found, or the user says half-graph, migrate
  campaign, adapt old campaign, clone-wars style migration, or worldgraph migration.
when-to-use: >
  migrate campaign, half-graph, inventory-system.json, Gold 0, weapon not found,
  adapt old campaign, dm-migrate, post engine upgrade
compatibility: Requires project tools/, uv, world-state/campaigns/
---

# Migrate campaign (WorldGraph / half-graph)

Do **not** invent a second state store. Prefer tools and small scripts; edit
`world.json` by hand only when no tool covers the field.

Full post-mortem of the clone-wars case:
`docs/migration/half-graph-postmortem.md`.

## 0. Classify the problem first

| Evidence | Kind | Tool |
|----------|------|------|
| Still has `character.json` / `npcs.json` / `locations.json` | **Legacy flat → graph** | `bash tools/dm-migrate-worldgraph.sh <name>` |
| Has `world.json` graph + `module-data/inventory-system.json` and empty `player:active.inventory` | **Half-graph** | `uv run python tools/migrate_half_graph_campaign.py <name>` |
| Only missing one field (e.g. money) | **Surgical fix** | tools / tiny Python, not full migrate |

```bash
CAM=world-state/campaigns/<name>
ls "$CAM"
# flat leftovers?
ls "$CAM"/{character,npcs,locations,facts,plots,consequences}.json 2>/dev/null
# half-graph leftover?
ls "$CAM/module-data/inventory-system.json" 2>/dev/null
# player shape
uv run python -c "
import json; from pathlib import Path
w=json.loads(Path('$CAM/world.json').read_text())
p=w['nodes'].get('player:active',{})
print('inventory', p.get('inventory'))
print('money', (p.get('data') or {}).get('money'), 'gold', (p.get('data') or {}).get('gold'))
print('weapons', sum(1 for n in w['nodes'].values() if n.get('type')=='weapon'))
print('creatures', sum(1 for n in w['nodes'].values() if n.get('type')=='creature'))
"
```

## 1. Backup (mandatory)

```bash
export UV_CACHE_DIR="${UV_CACHE_DIR:-/tmp/dm-uv-cache}"
TS=$(date -u +%Y%m%dT%H%M%SZ)
CAM_NAME=<name>
mkdir -p world-state/backups
cp -a "world-state/campaigns/$CAM_NAME" "world-state/backups/${CAM_NAME}-pre-migrate-$TS"
bash tools/dm-campaign.sh switch "$CAM_NAME"
bash tools/dm-session.sh save "pre-migrate-$TS"
```

Never migrate without a full tree backup under `world-state/backups/`.

## 2. Legacy flat → graph

Only if flat files still exist:

```bash
bash tools/dm-migrate-worldgraph.sh <name> --dry-run
bash tools/dm-migrate-worldgraph.sh <name>
# optional later: --remove-legacy
```

Then still run the **half-graph checklist** below — flat migrator does not embed
module-data inventories or create firearm weapon nodes.

## 3. Half-graph automated path

```bash
uv run python tools/migrate_half_graph_campaign.py <name> --dry-run
uv run python tools/migrate_half_graph_campaign.py <name>
```

The script:

1. `gold` → `money`
2. `stats` → `abilities` + `proficiency_bonus` (firearms attack bonus)
3. Embeds `module-data/inventory-system.json` → `player:active.inventory`
4. Embeds `inventory-party.json` → matching NPC `inventory` (by display name)
5. Creates `weapon:*` / `armor:*` from `firearms-combat.json` + `ammo_type`
6. Sets `data.equipment` when missing
7. Adds default droid/tank `creature` templates (SW-oriented defaults — review for non-SW)
8. Moves party `at` edges to `player_position.current_location`
9. Fills overview: `play_mode`, `cinematic_visuals`, `currency`, normalizes clock in `time_of_day`
10. Upgrades incomplete `fire_modes` to duration/salvo schema
11. Archives inv dumps to `module-data/archived-pre-embed/*.migrated` (does not delete)

**Limits of the script (do manually if needed):**

- Quest text / objective progress vs session-log story drift
- Non-SW ammo labels (override `DEFAULT_AMMO` in script or edit weapon nodes)
- Custom creature roster beyond B1/B2/Droideka/AAT
- Narrative `session-handoff.md` (create if missing)

## 4. Manual half-graph checklist (if you refuse the script)

Work from project root. Prefer `WorldGraph` transaction via a short `uv run python`
snippet or existing `tools/dm-*.sh`.

### 4.1 Money

- Set `player:active.data.money` from `data.gold` if money missing/0.
- Keep `gold` for human audit if you want; tools use **money**.

### 4.2 Inventory embed

- Copy `module-data/inventory-system.json` → node field  
  `player:active.inventory = { "stackable": {...}, "unique": [...] }`
- For each key in `inventory-party.json`, find NPC by **exact name**, set same shape on NPC node.
- Archive old JSON; do not leave two live sources of truth.

### 4.3 Firearms weapons

For each weapon in `module-data/firearms-combat.json` → `weapons`:

```json
"weapon:dc-15a": {
  "type": "weapon",
  "name": "DC-15A",
  "data": {
    "damage": "2d6+2",
    "pen": 3,
    "rpm": 600,
    "magazine": 50,
    "weapon_type": "assault_rifle",
    "ammo_type": "Заряд DC-15A",
    "allowed_fire_modes": ["single", "burst", "full_auto"],
    "source_module": "firearms-combat"
  }
}
```

`ammo_type` **must** match a stackable key in player inventory.

### 4.4 Equipment

Mirror modern sci-fi campaigns (`starcraft-terran-command`):

```json
"equipment": {
  "armor": {"id": "armor:…", "name": "…", "ac": 14, "prot": 4},
  "weapons": [{"id": "weapon:…", "name": "…", "damage": "…", "pen": …, "rpm": …, "magazine": …, "ammo_type": "…"}],
  "items": ["…"]
}
```

Also set `abilities` = copy of `stats` if firearms module is active.

### 4.5 Creatures

Add reusable `creature:*` nodes with `hp`, `ac`, `prot`, `attack_bonus`/`attack`, `damage`, `pen`, `xp`.

### 4.6 Party location

For each `is_party_member` NPC: one `at` edge → current location node.  
Remove stale `at` edges first.

### 4.7 Overview

Ensure: `schema_version`, `play_mode`, `modules` dict, `player_position`,  
`precise_time` / `time_of_day` not confused, optional `currency` / `calendar` / `cinematic_visuals`.

### 4.8 Fire modes config

If `fire_modes.full_auto` lacks `duration_seconds` / salvo caps, replace with the
modern schema used by `starcraft-terran-command` (see migrator constant
`STARCRAFT_STYLE_FIRE_MODES`).

## 5. Verification (must pass before claiming done)

```bash
bash tools/dm-campaign.sh switch <name>
bash tools/dm-player.sh show
bash tools/dm-inventory.sh show player:active
bash tools/dm-npc.sh party
bash tools/dm-location.sh show "<current location name>"
bash tools/dm-roll.sh --skill "Perception" --dc 10
# if firearms module active:
bash modules/firearms-combat/tools/dm-combat.sh resolve \
  --attacker "<PC name>" --weapon "<primary>" --fire-mode single \
  --target "<creature name>" --test
```

Expect: non-zero money when economy exists, non-empty inventory when gear exists,
party `at` current location, resolve returns HIT/MISS without "not found".

## 6. Aftercare

- Write/update `docs/migration/` note if a new failure mode appeared.
- Do **not** commit `world-state/campaigns/**` unless the user asks (often local-only).
- Do commit migrator/skill/docs when the procedure improves.
- If play continues, create `session-handoff.md` after the first post-migrate session.

## 7. Priority of truth

1. This skill + `docs/migration/half-graph-postmortem.md`
2. Compiled `/tmp/dm-rules.md` during play
3. `starcraft-terran-command` as modern firearms reference campaign
4. Stale TODO.md / old README module paths — ignore if they contradict WorldGraph
