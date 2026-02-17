# Firearms Combat System

**Module:** `firearms-combat`
**Status:** Active
**Version:** 1.0.0

---

## Overview

Automated firearms combat resolution system designed for modern/post-apocalyptic campaigns (STALKER, Fallout, etc.). Provides realistic ballistics simulation with:

- **Fire modes**: Single, burst, full-auto
- **Penetration vs Protection**: Damage scaling based on ammo type vs armor
- **RPM-based mechanics**: Realistic rounds-per-turn calculation
- **Subclass bonuses**: Стрелок (Sharpshooter) reduces accuracy penalties
- **Critical hits**: Natural 20s double dice damage
- **Auto XP tracking**: Awards XP automatically after kills

---

## Activation

**Field-based activation:** Campaign has `campaign_rules.firearms_system` in `campaign-overview.json`.

**Example:**
```json
{
  "campaign_rules": {
    "firearms_system": {
      "weapons": {
        "AK-74": {
          "damage": "2d8+2",
          "pen": 6,
          "rpm": 650,
          "ammo_type": "5.45x39mm"
        }
      },
      "fire_modes": {
        "full_auto": {
          "penalty_per_shot": -2,
          "penalty_per_shot_sharpshooter": -1
        }
      }
    }
  }
}
```

---

## Mechanics

### Fire Mode: Full-Auto

**Rounds per D&D round (6 seconds):**
```
max_rounds = (weapon.rpm / 60) × 6
```

**Example:** AK-74 at 650 RPM → (650 / 60) × 6 = 65 rounds per turn (capped by ammo available).

**Accuracy Penalty:**
- Standard: -2 per shot after first
- Стрелок subclass: -1 per shot after first

**Target Distribution:**
Shots spread evenly across all targets (minimum 1 shot per target).

### Penetration vs Protection

| Condition | Damage Multiplier |
|-----------|-------------------|
| PEN > PROT | 100% (full damage) |
| PEN ≤ PROT/2 | 25% (quarter damage) |
| Otherwise | 50% (half damage) |

**Example:**
- 5.45×39mm PS (PEN 6) vs Light Jacket (PROT 2) → Full damage
- 5.45×39mm PS (PEN 6) vs Military Armor (PROT 8) → Half damage
- 5.45×39mm PS (PEN 6) vs Exoskeleton (PROT 15) → Quarter damage

### Critical Hits

- Natural 20: Hit regardless of AC, **double all damage dice** (then add modifiers)
- Natural 1: Auto-miss

---

## Usage

### CLI Command

```bash
bash tools/dm-combat.sh resolve \
  --attacker "Dmitri" \
  --weapon "AK-74" \
  --fire-mode full_auto \
  --ammo 30 \
  --targets "Snork:12:15:2" "Snork:12:15:2" "Snork:12:15:2"
```

**Target Format:** `Name:AC:HP:PROT`

**Test Mode (dry run):**
```bash
bash tools/dm-combat.sh resolve ... --test
```
Shows results without modifying character.json.

---

## Data Structures

### Weapon Schema

```json
{
  "AK-74": {
    "damage": "2d8+2",
    "pen": 6,
    "rpm": 650,
    "ammo_type": "5.45x39mm"
  }
}
```

### Fire Mode Schema

```json
{
  "full_auto": {
    "penalty_per_shot": -2,
    "penalty_per_shot_sharpshooter": -1
  }
}
```

---

## Character Integration

**Attack Bonus Calculation:**
```
base_attack = DEX_mod + proficiency_bonus + subclass_bonus
```

**Subclass Bonus:**
- Стрелок: +2 to attack rolls (stacks with proficiency)

**XP Auto-Award:**
System awards 25 XP per kill (configurable in future versions).

---

## Output Format

```
================================================================
  FIREARMS COMBAT RESOLVER
================================================================
Weapon: AK-74
Base Attack: +7 (Стрелок subclass)
Shots Fired: 30
Ammo Remaining: 0

----------------------------------------------------------------
TARGET RESULTS:
----------------------------------------------------------------

Snork (AC 12, HP 15, PROT 2)
  Shots: 10 | Hits: 7 (including 1 CRITS!)

  Shot #1: ✓ HIT (14+7=21 vs AC 12)
    Damage: 2d8+2 = 12 raw → PEN 6 vs PROT 2 = FULL → 12 HP
  Shot #2: ⚔ CRIT! (20+5=25 vs AC 12)
    Damage: 4d8+2 = 22 raw → PEN 6 vs PROT 2 = FULL → 22 HP
  ...

  Total Damage Dealt: 68 HP
  Status: 💀 KILLED (overkill: -53)

----------------------------------------------------------------
SUMMARY:
----------------------------------------------------------------
Total Damage: 175 HP
Enemies Killed: 3/3
XP Gained: +75
================================================================
```

---

## DM Guidance

### When to Use

- Combat with firearms (modern, sci-fi, post-apocalyptic)
- Realistic ballistics matter (ammo types, armor penetration)
- Multiple-target engagements
- High RPM weapons (SMGs, assault rifles, machine guns)

### When NOT to Use

- Medieval/fantasy campaigns
- Single-shot weapons (better handled manually)
- Narrative-first combat (abstract outcomes)

### Tactical Considerations

**Full-auto burst discipline:**
- First 3 shots most accurate (-0, -2, -4 penalty)
- Spray mode: Divide fire among multiple targets
- Focus fire: All rounds on one target for maximum kill probability

**Armor counters:**
- Armor-piercing rounds (high PEN) vs armored enemies
- Hollow-point rounds (low PEN, high damage) vs unarmored

**Subclass value:**
- Стрелок halves accuracy penalty (-1 vs -2)
- At 10 shots: Standard = -18 total penalty, Стрелок = -9 penalty
- 2-3x more hits with sustained fire

---

## Integration with CORE

**Dependencies:**
- `lib/player_manager.py` — XP modification
- `lib/json_ops.py` — Campaign data access
- `lib/campaign_manager.py` — Active campaign detection

**CORE Ignorance:**
CORE has no knowledge of this module. Module reaches into CORE to use its managers.

**Tool Replacement:**
CORE's `tools/dm-combat.sh` is a passthrough wrapper. When firearms system is active, it calls module's resolver.

---

## Future Enhancements

- [ ] Single-shot and burst fire modes
- [ ] Configurable XP per enemy type (read from campaign_rules)
- [ ] Ammo inventory auto-deduction
- [ ] Weapon jamming/malfunction mechanics
- [ ] Suppression and morale effects
- [ ] Cover/concealment mechanics
- [ ] Range penalties
- [ ] Enemy stat templates in campaign_rules

---

## See Also

- **CORE Combat Rules:** `CLAUDE.md` (melee/magic combat)
- **Module Manifest:** `module.json`
- **Test Suite:** `tests/test_firearms_resolver.py`
