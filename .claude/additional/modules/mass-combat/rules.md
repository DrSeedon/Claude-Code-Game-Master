# Mass Combat — DM Rules

Large-scale battle tracker. Every unit has individual HP, attacks individually, dies individually.

---

## Setup (once per battle)

```bash
# 0. Check available templates
bash .claude/additional/modules/mass-combat/tools/dm-mass-combat.sh templates

# 1. Initialize battle
bash .claude/additional/modules/mass-combat/tools/dm-mass-combat.sh init "Battle Name"

# 2. Add units from template (preferred — stats from module-data/mass-combat.json)
bash .claude/additional/modules/mass-combat/tools/dm-mass-combat.sh add \
  --faction enemies --group B1-bridge --template B1 --count 6

# 3. Add named units from template
bash .claude/additional/modules/mass-combat/tools/dm-mass-combat.sh add \
  --faction allies --group clone-alpha --template Clone --count 1 --names "Хантер"

# 4. Add custom units (no template needed)
bash .claude/additional/modules/mass-combat/tools/dm-mass-combat.sh add \
  --faction allies --group heroes --type Jedi --count 1 \
  --ac 16 --hp 38 --atk 7 --dmg "2d8+4" --names "Асока"
```

---

## Round Flow

Each round follows this pattern:

```
1. DM: next-round
2. DM: Enemy groups attack (one 'round' call per group)
3. DM: Ask player for action
4. Player decides: attack / grenade / cover / special ability
5. DM: Execute player action (attack / aoe / cover)
6. DM: Allied NPC groups attack (one 'round' call per group)
7. DM: status → show situation
8. DM: Narrate results
```

---

## Commands

### Group Attack — one group fires at enemy faction
```bash
bash .claude/additional/modules/mass-combat/tools/dm-mass-combat.sh round B1-bridge
bash .claude/additional/modules/mass-combat/tools/dm-mass-combat.sh round B1-bridge --count 4
bash .claude/additional/modules/mass-combat/tools/dm-mass-combat.sh round B1-bridge --target-group clone-alpha
bash .claude/additional/modules/mass-combat/tools/dm-mass-combat.sh round twilek-bravo --advantage
```

### Single Attack — named unit picks targets
```bash
bash .claude/additional/modules/mass-combat/tools/dm-mass-combat.sh attack Хантер --targets B1-01 B1-02
bash .claude/additional/modules/mass-combat/tools/dm-mass-combat.sh attack Асока --targets B1-05 B1-06 --advantage
bash .claude/additional/modules/mass-combat/tools/dm-mass-combat.sh attack Рекс --targets B1-03 --atk 5 --dmg "2d6"
```

### AOE — grenades, explosions, Force abilities
```bash
bash .claude/additional/modules/mass-combat/tools/dm-mass-combat.sh aoe "Thermal Detonator" \
  --targets B1-01 B1-02 B1-03 --damage "3d6" --save-type DEX --save-dc 14

bash .claude/additional/modules/mass-combat/tools/dm-mass-combat.sh aoe "Force Push (Асока)" \
  --targets B1-04 B1-05 --damage "1d8" --save-type STR --save-dc 14
```

### Direct Damage / Heal / Kill
```bash
bash .claude/additional/modules/mass-combat/tools/dm-mass-combat.sh damage Хантер 5
bash .claude/additional/modules/mass-combat/tools/dm-mass-combat.sh heal Рекс 8
bash .claude/additional/modules/mass-combat/tools/dm-mass-combat.sh kill B1-15
```

### Cover
```bash
bash .claude/additional/modules/mass-combat/tools/dm-mass-combat.sh cover clone-alpha
bash .claude/additional/modules/mass-combat/tools/dm-mass-combat.sh cover clone-alpha --remove
```

### Turret Fire (auto-pick targets, no repeats)
```bash
bash .claude/additional/modules/mass-combat/tools/dm-mass-combat.sh turret J1-01 --target-group alpha --targets 3
```

### Move Units Between Groups
```bash
bash .claude/additional/modules/mass-combat/tools/dm-mass-combat.sh move B1-23 B1-24 --to J1-north
bash .claude/additional/modules/mass-combat/tools/dm-mass-combat.sh move Хантер Рекс --to gamma
```

Move = reposition only, units skip their attack this turn (spent action moving).

### Test Mode (preview without saving)
```bash
bash .claude/additional/modules/mass-combat/tools/dm-mass-combat.sh --test round B1-patrol --target-group alpha
bash .claude/additional/modules/mass-combat/tools/dm-mass-combat.sh --test turret J1-01 --target-group bravo
```

### Status / Round / End
```bash
bash .claude/additional/modules/mass-combat/tools/dm-mass-combat.sh status
bash .claude/additional/modules/mass-combat/tools/dm-mass-combat.sh next-round
bash .claude/additional/modules/mass-combat/tools/dm-mass-combat.sh end
```

---

## DM Rules [MANDATORY]

### 1. Every Unit Attacks Individually
Each unit in a group rolls its own d20. No grouped "the squad hits for 20 damage". Every B1, every clone, every fighter — individual roll.

### 2. One Group Per Command
`round` fires ONE group. Not "all enemies". This gives space for player decisions between enemy actions.

### 3. Player Actions Between Enemy Groups
After each enemy group fires, check if the player wants to react. Cover, return fire, throw grenade, use ability.

### 4. Targeting by Unit Type [MANDATORY]
Each template has a `targeting` field in module-data. Follow it:

| Targeting | Command | Used by | Why |
|-----------|---------|---------|-----|
| `random` | `round` | B1, militia, beasts | Dumb/untrained, fire at the crowd |
| `aimed` | `attack` | Clones, heroes, commanders | Trained, pick specific targets |
| `aoe` | `aoe` | Turrets, heavy weapons, grenades | Splash damage, DEX save for half |

**Never** use `attack` for B1 droids — they don't aim.
**Never** use `round` for turrets — they splash.
**Always** check template targeting before resolving attacks.

### 5. Status After Every 2-3 Actions
Run `status` regularly so player sees the battlefield clearly.

### 6. Cover Matters
Groups in cover get +2 AC. Always declare cover BEFORE attacks resolve. Use `cover` command.

### 7. Templates Are Truth
Unit stats come from `module-data/mass-combat.json` templates. Use `--template` when adding units. Only use manual `--type --ac --hp` for unique units not in templates (e.g. player character with custom stats from character.json).

### 8. Zone Grouping [MANDATORY]
Units that physically occupy the same area MUST be in the same group. When attackers fire at the group, random targeting distributes shots across ALL units in the zone — including vehicles, turrets, cover objects. AC naturally regulates hit probability (a turret at AC 18 gets hit much less than a B1 at AC 13 by the same attacker).

**Examples:**
- Turret + crew → same group. Shots randomly hit either crew or turret.
- Soldiers behind sandbags → sandbags are a "unit" with high AC, low HP. Destroy them = no more cover.
- BTR with exposed gunner → BTR (AC 19, HP 80) + gunner (AC 14, HP 20) in same group.
- Explosive barrel near enemies → barrel (AC 8, HP 10) in the group. If hit → AOE on the group.

**When the group attacks outward**, use `--count` to exclude non-combatant objects:
```bash
# Only 3 B1 crew shoot, not the turret itself
round J1-west --target-group bravo --count 3
# Turret fires separately as AOE
turret J1-04 --target-group bravo
```

### 9. Attack Range [MANDATORY]
Units have `range`: `ranged` (default), `melee`, or `both`.

- **ranged** — can attack any group (blasters, cannons)
- **melee** — can ONLY attack targets in the SAME group (lightsabers, vibroswords). Must `move` to target group first!
- **both** — can do either (BX commando droids)

Set via `--range melee` on add, or `"range"` in template/unit data. Melee units in `round` auto-skip if no enemies in their group. `attack` command blocks with error message.

**Example:** Ahsoka (melee) wants to attack J1-north crew → must `move Асока --to J1-north` first (costs 1 round), then attack next round.

### 10. Targeting Weight [MANDATORY]
Large objects absorb more incoming fire. `weight` controls how often a unit is randomly targeted by `round` and `turret` commands. `attack` (aimed shots) ignores weight — trained shooters pick their target.

| Weight | Size | Examples |
|--------|------|----------|
| 1 | Person-sized (default) | B1, clone, tvi'lek, commander |
| 2-3 | Vehicle/turret | J-1 cannon, speeder, mounted gun |
| 4-5 | Large vehicle | AAT tank, AT-TE, dropship |

Set via `--weight` on add or `"weight"` in template. Crew hiding behind turret (weight 3) gets targeted ~17% vs turret ~50% — instead of equal 25% each. AC still determines if the shot hits.

---

## Output Format

```
═══ B1-bridge (6 units) ═══
🎲 B1-01 → Хантер vs AC 14: [12]+3=15 — ✓ HIT → 1d6=[4]=4 dmg (HP→13)
🎲 B1-02 → Рекс vs AC 14: [7]+3=10 — ✗ MISS
🎲 B1-03 → Асока vs AC 16: [2]+3=5 — ✗ MISS
🎲 B1-04 → Хантер vs AC 14: [18]+3=21 — ✓ HIT → 1d6=[3]=3 dmg (HP→10)
🎲 B1-05 → Глюк vs AC 14: [1]+3=4 — 💀 FUMBLE
🎲 B1-06 → Рекс vs AC 14: [15]+3=18 — ✓ HIT → 1d6=[5]=5 dmg (HP→23)
───
Hits: 3/6 | Damage: 12 | Kills: 0
```

---

## Stat Reference (Star Wars)

| Unit | AC | HP | ATK | DMG | Notes |
|------|----|----|-----|-----|-------|
| B1 Battle Droid | 13 | 7 | +3 | 1d6 | Cheap, inaccurate |
| B2 Super Battle Droid | 16 | 22 | +5 | 2d6 | Wrist blaster |
| BX Commando Droid | 15 | 18 | +6 | 1d8+2 | Melee or ranged |
| Tactical Droid | 15 | 40 | +5 | 2d6 | Commander |
| Clone Trooper | 14 | 20 | +5 | 2d6 | DC-15S |
| Tvi'lek Fighter | 12 | 10 | +3 | 1d6 | Light blaster |
| J-1 Turret | 18 | 50 | +6 | 3d10 | Anti-air, slow |
