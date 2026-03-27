# Mass Combat — DM Rules

Large-scale battle tracker. Every unit has individual HP, attacks individually, dies individually.
Supports PEN/PROT armor penetration system.

---

## When to Use Mass Combat vs Firearms Combat

**Both systems coexist in the same battle.**

| Situation | Engine | Why |
|-----------|--------|-----|
| PC attacks 1-3 enemies | `firearms-combat` | Full detail: ammo, fire modes, weapon choice |
| PC alone vs 1-3 enemies, no allies | `firearms-combat` only | No mass combat needed |
| NPC allies attack enemies | `mass-combat round` | Auto-resolve, fast |
| NPC enemies attack other NPCs | `mass-combat round` | Auto-resolve, fast |
| NPC enemies attack PC | `mass-combat attack` for roll, then `dm-player.sh hp` | Use NPC's PEN vs PC's PROT |
| Large battle 10+ units, PC participating | Both: `firearms-combat` for PC turns, `mass-combat` for NPC turns |
| Battle where PC is observer (Kingdom A vs Kingdom B) | `mass-combat` only | PC not fighting |

**Round flow in combined combat:**
```
1. next-round
2. Enemy NPC groups attack (mass-combat round per group)
   - Attacks at PC → apply damage via dm-player.sh hp (respect PEN vs PC's PROT)
   - Attacks at allied NPCs → mass-combat handles it
3. PC turn → firearms-combat (player chooses weapon, fire mode, target)
4. Allied NPC groups attack (mass-combat round per group)
5. status → show battlefield
6. Narrate results
```

---

## PEN/PROT — Armor Penetration

Units can have `pen` (weapon penetration) and `prot` (armor protection). Both default to 0.

### Damage Scaling

| Condition | Damage | Tag |
|-----------|--------|-----|
| PEN > PROT | 100% (full) | `[FULL]` |
| PROT/2 < PEN ≤ PROT | 50% (half) | `[HALF]` |
| PEN ≤ PROT/2 | 25% (quarter) | `[QUARTER]` |

Minimum 1 damage on hit. If both PEN and PROT are 0 (legacy units, unarmed) → full damage.

### Where PEN/PROT Applies
- `_resolve_attack()` — standard attacks (round, attack commands)
- `_spray_fire()` — turret/heavy weapon spray uses source PEN vs each target's PROT
- `aoe_damage()` — AOE uses `--pen` (CLI) or `source_pen` vs each target's PROT

### Practical Examples
```
Bandit (PEN 1) → Mercenary (PROT 5): PEN ≤ PROT/2 → QUARTER damage
Mercenary (PEN 4) → Bandit (PROT 1): PEN > PROT → FULL damage
War Hound (PEN 0) → Knight (PROT 4): PEN ≤ PROT/2 → QUARTER (claws vs armor)
War Hound (PEN 0) → Peasant (PROT 0): both 0 → FULL (claws vs bare skin)
Ballista (PEN 5) → Dragon Knight (PROT 6): PROT/2 < PEN ≤ PROT → HALF
```

---

## Setup (once per battle)

```bash
# 0. Check available templates
bash .claude/additional/modules/mass-combat/tools/dm-mass-combat.sh templates

# 1. Initialize battle
bash .claude/additional/modules/mass-combat/tools/dm-mass-combat.sh init "Battle Name"

# 2. Add units from template (preferred — stats from module-data/mass-combat.json)
bash .claude/additional/modules/mass-combat/tools/dm-mass-combat.sh add \
  --faction enemies --group Bandits-North --template BanditRaider --count 6

# 3. Add named units from template
bash .claude/additional/modules/mass-combat/tools/dm-mass-combat.sh add \
  --faction allies --group KingsGuard --template RoyalGuard --count 1 --names "Ser Aldric"

# 4. Add custom units (no template needed)
bash .claude/additional/modules/mass-combat/tools/dm-mass-combat.sh add \
  --faction allies --group KingsGuard --type Veteran --count 1 \
  --ac 14 --hp 30 --atk 6 --dmg "2d6+3" --pen 4 --prot 3 --names "Gareth"
```

---

## Round Flow

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
bash .claude/additional/modules/mass-combat/tools/dm-mass-combat.sh round Bandits-North --target-group KingsGuard
bash .claude/additional/modules/mass-combat/tools/dm-mass-combat.sh round Bandits-North --target-group KingsGuard --count 4
bash .claude/additional/modules/mass-combat/tools/dm-mass-combat.sh round RoyalGuard --target-faction enemies --advantage
```

### Single Attack — named unit picks targets
```bash
bash .claude/additional/modules/mass-combat/tools/dm-mass-combat.sh attack "Ser Aldric" --targets Bandit-01 Bandit-02
bash .claude/additional/modules/mass-combat/tools/dm-mass-combat.sh attack Gareth --targets Goblin-01 --advantage
bash .claude/additional/modules/mass-combat/tools/dm-mass-combat.sh attack Archer-01 --targets BanditLeader-01 --atk 8 --dmg "2d10+4"
```

### AOE — grenades, explosions, magical abilities
```bash
# Alchemist's Fire Flask
bash .claude/additional/modules/mass-combat/tools/dm-mass-combat.sh aoe "Alchemist Fire" \
  --targets Bandit-01 Bandit-02 Bandit-03 --damage "5d6" --save-type DEX --save-dc 14 --pen 5

# Catapult volley (use turret command for aoe template units)
bash .claude/additional/modules/mass-combat/tools/dm-mass-combat.sh turret Catapult-01 --target-group Infantry

# Necromancer fear wave
bash .claude/additional/modules/mass-combat/tools/dm-mass-combat.sh turret Necromancer-01 --target-group Militia
```

### Direct Damage / Heal / Kill
```bash
bash .claude/additional/modules/mass-combat/tools/dm-mass-combat.sh damage "Ser Aldric" 5
bash .claude/additional/modules/mass-combat/tools/dm-mass-combat.sh heal Gareth 8
bash .claude/additional/modules/mass-combat/tools/dm-mass-combat.sh kill Bandit-05
```

### Cover
```bash
bash .claude/additional/modules/mass-combat/tools/dm-mass-combat.sh cover KingsGuard
bash .claude/additional/modules/mass-combat/tools/dm-mass-combat.sh cover KingsGuard --remove
```

### Turret Fire (AOE template units — auto-pick targets)
```bash
bash .claude/additional/modules/mass-combat/tools/dm-mass-combat.sh turret VolleyArcher-01 --target-group Bandits --targets 3
```

### Move Units Between Groups
```bash
bash .claude/additional/modules/mass-combat/tools/dm-mass-combat.sh move GoblinBerserker-01 GoblinBerserker-02 --to KingsGuard
```

Move = reposition only, units skip their attack this turn (spent action moving).

### Test Mode (preview without saving)
```bash
bash .claude/additional/modules/mass-combat/tools/dm-mass-combat.sh --test round Bandits --target-group KingsGuard
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
Each unit in a group rolls its own d20. No grouped "the squad hits for 20 damage". Individual rolls, individual PEN vs PROT.

### 2. One Group Per Command
`round` fires ONE group. Not "all enemies". This gives space for player decisions between enemy actions.

### 3. Player Actions Between Enemy Groups
After each enemy group fires, check if the player wants to react. Cover, return fire, throw grenade, use ability.

### 4. Targeting by Unit Type [MANDATORY]
Each template has a `targeting` field. Follow it:

| Targeting | Command | Used by | Why |
|-----------|---------|---------|-----|
| `random` | `round` | Bandits, goblins, zombies, conscripts | Untrained, fire at the crowd |
| `aimed` | `attack` | Knights, veterans, elite archers, assassins | Trained, pick specific targets |
| `aoe` | `turret` | Catapults, volley archers, necromancers, siege engines | Splash damage, saves for half |

### 5. PEN/PROT Determines Lethality [MANDATORY]
Check PEN vs PROT before narrating. A bandit with a shortsword (PEN 1) hitting a mercenary (PROT 5) does QUARTER damage — narrate the blade glancing off armor. An elite archer (PEN 5) hitting that same mercenary does FULL — narrate the bolt punching clean through.

### 6. Status After Every 2-3 Actions
Run `status` regularly so player sees the battlefield clearly.

### 7. Cover Matters
Groups in cover get +2 AC. Always declare cover BEFORE attacks resolve.

### 8. Templates Are Truth
Unit stats come from `module-data/mass-combat.json` templates. Use `--template`. Only use manual stats for unique units not in templates.

### 9. Zone Grouping [MANDATORY]
Units that physically occupy the same area MUST be in the same group. Random targeting distributes shots across ALL units in the zone. AC determines if the attack hits.

### 10. Attack Range [MANDATORY]
Units have `range`: `ranged` (default), `melee`, or `both`.

- **ranged** — can attack any group
- **melee** — can ONLY attack targets in the SAME group. Must `move` first!
- **both** — can do either

Melee units in `round` auto-skip if no enemies in their group.

### 11. Targeting Weight
`weight` controls random targeting priority. Higher = more likely to be targeted by `round`. Default 1. Commanders and bosses typically weight 2-3.

### 12. PC Damage from Mass Combat
When NPC hits PC via mass-combat:
1. Note the raw damage from mass-combat output
2. Apply PEN (attacker) vs PROT (PC's armor) scaling manually
3. Use `dm-player.sh hp -X` to apply final damage

---

## Output Format

```
═══ Bandits-North (4 units) ═══
🎲 Bandit-01 → Ser Aldric vs AC 15: [14]+3=17 — ✓ HIT → 1d6+1=[4]+1=5 PEN1vsPROT4[QUARTER] → 1 dmg (HP→25)
🎲 Bandit-02 → Gareth vs AC 14: [7]+3=10 — ✗ MISS
🎲 Bandit-03 → Guard-01 vs AC 15: [18]+3=21 — ✓ HIT → 1d6+1=[5]+1=6 PEN1vsPROT4[QUARTER] → 1 dmg (HP→21)
🎲 Bandit-04 → Ser Aldric vs AC 15: [1]+3=4 — 💀 FUMBLE
───
Hits: 2/4 | Damage: 2 | Kills: 0
```
