# firearms-combat

Automated firearms combat resolver for the DM System. Replaces vanilla D&D 5e attack mechanics when a campaign needs physical ammunition expenditure, automatic-fire salvos, and armor penetration.

---

## What Is This

A standalone module that handles modern/sci-fi combat resolution: duration-based RPM expenditure, bounded salvo rolls, penetration vs protection damage scaling, progressive recoil, magazine limits, and automatic XP tracking. The DM calls `dm-combat.sh` directly when firearms combat occurs — there is no middleware, the module does not intercept CORE tools.

**Supported genres:** STALKER, Fallout wasteland, modern military, cyberpunk, zombie survival, military sci-fi.

---

## Data Storage

```
world-state/campaigns/<campaign>/
  world.json                       <-- weapon, armor, creature, and player nodes
  module-data/
    firearms-combat.json           <-- fire mode and combat config
  campaign-overview.json           <-- no firearms reference data
```

| Data | Location | Who writes |
|------|----------|------------|
| Weapon definitions | `world.json` -> `weapon:*` nodes | DM during /new-game |
| Fire mode config | `module-data/firearms-combat.json` -> `fire_modes` | DM during /new-game |
| Armor and creatures | `world.json` -> `armor:*`, `creature:*` nodes | DM during /new-game |
| Character subclass | `world.json` -> `player:active` | DM during /new-game |
| Character XP | `world.json` -> player XP | Resolver after combat |
| Ammo inventory | `world.json` via CORE inventory | Resolver after combat |

The template at `templates/modern-firearms-campaign.json` contains a full STALKER preset with all weapons, armor, enemies, subclasses, and survival stats.

---

## CORE D&D 5e vs firearms-combat

| Feature | Vanilla CORE (D&D 5e) | firearms-combat |
|---|---|---|
| Attack roll | 1d20 + bonus | 1d20 + DEX mod + proficiency + subclass |
| Damage per round | One dice roll | One roll per bounded salvo; damage per bullet hit |
| Shots per action | 1 (or Extra Attack) | Derived from RPM and trigger duration |
| Armor | AC threshold | AC threshold + PROT rating that scales damage |
| Ammunition | Not tracked | Deducted from the active player's WorldGraph inventory |
| Fire modes | None | `single` / `burst` / `full_auto` |
| Crit mechanics | 2x dice on nat 20 | Automatic fire crits only the first bullet in a natural-20 salvo |
| XP tracking | Manual | Auto-written to the active WorldGraph player node |
| Test mode | None | `--test` flag: show result, write nothing |

---

## How It Works

### RPM -> Physical Rounds Fired

A D&D combat round is 6 seconds, but an attack does not hold the trigger for the entire round. Each fire mode defines a trigger duration:

```
rounds_fired = floor((rpm / 60) * duration_seconds)
```

Loaded ammo and magazine capacity cap the result. A burst holds the trigger for 1 second; full auto holds it for 3 seconds by default.

Example: an AK-74 at 650 RPM fires 10 rounds in a one-second burst and empties its 30-round magazine during three-second full auto. A 1,800 RPM weapon fires 30 and 90 rounds respectively.

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

**`burst`** — One second of automatic fire, grouped into at most 3 salvos.

**`full_auto`** — Three seconds of automatic fire, grouped into at most 6 salvos per target and 12 total.

```
attack_modifier = base_attack + (salvo_index * penalty_per_salvo)
```

Default recoil: **-2 per salvo**. With Sharpshooter subclass: **-1 per salvo**.

A Sharpshooter with +8 resolving 5 salvos attacks at +8, +7, +6, +5, +4. A normal shooter with +5 attacks at +5, +3, +1, -1, -3.

### Balance Design

Automatic fire separates physical ammunition from attack rolls:
- Every physical round is consumed, including misses.
- Salvo caps prevent one d20 roll per bullet.
- A hit lands 1 bullet, plus 1 per 5 points above AC, capped at 3 and by rounds in the salvo.
- Single fire is ammo-efficient; automatic fire buys damage potential and suppression with high ammo cost.

### Critical Hits

Natural 20 on a single shot doubles its damage dice. A natural-20 automatic salvo lands up to 2 bullets and doubles only the first bullet's damage dice.

```
Normal:   2d8+2  ->  roll 2d8, add 2
Crit:     4d8+2  ->  roll 4d8, add 2
```

### Attack Bonus Calculation

```
total_attack = DEX_modifier + proficiency_bonus + subclass_bonus
```

Subclass Sharpshooter adds +2 to attack and reduces automatic-fire recoil from -2 to -1 per salvo.

---

## CLI Usage

All combat is resolved through a single command:

```bash
bash .claude/additional/modules/firearms-combat/tools/dm-combat.sh resolve \
  --attacker "Stalker" \
  --weapon "AK-74" \
  --fire-mode full_auto \
  --target "Bandit" \
  --target "Bandit2"
```

Add `--test` to simulate without writing any changes:

```bash
bash .claude/additional/modules/firearms-combat/tools/dm-combat.sh resolve \
  --attacker "Stalker" \
  --weapon "SVD" \
  --fire-mode single \
  --target "Mercenary" \
  --test
```

### Arguments

| Argument | Required | Description |
|---|---|---|
| `--attacker` | yes | Character name (must match active character) |
| `--weapon` | yes | Weapon node name or ID from `world.json` |
| `--fire-mode` | yes | `single`, `burst`, or `full_auto` |
| `--target` | yes | WorldGraph target name or ID; repeat for full auto |
| `--ammo` | no | Explicit ammo override; defaults to player inventory |
| `--targets` | no | Legacy manual targets; accepted only with `--test` |
| `--test` | no | Dry run: print results, do not update character or inventory |

### Target Format

```
Name:AC:HP:Protection
```

Example: `"Bandit:13:20:2"` — enemy named Bandit, AC 13, 20 HP, protection rating 2.

---

## Weapon Configuration

Weapons are `weapon:*` nodes in `world.json`. The module ships with a ready-to-use reference template at `templates/modern-firearms-campaign.json`.

### Weapon Fields

| Field | Type | Description |
|---|---|---|
| `damage` | string | Dice notation: `"2d8+3"` |
| `pen` | int | Penetration rating (compared against target `prot`) |
| `rpm` | int | Rounds per minute used with fire-mode duration |
| `magazine` | int | Loaded magazine capacity enforced per fire action |
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

Add a weapon node through `dm-world.sh`:

```bash
bash tools/dm-world.sh add-node "weapon:g36c" --name "G36C" --type weapon \
  --data '{"damage":"2d6+2","pen":3,"rpm":750,"magazine":30,"weapon_type":"assault_rifle","source_module":"firearms-combat"}'
```

---

## Fire Mode Configuration

Fire modes are configurable per campaign in `module-data/firearms-combat.json`:

```json
"fire_modes": {
  "single": {"attacks": 1, "ammo": 1, "penalty": 0},
  "burst": {
    "duration_seconds": 1,
    "max_salvos_per_target": 3,
    "max_salvos_total": 3,
    "penalty_per_salvo": -2,
    "penalty_per_salvo_sharpshooter": -1,
    "max_hits_per_salvo": 3,
    "hit_margin_per_extra_bullet": 5
  },
  "full_auto": {
    "duration_seconds": 3,
    "max_salvos_per_target": 6,
    "max_salvos_total": 12,
    "penalty_per_salvo": -2,
    "penalty_per_salvo_sharpshooter": -1,
    "max_hits_per_salvo": 3,
    "hit_margin_per_extra_bullet": 5
  }
}
```

Legacy `penalty_per_shot*` keys are read as a compatibility fallback. New campaigns must use the salvo keys above.

---

## Enemy Types

From the template, enemies for modern/STALKER campaigns:

| Enemy | AC | HP | PROT | XP |
|---|---|---|---|---|
| Snork (Mutant) | 14 | 25 | 1 | 25 |
| Bandit | 13 | 20 | 2 | 100 |
| Mercenary | 16 | 30 | 3 | 450 |
| Controller | 12 | 60 | 0 | 1800 |

Persistent targets are resolved directly from WorldGraph:

```bash
--target "Snork" --target "Mercenary"
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
- Automatic-fire recoil: -1 per salvo instead of -2
- Quick Reload as bonus action (roleplay rule)

**Sniper (Rogue subclass)**
- Critical hits on 19-20 (roleplay/DM-adjudicated)
- Long Shot: double range without penalty
- Precision Strike: +1d8 on first shot each round

---

## State Dependencies

- `world.json` must contain `player:active`, the selected `weapon:*` node, and the ammunition stack in the player's inventory. These are canonical CORE WorldGraph records, not a separate module dependency.

---

## Balance Tools

Two matplotlib dashboards in `tools/`:

- `balance-dashboard.py` — 8-chart dashboard: DPA, kill% heatmap, accuracy decay, damage distribution, avg damage, ammo cost, PEN/PROT matrix, verdict panel
- `balance-comparison.py` — side-by-side comparison of different penalty/cap configurations

Run: `uv run python .claude/additional/modules/firearms-combat/tools/balance-dashboard.py`

---

## Architecture Notes

The module uses CORE's `CampaignManager` only to locate the active campaign. Character, weapon, XP, and ammunition state are read and written through `WorldGraph`; module-specific progression logic preserves the existing D&D level thresholds. CORE has zero knowledge of this module. No middleware is registered — the module does not intercept any CORE tool. The DM decides when to call `dm-combat.sh` based on campaign context.

Post-combat, XP and physical rounds fired are persisted to `player:active` in `world.json`. A missing or insufficient ammunition stack is reported as a failed WorldGraph deduction and is never redirected to a legacy file.
