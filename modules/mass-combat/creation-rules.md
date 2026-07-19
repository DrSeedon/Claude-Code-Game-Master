# Mass Combat — Creation Rules

Create reusable unit templates as `creature` nodes in `world.json`. Store only
module configuration in `module-data/mass-combat.json`.

## Template Schema

```json
{
  "ac": 13,
  "hp": 15,
  "atk": 4,
  "dmg": "1d8+2",
  "range": "ranged",
  "targeting": "random",
  "weight": 1,
  "notes": "Short tactical description",
  "source_module": "mass-combat",
  "mass_combat_template": true
}
```

Required fields:

| Field | Type | Meaning |
|---|---:|---|
| `ac` | int | Armor Class |
| `hp` | int | HP per individual unit |
| `atk` | int | Attack bonus |
| `dmg` | string | Damage dice notation |
| `source_module` | string | `mass-combat` |
| `mass_combat_template` | bool | `true` |

Optional fields:

| Field | Type | Default | Meaning |
|---|---:|---:|---|
| `range` | string | `ranged` | `melee`, `ranged`, or `both` |
| `targeting` | string | `random` | `random`, `aimed`, or `aoe` |
| `weight` | int | `1` | Relative chance to be targeted |
| `notes` | string | empty | Tactical description |
| `crewed` | bool | `false` | Requires living crew in the same group |
| `combat_profile` | object | absent | Opaque active-provider data |

Mass combat does not define the contents of `combat_profile`. Populate it only
when the compiled resolved profile provides an exact schema.

## AOE Fields

```json
{
  "targeting": "aoe",
  "aoe_save_type": "DEX",
  "aoe_save_dc": 14,
  "aoe_targets": 4,
  "aoe_mode": "blast"
}
```

- `blast` rolls damage once and applies it to selected targets.
- `spray` rolls damage independently for each selected target.

## Suggested Vanilla D&D Tiers

| Tier | AC | HP | ATK | Damage |
|---|---:|---:|---:|---|
| Fodder | 11–13 | 5–15 | +3 | `1d6` |
| Regular | 13–15 | 15–30 | +4 to +5 | `1d8+2` |
| Elite | 15–17 | 30–60 | +5 to +7 | `1d10+3` |
| Boss | 16–19 | 60–120 | +7 to +9 | `2d10+5` |
| Vehicle or siege unit | 17–20 | 50–150 | +5 to +8 | `3d10` or higher |

## WorldGraph Examples

```bash
bash tools/dm-world.sh add-node "creature:militia-recruit" \
  --name "Militia Recruit" --type creature \
  --data '{"ac":11,"hp":8,"atk":3,"dmg":"1d6","range":"melee","targeting":"random","notes":"Poorly trained","source_module":"mass-combat","mass_combat_template":true}'

bash tools/dm-world.sh add-node "creature:royal-guard" \
  --name "Royal Guard" --type creature \
  --data '{"ac":15,"hp":22,"atk":5,"dmg":"1d8+2","range":"melee","targeting":"random","notes":"Disciplined heavy infantry","source_module":"mass-combat","mass_combat_template":true}'

bash tools/dm-world.sh add-node "creature:catapult" \
  --name "Catapult" --type creature \
  --data '{"ac":15,"hp":80,"atk":5,"dmg":"4d10","range":"ranged","targeting":"aoe","aoe_save_type":"DEX","aoe_save_dc":15,"aoe_targets":4,"aoe_mode":"blast","crewed":true,"notes":"Siege engine","source_module":"mass-combat","mass_combat_template":true}'
```

## Validation

After creation:

```bash
bash modules/mass-combat/tools/dm-mass-combat.sh templates
bash modules/mass-combat/tools/dm-mass-combat.sh init "Template Check"
bash modules/mass-combat/tools/dm-mass-combat.sh add \
  --faction allies --group Test --template royal-guard --count 2
bash modules/mass-combat/tools/dm-mass-combat.sh status
bash modules/mass-combat/tools/dm-mass-combat.sh end
```
