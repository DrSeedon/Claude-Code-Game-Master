# Mass Combat — Creation Rules

How to create unit templates for a new campaign.

---

## Where Templates Live

`world-state/campaigns/<campaign>/module-data/mass-combat.json`

```json
{
  "unit_templates": { ... },
  "targeting_rules": { ... },
  "combat_rules": { ... }
}
```

---

## Adding a Unit Template

Each template in `unit_templates`:

```json
"TemplateID": {
  "name": "Human-readable name",
  "ac": 13,
  "hp": 15,
  "atk": 4,
  "dmg": "1d8+2",
  "targeting": "random|aimed|aoe",
  "notes": "Short description"
}
```

### AOE units need extra fields:

```json
"Artillery": {
  "name": "Siege Cannon",
  "ac": 16,
  "hp": 60,
  "atk": 5,
  "dmg": "4d10",
  "targeting": "aoe",
  "aoe_save_type": "DEX",
  "aoe_save_dc": 15,
  "aoe_targets": 4,
  "notes": "Stationary, splash damage"
}
```

---

## Stat Guidelines

Use D&D 5e NPC stat blocks as reference:

| D&D Reference | AC | HP | ATK | Damage | CR |
|---------------|----|----|-----|--------|----|
| Commoner | 10 | 4 | +2 | 1d4 | 0 |
| Guard | 16 | 11 | +3 | 1d6+1 | 1/8 |
| Bandit | 12 | 11 | +3 | 1d6+1 | 1/8 |
| Thug | 11 | 32 | +4 | 1d6+2 | 1/2 |
| Veteran | 17 | 58 | +5 | 1d8+3 | 3 |
| Knight | 18 | 52 | +5 | 1d10+3 | 3 |
| Assassin | 15 | 78 | +6 | 1d8+3 | 8 |

### Quick Scaling

- **Fodder** (goblins, B1 droids, zombies): AC 11-13, HP 5-10, ATK +3, DMG 1d6
- **Regular** (guards, clones, bandits): AC 13-15, HP 15-25, ATK +4-5, DMG 1d8+2 or 2d6
- **Elite** (veterans, commandos): AC 15-17, HP 30-60, ATK +5-7, DMG 1d10+3 or 2d8
- **Boss** (commanders, champions): AC 16-19, HP 60-120, ATK +7-9, DMG 2d10+5
- **Vehicle/Turret**: AC 17-20, HP 50-150, ATK +5-8, DMG 3d10+, targeting=aoe

---

## Targeting Rules

| Type | When to use | Examples |
|------|-------------|---------|
| `random` | Dumb or undisciplined units that shoot in the general direction | B1 droids, zombies, militia, beasts, swarms |
| `aimed` | Trained combatants who pick their targets | Clone troopers, veterans, rangers, assassins, player characters |
| `aoe` | Area-effect weapons that hit a zone | Turrets, cannons, grenades, dragon breath, artillery, heavy repeaters |

---

## Combat Rules (optional)

```json
"combat_rules": {
  "cover": "+2 AC while in cover.",
  "surprise_round": "Ambushing side gets one free round.",
  "morale": "When group loses 50%+ units, remaining may flee (WIS DC 12).",
  "turret_crew": "Turret needs at least 1 crew alive to fire.",
  "reinforcements": "Can add units mid-battle with 'add' command."
}
```

Customize per campaign. These are DM reference — the engine does not enforce them automatically.

---

## Example: Fantasy Campaign

```json
{
  "unit_templates": {
    "Goblin": {"name": "Goblin", "ac": 13, "hp": 7, "atk": 4, "dmg": "1d6+2", "targeting": "random", "notes": "Nimble, cowardly"},
    "Orc": {"name": "Orc Warrior", "ac": 13, "hp": 15, "atk": 5, "dmg": "1d12+3", "targeting": "random", "notes": "Aggressive, greataxe"},
    "OrcChief": {"name": "Orc War Chief", "ac": 16, "hp": 93, "atk": 6, "dmg": "1d12+4", "targeting": "aimed", "notes": "Battle Cry ability"},
    "Skeleton": {"name": "Skeleton", "ac": 13, "hp": 13, "atk": 4, "dmg": "1d6+2", "targeting": "random", "notes": "Vulnerable to bludgeoning"},
    "Ballista": {"name": "Ballista", "ac": 15, "hp": 50, "atk": 6, "dmg": "3d10", "targeting": "aimed", "notes": "Stationary, single target"},
    "Catapult": {"name": "Catapult", "ac": 15, "hp": 80, "atk": 5, "dmg": "4d10", "targeting": "aoe", "aoe_save_type": "DEX", "aoe_save_dc": 15, "aoe_targets": 4, "notes": "Siege weapon, splash"}
  }
}
```
