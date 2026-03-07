# firearms-combat

Automated firearms combat resolver for the DM System. Replaces vanilla D&D 5e attack mechanics when your campaign involves guns, armor vests, and people who fire 30 rounds in 6 seconds.

---

## What Is This

A standalone module that handles modern/sci-fi combat resolution: RPM-based shot count, penetration vs protection damage scaling, progressive full-auto penalties, and automatic XP tracking. The DM calls `dm-combat.sh` directly when firearms combat occurs — there is no middleware, the module does not intercept CORE tools.

**Supported genres:** STALKER, Fallout wasteland, modern military, cyberpunk, zombie survival.

---

## Data Storage

```
world-state/campaigns/<campaign>/
  module-data/
    firearms-combat.json     <-- weapons, fire_modes, armor, enemies
  character.json             <-- subclass, XP (written by resolver)
  campaign-overview.json     <-- no firearms data (migrated out)
```

| Data | Location | Who writes |
|------|----------|------------|
| Weapon definitions | `module-data/firearms-combat.json` -> `weapons` | DM during /new-game |
| Fire mode config | `module-data/firearms-combat.json` -> `fire_modes` | DM during /new-game |
| Armor/enemy presets | `module-data/firearms-combat.json` -> `armor_system`, `enemies_modern` | DM during /new-game |
| Character subclass | `character.json` -> `subclass` | DM during /new-game |
| Character XP | `character.json` -> `xp.current` | Resolver after combat |
| Ammo inventory | `character.json` (via inventory-system) | Resolver after combat |

The template at `templates/modern-firearms-campaign.json` contains a full STALKER preset with all weapons, armor, enemies, subclasses, and survival stats.

---

## CORE D&D 5e vs firearms-combat

| Feature | Vanilla CORE (D&D 5e) | firearms-combat |
|---|---|---|
| Attack roll | 1d20 + bonus | 1d20 + DEX mod + proficiency + subclass |
| Damage per round | One dice roll | One dice roll **per shot** |
| Shots per round | 1 (or Extra Attack) | Derived from weapon RPM over 6 seconds |
| Armor | AC threshold | AC threshold + PROT rating that scales damage |
| Ammunition | Not tracked | Deducted automatically (if inventory-system active) |
| Fire modes | None | `single` / `burst` / `full_auto` |
| Crit mechanics | 2x dice on nat 20 | 2x dice on nat 20, applied per-shot |
| XP tracking | Manual | Auto-written to character file |
| Test mode | None | `--test` flag: show result, write nothing |

---

## How It Works

### RPM -> Shots Per Round

A D&D combat round is 6 seconds. The resolver converts weapon RPM into a realistic shot count:

```
shots_per_round = int((rpm / 60) * 6)
```

Available ammo caps the total. In full_auto, shots per target are capped at `max_shots_per_target` (default 10).

Example: AK-74 at 650 RPM -> 65 shots/round theoretical. With 30 rounds and 3 targets, each target gets 10 shots (capped).

### Penetration vs Protection

Every weapon has a `pen` value. Every armored target has a `prot` value:

| Condition | Damage Applied |
|---|---|
| `pen > prot` | 100% (full damage) |
| `prot/2 < pen <= prot` | 50% (half damage) |
| `pen <= prot/2` | 25% (quarter damage) |

Example: AKM (`pen 4`) vs Mercenary (`prot 3`) -> full damage.
Example: PM Pistol (`pen 1`) vs Heavy Armor (`prot 5`) -> quarter damage.

### Fire Modes

**`single`** — One attack roll, one damage roll. No penalty. Consumes 1 round.

**`burst`** — 3 shots (or less if low ammo), progressive penalty:
- Shot 1: no penalty
- Shot 2: -3 to attack (Sharpshooter: -2)
- Shot 3: -6 to attack (Sharpshooter: -4)

**`full_auto`** — RPM-based shot count, max 10 per target. Progressive penalty:

```
attack_modifier = base_attack + (shot_index * penalty_per_shot)
```

Default penalty: **-3 per shot**. With Sharpshooter subclass: **-2 per shot**.

A Sharpshooter with +8 to attack firing 5 shots: +8, +6, +4, +2, +0.
A normal shooter with +5 firing 5 shots: +5, +2, -1, -4, -7.

### Balance Design

Full auto is deliberately **not** a guaranteed kill:
- Cap at 10 shots/target prevents mag-dumping 30 rounds into one enemy
- Steep penalty means only first 3-5 shots reliably hit
- Single fire is ammo-efficient; full auto is high-risk burst damage
- Monte Carlo sims show AK-74 full_auto kills a Bandit ~59% of the time (was 100% before balance patch)

### Critical Hits

Natural 20 on any shot: double the number of damage dice. The flat bonus is not doubled.

```
Normal:   2d8+2  ->  roll 2d8, add 2
Crit:     4d8+2  ->  roll 4d8, add 2
```

### Attack Bonus Calculation

```
total_attack = DEX_modifier + proficiency_bonus + subclass_bonus
```

Subclass Sharpshooter adds +2 to attack and reduces burst/full-auto penalty from -3 to -2 per shot.

---

## CLI Usage

All combat is resolved through a single command:

```bash
bash .claude/additional/modules/firearms-combat/tools/dm-combat.sh resolve \
  --attacker "Stalker" \
  --weapon "AK-74" \
  --fire-mode full_auto \
  --ammo 90 \
  --targets "Bandit:14:25:3" "Bandit2:12:20:2"
```

Add `--test` to simulate without writing any changes:

```bash
bash .claude/additional/modules/firearms-combat/tools/dm-combat.sh resolve \
  --attacker "Stalker" \
  --weapon "SVD" \
  --fire-mode single \
  --ammo 10 \
  --targets "Mercenary:16:30:3" \
  --test
```

### Arguments

| Argument | Required | Description |
|---|---|---|
| `--attacker` | yes | Character name (must match active character) |
| `--weapon` | yes | Weapon key from `campaign_rules.firearms_system.weapons` |
| `--fire-mode` | yes | `single`, `burst`, or `full_auto` |
| `--ammo` | yes | Rounds available before this combat action |
| `--targets` | yes | One or more targets in `Name:AC:HP:PROT` format |
| `--test` | no | Dry run: print results, do not update character or inventory |

### Target Format

```
Name:AC:HP:Protection
```

Example: `"Bandit:13:20:2"` — enemy named Bandit, AC 13, 20 HP, protection rating 2.

---

## Weapon Configuration

Weapons are defined in `campaign-overview.json` under `campaign_rules.firearms_system.weapons`. The module ships with a ready-to-use template at `templates/modern-firearms-campaign.json`.

### Weapon Fields

| Field | Type | Description |
|---|---|---|
| `damage` | string | Dice notation: `"2d8+3"` |
| `pen` | int | Penetration rating (compared against target `prot`) |
| `rpm` | int | Rounds per minute (determines full-auto shot count) |
| `magazine` | int | Magazine capacity (reference only, not enforced by resolver) |
| `type` | string | `assault_rifle`, `pistol`, `sniper_rifle`, `shotgun` |

### Included Weapon Presets (from template)

| Key | Name | Damage | PEN | RPM | Type |
|---|---|---|---|---|---|
| `AKM` | AKM (7.62x39mm) | 2d8+3 | 4 | 600 | Assault rifle |
| `AK74` | AK-74 (5.45x39mm) | 2d6+2 | 3 | 650 | Assault rifle |
| `M4A1` | M4A1 Carbine (5.56x45mm) | 2d6+2 | 3 | 700 | Assault rifle |
| `SVD` | SVD Dragunov (7.62x54mm) | 2d10+4 | 5 | 30 | Sniper rifle |
| `SPAS12` | SPAS-12 Shotgun (12ga) | 3d8+2 | 2 | 40 | Shotgun |
| `Glock17` | Glock 17 (9x19mm) | 2d4+2 | 2 | 60 | Pistol |
| `PM_Pistol` | PM Pistol (9x18mm) | 2d4+1 | 1 | 30 | Pistol |

### Adding a Custom Weapon

Add a new entry to `campaign-overview.json`:

```json
"campaign_rules": {
  "firearms_system": {
    "weapons": {
      "G36C": {
        "damage": "2d6+2",
        "pen": 3,
        "rpm": 750,
        "magazine": 30,
        "type": "assault_rifle"
      }
    }
  }
}
```

---

## Fire Mode Configuration

Fire modes are configurable per-campaign in `campaign-overview.json`:

```json
"fire_modes": {
  "single": {"attacks": 1, "ammo": 1, "penalty": 0},
  "burst": {
    "penalty_per_shot": -3,
    "penalty_per_shot_sharpshooter": -2
  },
  "full_auto": {
    "penalty_per_shot": -3,
    "penalty_per_shot_sharpshooter": -2,
    "max_shots_per_target": 10
  }
}
```

If `fire_modes` is missing, the resolver uses defaults: -3/-2 penalty, 10 max shots/target.

---

## Enemy Types

From the template, enemies for modern/STALKER campaigns:

| Enemy | AC | HP | PROT | XP |
|---|---|---|---|---|
| Snork (Mutant) | 14 | 25 | 1 | 25 |
| Bandit | 13 | 20 | 2 | 100 |
| Mercenary | 16 | 30 | 3 | 450 |
| Controller | 12 | 60 | 0 | 1800 |

Pass any enemy as a CLI target directly:

```bash
--targets "Snork:14:25:1" "Mercenary:16:30:3"
```

---

## Armor Reference

| Armor | AC Bonus | PROT |
|---|---|---|
| Leather Jacket | +1 | 1 |
| Medium Body Armor | +3 | 3 |
| Heavy Armor Plate | +5 | 5 |
| Powered Exoskeleton | +7 | 7 |

---

## Subclasses

**Sharpshooter (Fighter subclass)**
- +2 to attack bonus on all ranged attacks
- Full-auto/burst penalty: -2 per shot instead of -3
- Quick Reload as bonus action (roleplay rule)

**Sniper (Rogue subclass)**
- Critical hits on 19-20 (roleplay/DM-adjudicated)
- Long Shot: double range without penalty
- Precision Strike: +1d8 on first shot each round

---

## Optional Dependencies

- **inventory-system** — if active, resolver auto-deducts ammo via `dm-inventory.sh`. If not active, prints manual deduction note. This is a soft dependency — the module works fine without it.

---

## Balance Tools

Two matplotlib dashboards in `tools/`:

- `balance-dashboard.py` — 8-chart dashboard: DPA, kill% heatmap, accuracy decay, damage distribution, avg damage, ammo cost, PEN/PROT matrix, verdict panel
- `balance-comparison.py` — side-by-side comparison of different penalty/cap configurations

Run: `uv run python .claude/additional/modules/firearms-combat/tools/balance-dashboard.py`

---

## Architecture Notes

The module imports CORE's `PlayerManager`, `CampaignManager`, and `JsonOperations` directly. CORE has zero knowledge of this module. No middleware is registered — the module does not intercept any CORE tool. The DM (Claude) decides when to call `dm-combat.sh` based on campaign context.

Post-combat: XP is written to character file automatically. Ammo is deducted via inventory-system if available, otherwise printed as manual note.
