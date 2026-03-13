# mass-combat

Individual unit tracking for large-scale battles. Every unit has HP, attacks individually, dies individually.

---

## What Is This

A battle engine that tracks 40+ combatants with individual HP, attack rolls, and death. No grouped damage, no abstract "the squad deals 15 damage". Each B1 droid rolls its own d20. Each clone takes their own hit.

**Works with any genre** — fantasy armies, clone wars, zombie hordes, gang shootouts.

---

## CORE vs mass-combat

| Feature | Vanilla CORE combat | mass-combat |
|---------|-------------------|-------------|
| Unit tracking | Party members only | Every unit on the field |
| NPC combat | "Resolve narratively" | Individual rolls per unit |
| 24 enemies | DM handwaves | 24 individual attack rolls |
| HP tracking | Party only | All combatants, persistent state |
| Cover | Manual AC adjustment | `cover` command, auto +2 AC |
| AOE | Manual calculation | `aoe` with auto saves per target |
| Status | DM memory | HP bars, alive/dead counts |

---

## Architecture

```
tools/dm-mass-combat.sh              <-- bash wrapper (thin)
  └─ mass-combat/lib/mass_combat_engine.py
       └─ lib/campaign_manager.py (CORE — find campaign dir)
```

- Battle state stored in `combat-state.json` inside campaign directory
- Temporary file — deleted when battle ends
- No middleware — standalone tool, does not intercept CORE
- No module-data — no persistent config needed

---

## Quick Start

```bash
MC="bash .claude/additional/modules/mass-combat/tools/dm-mass-combat.sh"

# 1. Start battle
$MC init "Assault on Nabat"

# 2. Add enemies by template (24 droids in one command)
$MC add --faction enemies --group B1-bridge --type B1 --count 6 --ac 13 --hp 7 --atk 3 --dmg "1d6"
$MC add --faction enemies --group B1-patrol --type B1 --count 6 --ac 13 --hp 7 --atk 3 --dmg "1d6"

# 3. Add named heroes
$MC add --faction allies --group alpha --type X --count 1 --ac 14 --hp 17 --atk 6 --dmg "2d6" --names "Hunter"
$MC add --faction allies --group alpha --type X --count 1 --ac 16 --hp 38 --atk 7 --dmg "2d8+4" --names "Ahsoka"

# 4. Fight
$MC next-round
$MC round B1-bridge                              # all 6 droids fire
$MC attack Hunter --targets B1-01 B1-02          # player picks targets
$MC aoe "Thermal Detonator" --targets B1-03 B1-04 B1-05 --damage "3d6" --save-type DEX --save-dc 14
$MC cover alpha                                  # take cover (+2 AC)
$MC status                                       # battlefield overview

# 5. End
$MC end                                          # XP calculation, cleanup
```

---

## Commands

| Command | Purpose | Example |
|---------|---------|---------|
| `init "name"` | Start a battle | `init "Siege of Helm's Deep"` |
| `add` | Add units by template | `add --faction enemies --group orcs --type Orc --count 20 --ac 13 --hp 15 --atk 5 --dmg "1d12+3"` |
| `round <group>` | Group fires (each unit rolls individually) | `round B1-bridge` |
| `attack <name> --targets` | Named unit attacks specific targets | `attack Legolas --targets Orc-01 Orc-02` |
| `aoe <source> --targets --damage` | Area damage with optional saves | `aoe "Fireball" --targets Orc-01 Orc-02 Orc-03 --damage "8d6" --save-type DEX --save-dc 15` |
| `damage <unit> <amount>` | Direct HP damage | `damage Aragorn 8` |
| `heal <unit> <amount>` | Heal HP (caps at max) | `heal Aragorn 10` |
| `kill <unit>` | Instant kill | `kill Orc-15` |
| `cover <group>` | Group takes cover (+2 AC) | `cover defenders` |
| `cover <group> --remove` | Leave cover | `cover defenders --remove` |
| `status` | Show all units with HP bars | `status` |
| `status --group <name>` | Show specific group | `status --group orcs` |
| `next-round` | Advance round counter | |
| `end` | End battle, calculate XP, delete state | |

---

## Round Flags

| Flag | Effect | Used with |
|------|--------|-----------|
| `--count N` | Only N units from group attack | `round` |
| `--target-group X` | Attack specific group only | `round` |
| `--target-faction X` | Attack specific faction only | `round` |
| `--advantage` | Roll 2d20, take higher | `round`, `attack` |
| `--disadvantage` | Roll 2d20, take lower | `round`, `attack` |
| `--atk N` | Override attack bonus | `attack` |
| `--dmg "XdY+Z"` | Override damage dice | `attack` |
| `--save-type X` | Save type for AOE | `aoe` |
| `--save-dc N` | Save DC for AOE | `aoe` |
| `--no-half` | Zero damage on save (not half) | `aoe` |

---

## Output Examples

### Group Attack
```
═══ B1-bridge (6 units) ═══
🎲 B1-01 → Hunter vs AC 14: [12]+3=15 — ✓ HIT → 1d6=[4]=4 dmg (HP→13)
🎲 B1-02 → Rex vs AC 14: [7]+3=10 — ✗ MISS
🎲 B1-03 → Ahsoka vs AC 16: [2]+3=5 — ✗ MISS
🎲 B1-04 → Hunter vs AC 14: [18]+3=21 — ✓ HIT → 1d6=[3]=3 dmg (HP→10)
🎲 B1-05 → Glitch vs AC 14: [1]+3=4 — 💀 FUMBLE
🎲 B1-06 → Rex vs AC 14: [15]+3=18 — ✓ HIT → 1d6=[5]=5 dmg (HP→23)
───
Hits: 3/6 | Damage: 12 | Kills: 0
```

### Status
```
═══ BATTLE: Assault on Nabat | Round 3 ═══

▸ ENEMIES
  B1-bridge: 4/6 alive
    B1-01: HP 7/7 [█████]
    B1-02: 💀
    B1-03: HP 2/7 [█░░░░]
    B1-04: 💀
    B1-05: HP 7/7 [█████]
    B1-06: HP 5/7 [███░░]
    (2 dead)

▸ ALLIES
  alpha: 4/4 alive [COVER +2AC]
    Hunter: HP 10/17 [██░░░] 🛡
    Rex: HP 23/28 [████░] 🛡
    Ahsoka: HP 38/38 [█████] 🛡
    Glitch: HP 18/18 [█████] 🛡

enemies: 4/6 alive
allies: 4/4 alive
```
