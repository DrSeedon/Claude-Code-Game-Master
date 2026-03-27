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

## Recommended Module Pairing

Mass combat works standalone, but pairs well with **firearms-combat** module.

| With firearms-combat | Without firearms-combat |
|---------------------|------------------------|
| PEN/PROT values come from `firearms-combat.json` weapon/armor tables | Set PEN/PROT manually per template |
| PC uses firearms-combat engine (ammo, fire modes) | PC uses standard D&D attacks |
| NPC-vs-NPC uses mass-combat engine | All combat uses mass-combat engine |
| Consistent lethality model across both systems | Self-contained PEN/PROT within mass-combat |

If both modules are active, keep PEN/PROT values **consistent** between `firearms-combat.json` (weapon penetration, armor protection) and `mass-combat.json` (unit pen/prot). A unit armed with a Longbow (PEN 2 in firearms-combat) should have `"pen": 2` in its mass-combat template.

---

## Template Format

### Standard Unit

```json
"TemplateID": {
  "name": "Human-readable name",
  "ac": 13,
  "hp": 15,
  "atk": 4,
  "dmg": "1d8+2",
  "pen": 3,
  "prot": 2,
  "targeting": "random",
  "notes": "Short description"
}
```

### AOE Unit (blast mode — one damage roll, all targets)

```json
"HeavyWeapon": {
  "name": "Catapult Crew",
  "ac": 14,
  "hp": 40,
  "atk": 5,
  "dmg": "3d6",
  "pen": 5,
  "prot": 3,
  "targeting": "aoe",
  "aoe_save_type": "DEX",
  "aoe_save_dc": 14,
  "aoe_targets": 4,
  "aoe_mode": "blast",
  "notes": "Splash damage, saves for half"
}
```

### AOE Unit (spray mode — individual rolls per target)

```json
"VolleyArcher": {
  "name": "Volley Archer",
  "ac": 14,
  "hp": 35,
  "atk": 5,
  "dmg": "2d6+2",
  "pen": 3,
  "prot": 3,
  "targeting": "aoe",
  "aoe_save_type": "DEX",
  "aoe_save_dc": 13,
  "aoe_targets": 3,
  "aoe_mode": "spray",
  "notes": "Rain of arrows, each target rolled individually"
}
```

### Melee Unit

```json
"Beast": {
  "name": "War Hound",
  "ac": 12,
  "hp": 10,
  "atk": 4,
  "dmg": "1d6+2",
  "pen": 0,
  "prot": 0,
  "range": "melee",
  "targeting": "random",
  "notes": "Must move into group before attacking"
}
```

Melee units can ONLY attack targets in their own group. Use `move` command to reposition them first. They skip their attack on the turn they move.

---

## Required Fields

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `name` | string | yes | — | Display name |
| `ac` | int | yes | — | Armor class |
| `hp` | int | yes | — | Hit points |
| `atk` | int | yes | — | Attack bonus |
| `dmg` | string | yes | — | Damage dice (e.g. "1d8+2") |
| `targeting` | string | yes | — | `random`, `aimed`, or `aoe` |
| `pen` | int | no | 0 | Weapon penetration |
| `prot` | int | no | 0 | Armor protection |
| `range` | string | no | `"ranged"` | `"ranged"`, `"melee"`, or `"both"` |
| `weight` | int | no | 1 | Targeting priority (higher = more likely targeted) |
| `notes` | string | no | — | DM reference |

### AOE-only fields

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `aoe_save_type` | string | yes (aoe) | — | Save type: `DEX`, `CON`, `WIS`, etc. |
| `aoe_save_dc` | int | yes (aoe) | — | Save DC |
| `aoe_targets` | int | yes (aoe) | — | Max targets per attack |
| `aoe_mode` | string | no | `"blast"` | `"blast"` (one roll, all targets) or `"spray"` (individual rolls) |

---

## PEN/PROT — Armor Penetration

Every unit can have `pen` (weapon penetration) and `prot` (armor protection). Both default to 0.

### Damage Scaling

| Condition | Damage | Tag |
|-----------|--------|-----|
| PEN > PROT | 100% (full) | `[FULL]` |
| PROT/2 < PEN ≤ PROT | 50% (half) | `[HALF]` |
| PEN ≤ PROT/2 | 25% (quarter) | `[QUARTER]` |

Minimum 1 damage on hit. If both PEN and PROT are 0 → full damage (legacy compatibility).

### PEN/PROT Scale

| PEN | Weapon class | Examples |
|-----|-------------|---------|
| 0 | Unarmed / claws / improvised | Fists, teeth, thrown rocks |
| 1 | Light blades, shortbow | Dagger, shortbow, sling |
| 2 | Standard weapons | Shortsword, longbow, handaxe |
| 3 | Military weapons | Longsword, war pick, heavy crossbow |
| 4 | Heavy weapons, marksman | Greataxe, lance, sniper crossbow |
| 5 | Siege / armor-piercing | Ballista bolt, siege hammer, magical piercing |

| PROT | Armor class | Examples |
|------|------------|---------|
| 0 | Unarmored | Civilian clothes, bare hide |
| 1 | Light cover | Thick robes, padded armor |
| 2 | Light armor | Leather armor, studded leather |
| 3 | Medium armor | Chain mail, breastplate |
| 4 | Heavy armor | Half plate, full plate |
| 5 | Exceptional armor | Enchanted plate, dragon-scale armor |
| 6 | Fortress | Stone walls, iron plating, siege fortification |

---

## Stat Guidelines

### Quick Scaling

- **Fodder** (conscripts, skeletons, goblins): AC 11-13, HP 5-15, ATK +3, DMG 1d6, PEN 0-1, PROT 0-1
- **Regular** (soldiers, trained militia): AC 13-15, HP 15-30, ATK +4-5, DMG 1d8+2, PEN 2-3, PROT 2-3
- **Elite** (veterans, knights, alpha predators): AC 15-17, HP 30-60, ATK +5-7, DMG 1d10+3, PEN 3-4, PROT 3-5
- **Boss** (commanders, monsters): AC 16-19, HP 60-120, ATK +7-9, DMG 2d10+5, PEN 4-5, PROT 4-6
- **Vehicle/Siege**: AC 17-20, HP 50-150, ATK +5-8, DMG 3d10+, targeting=aoe, PEN 5+, PROT 5+

### D&D 5e Reference

| D&D Equivalent | AC | HP | ATK | Damage | CR |
|----------------|----|----|-----|--------|----|
| Commoner | 10 | 4 | +2 | 1d4 | 0 |
| Guard | 16 | 11 | +3 | 1d6+1 | 1/8 |
| Bandit | 12 | 11 | +3 | 1d6+1 | 1/8 |
| Thug | 11 | 32 | +4 | 1d6+2 | 1/2 |
| Veteran | 17 | 58 | +5 | 1d8+3 | 3 |
| Assassin | 15 | 78 | +6 | 1d8+3 | 8 |

---

## Targeting Rules

| Type | When to use | Examples |
|------|-------------|---------|
| `random` | Undisciplined or untrained — fire at the crowd | Bandits, conscripts, skeletons, goblins, militia |
| `aimed` | Trained combatants who pick targets | Veterans, knights, snipers, elite archers |
| `aoe` | Area weapons, suppressive fire, magical abilities | Catapults, fire mages, ballistas, ground pounds |

### AOE Modes

| Mode | Mechanic | Best for |
|------|----------|----------|
| `blast` | One damage roll, apply to all targets. Save for half | Explosions, fireball, ground pounds, grenades |
| `spray` | Individual attack roll per target. Save for half | Volley fire, turrets, suppressive arrow rain |

---

## Range Types

| Range | Behavior | Examples |
|-------|----------|---------|
| `ranged` (default) | Can attack any group | Bows, crossbows, thrown weapons, spells |
| `melee` | Can ONLY attack targets in same group. Must `move` first | Claws, fangs, swords, charging beasts |
| `both` | Can do either ranged or melee | Armed humanoids with backup melee |

---

## Combat Rules (optional)

```json
"combat_rules": {
  "cover": "+2 AC while in cover.",
  "surprise_round": "Ambushing side gets one free round.",
  "morale": "When group loses 50%+ units, remaining may flee (WIS DC 12).",
  "siege_crew": "Siege weapon needs at least 1 crew alive to fire.",
  "reinforcements": "Can add units mid-battle with 'add' command."
}
```

Customize per campaign. These are DM reference — the engine does not enforce them automatically.

---

## Example: Fantasy Campaign

```json
{
  "unit_templates": {
    "BanditRaider": {
      "name": "Bandit Raider", "ac": 11, "hp": 8, "atk": 3, "dmg": "1d6",
      "pen": 1, "prot": 0, "targeting": "random",
      "notes": "Shortsword, no armor, cowardly"
    },
    "RoyalGuard": {
      "name": "Royal Guard", "ac": 15, "hp": 22, "atk": 5, "dmg": "1d8+2",
      "pen": 3, "prot": 3, "targeting": "random",
      "notes": "Longsword, chain mail, disciplined"
    },
    "EliteArcher": {
      "name": "Elite Archer", "ac": 14, "hp": 20, "atk": 7, "dmg": "2d8+3",
      "pen": 4, "prot": 2, "targeting": "aimed", "weight": 1,
      "notes": "Heavy crossbow, priority — high-value targets"
    },
    "VolleyArcher": {
      "name": "Volley Archer", "ac": 14, "hp": 35, "atk": 5, "dmg": "2d6+2",
      "pen": 3, "prot": 3, "targeting": "aoe",
      "aoe_save_type": "DEX", "aoe_save_dc": 13, "aoe_targets": 3,
      "aoe_mode": "spray",
      "notes": "Rain of arrows, suppressive fire"
    },
    "GoblinBerserker": {
      "name": "Goblin Berserker", "ac": 14, "hp": 25, "atk": 5, "dmg": "2d6+2",
      "pen": 2, "prot": 1, "range": "melee", "targeting": "random",
      "notes": "Leaping attacker, fast, melee only"
    },
    "Necromancer": {
      "name": "Necromancer", "ac": 13, "hp": 60, "atk": 6, "dmg": "3d6",
      "pen": 0, "prot": 1, "targeting": "aoe",
      "aoe_save_type": "WIS", "aoe_save_dc": 15, "aoe_targets": 4,
      "aoe_mode": "blast",
      "notes": "Fear wave, bypasses physical armor"
    },
    "Knight": {
      "name": "Knight", "ac": 18, "hp": 52, "atk": 5, "dmg": "1d10+3",
      "pen": 2, "prot": 4, "range": "melee", "targeting": "aimed",
      "notes": "Heavy armor, longsword"
    },
    "Catapult": {
      "name": "Catapult", "ac": 15, "hp": 80, "atk": 5, "dmg": "4d10",
      "pen": 5, "prot": 3, "targeting": "aoe",
      "aoe_save_type": "DEX", "aoe_save_dc": 15, "aoe_targets": 4,
      "aoe_mode": "blast",
      "notes": "Siege weapon, splash"
    }
  },
  "combat_rules": {
    "cover": "+2 AC while in cover.",
    "surprise_round": "Ambushing side gets one free round.",
    "morale": "When group loses 50%+ units, remaining may flee (WIS DC 12).",
    "siege_crew": "Siege weapon needs at least 1 crew alive to fire.",
    "magic_resistance": "WIS save vs fear/mind effects. Certain enchanted helms may grant advantage."
  }
}
```

In fantasy settings, PEN/PROT maps to weapon vs armor quality:
- PEN 0 = fists/claws, PEN 1 = dagger/shortbow, PEN 2 = sword/longbow, PEN 3 = greataxe/heavy crossbow, PEN 4 = lance/ballista, PEN 5 = siege
- PROT 0 = unarmored, PROT 1 = padded/robes, PROT 2 = leather, PROT 3 = chain mail, PROT 4 = full plate, PROT 5 = magical plate
