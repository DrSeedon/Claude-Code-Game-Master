<!-- slot:dice-rolling -->
# Dice Rolling

Use `bash tools/dm-roll.sh` for ALL dice rolls.

---

## Auto-Lookup (PREFERRED)

Auto-lookup reads the player node in world.json for skill totals, dc_mod, saves, and weapon stats. No manual +N needed. 1d20 is the default die — no need to specify it.

```bash
# Skill check — auto-reads total + dc_mod from player node in world.json
bash tools/dm-roll.sh --skill "Perception" --dc 15

# Saving throw — auto-reads save modifier
bash tools/dm-roll.sh --save "INT" --dc 14

# Attack roll — auto-reads weapon stats
bash tools/dm-roll.sh --attack "Longsword" --ac 16

# Advantage/disadvantage with auto-lookup
bash tools/dm-roll.sh --skill "Stealth" --dc 12 --advantage
bash tools/dm-roll.sh --save "DEX" --dc 14 --disadvantage
```

Use auto-lookup for ALL player character rolls. Fall back to manual notation only for:
- NPC/monster rolls (no player node entry)
- Custom/situational rolls (damage, healing, random tables)
- Rolls with ad-hoc modifiers not in world.json player node

## Auto-Combat (creatures from wiki)

Creatures stored in world.json as type `creature` with mechanics (hp, ac, attack_bonus, damage). Auto-combat rolls attack + damage in one call.

```bash
# Player attacks creature — weapon from player node in world.json, AC from creature node in world.json, auto-damage on hit
bash tools/dm-roll.sh --attack "Longsword" --target "goblin"

# Same but auto-picks equipped weapon
bash tools/dm-roll.sh --target "goblin"

# Creature attacks player — attack_bonus+damage from creature node in world.json, player AC from player node in world.json
bash tools/dm-roll.sh --defend --from "goblin"

# With advantage/disadvantage
bash tools/dm-roll.sh --target "goblin" --advantage
bash tools/dm-roll.sh --defend --from "goblin" --disadvantage
```

**Adding creatures to wiki:**
```bash
bash tools/dm-wiki.sh add "goblin" --name "Goblin" --type creature \
  --stat "hp:7" --stat "ac:13" --stat "attack_bonus:4" --stat "damage:1d6+1" \
  --stat "speed:30" --stat "xp:50"
```

**On hit:** auto-rolls damage dice. On crit: doubles damage dice. On miss: no damage roll.

## Manual Notation (for NPCs, damage, custom rolls)

```bash
# NPC skill check with label and DC
bash tools/dm-roll.sh "1d20+4" --label "Perception (Grimjaw)" --dc 15

# Attack roll vs AC
bash tools/dm-roll.sh "1d20+5" --label "Longsword Attack (Conan)" --ac 16

# Advantage
bash tools/dm-roll.sh "2d20kh1+3" --label "Stealth (advantage)" --dc 14

# Disadvantage
bash tools/dm-roll.sh "2d20kl1+2" --label "Athletics (disadvantage)" --dc 15

# Damage roll (no DC/AC needed)
bash tools/dm-roll.sh "2d6+3" --label "Longsword Damage"

# Saving throw
bash tools/dm-roll.sh "1d20+1" --label "DEX Save (Goblin)" --dc 13

# Healing
bash tools/dm-roll.sh "2d4+2" --label "Healing Potion"
```

---

## Output Examples

```
🎲 Perception (Grimjaw) vs DC 15: [16] +4 = 20 — ✓ SUCCESS
🎲 Stealth (Silara) vs DC 12: [3] +7 = 10 — ✗ FAIL
🎲 Longsword Attack (Conan) vs AC 16: [20] +5 = 25 — ⚔ CRITICAL!
🎲 Shortbow Attack (Goblin) vs AC 14: [1] +4 = 5 — 💀 FUMBLE!
🎲 Longsword Damage: [4+6] +3 = 13
🎲 Stealth (advantage): [14] ~(5)~ +3 = 17 — ✓ SUCCESS
```

---

## Transparency Rules [MANDATORY]

These rules ensure fair, cheat-proof play. No exceptions.

### 1. Always Use Labels
Every roll MUST have `--label` describing who rolls and what for. A roll without a label is untraceable.

**Right:** `--label "Perception (Grimjaw)"`
**Wrong:** bare `"1d20+4"` with no label

### 2. Declare DC/AC Before Rolling
Use `--dc` or `--ac` flags — the target number appears in output BEFORE the result. This prevents adjusting difficulty after seeing the roll.

**Right:** `bash tools/dm-roll.sh "1d20+5" --label "Lockpick (Silara)" --dc 15`
**Wrong:** roll first, then decide what DC to compare against

### 3. Batch Related Rolls Together
Chain related rolls with `&&` in one Bash call. 1–4 rolls per batch. No separators between them.

```bash
# Good: 3 Perception checks in one call
bash tools/dm-roll.sh "1d20+4" --label "Perception (Grimjaw)" --dc 15 && \
bash tools/dm-roll.sh "1d20+2" --label "Perception (Silara)" --dc 15 && \
bash tools/dm-roll.sh "1d20+6" --label "Perception (Conan)" --dc 15
```

Output:
```
🎲 Perception (Grimjaw) vs DC 15: [16] +4 = 20 — ✓ SUCCESS
🎲 Perception (Silara) vs DC 15: [3] +2 = 5 — ✗ FAIL
🎲 Perception (Conan) vs DC 15: [11] +6 = 17 — ✓ SUCCESS
```

### 4. Damage Rolls Need Only Labels
Damage has no pass/fail — just `--label`. No `--dc` or `--ac` needed.

### 5. Nat 20 and Nat 1 Override
- **Natural 20** on d20 = ⚔ CRITICAL regardless of DC/AC
- **Natural 1** on d20 = 💀 FUMBLE regardless of DC/AC

---

## Flag Reference

| Flag | Purpose | When to Use |
|------|---------|-------------|
| `--skill "name"` | Auto-lookup skill total + dc_mod from player node in world.json | Player skill checks (preferred) |
| `--save "name"` | Auto-lookup save modifier from player node in world.json | Player saving throws (preferred) |
| `--attack "weapon"` | Auto-lookup weapon stats from player node in world.json | Player attack rolls (preferred) |
| `--target "creature"` | Auto-lookup creature AC from world.json, auto-damage on hit | Combat: player attacks creature |
| `--defend` | Creature attacks player | Combat: creature turn |
| `--from "creature"` | Creature doing the attacking (with --defend) | Combat: creature turn |
| `--advantage` | Roll 2d20, keep highest | Advantage |
| `--disadvantage` | Roll 2d20, keep lowest | Disadvantage |
| `--label "text"` | Who and what | NPC/monster/custom rolls |
| `--dc N` | Difficulty Class | Skill checks, saving throws |
| `--ac N` | Armor Class | Attack rolls |

---

## When to Roll

**Roll when outcome is uncertain and stakes matter:**
- Skill checks (Perception, Stealth, Persuasion...)
- Attack rolls
- Saving throws
- Contested checks

**Do NOT roll for:**
- Trivial tasks (opening an unlocked door)
- Impossible tasks (jumping across a 100ft chasm)
- No meaningful consequence for failure
