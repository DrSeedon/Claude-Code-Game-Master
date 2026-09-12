## Combat <!-- slot:combat -->

### Trigger Conditions
- Hostile action declared ("I attack...")
- Initiative required
- Hostile creature appears

### Phase 1: Initialization

#### Step 1: Get Enemy Stats [MANDATORY - NEVER SKIP]

**Preferred: Add creature to wiki** (reusable across encounters):
```bash
bash tools/dm-wiki.sh add "goblin" --name "Goblin" --type creature \
  --stat "hp:7" --stat "ac:13" --stat "attack_bonus:4" --stat "damage:1d6+1" \
  --stat "speed:30" --stat "xp:50"
```

Once in wiki, auto-combat works with `--target` and `--defend --from`.

**Fallback: Quick NPC stats** (no wiki entry needed):
```
echo "Enemy: [Name] | HP: [X] | AC: [Y] | Attack: +[Z] | Damage: [dice]"
```

**Common NPC Stats:**
| Type | HP | AC | Attack | Damage |
|------|----|----|--------|--------|
| Guard | 11 | 16 | +3 | 1d6+1 |
| Bandit | 11 | 12 | +3 | 1d6+1 |
| Priest | 27 | 13 | +2 | 1d6 |
| Veteran | 58 | 17 | +5 | 1d8+3 |
| Mage | 40 | 12 | +5 | 1d4+2 |

#### Step 2: Track Combat in the Active Session

Keep the encounter in the current session summary. Do not create a permanent
fact for a routine combat start; persist only mechanical changes and durable
world consequences as they occur.

#### Module Routing

The compiled **Resolved Gameplay Profile** at the top of this rules file is
authoritative. Use its exact route for individual ordinary attacks, specialized
weapon attacks, and group or zone combat. Do not choose an inactive alternative
from examples elsewhere in the rules.

### Phase 2: Initiative
```bash
# Roll the complete turn order through CORE auto-lookup
bash tools/dm-roll.sh --initiative "[player]" "[party NPC]" "[enemy]"
```
Track turn order in memory (highest to lowest).

### Phase 3: Combat Rounds

**Player Turn — Auto-Combat (PREFERRED):**
1. Ask: "Your turn. What do you do?"
2. Resolve action:
```bash
# Melee/ranged attack — auto-lookup weapon + creature AC + auto-damage on hit
bash tools/dm-roll.sh --attack "Longsword" --target "goblin"
bash tools/dm-roll.sh --target "goblin"                          # auto-picks equipped weapon

# Ranged with distance — auto-disadvantage beyond normal range
bash tools/dm-roll.sh --attack "Shortbow" --target "goblin" --range 120

# Spell attack — spell attack bonus + creature AC + auto-damage
bash tools/dm-roll.sh --spell "fire-bolt" --target "goblin"

# Save-based spell — creature rolls save vs spell DC + auto-damage on fail
bash tools/dm-roll.sh --spell "shyish-bolt" --target "goblin"
```
3. The same command rolls damage, applies PEN/PROT when present, persists target
   HP, and deducts one round for weapons with `ammo_type`.
4. Never run a second damage roll or a separate HP command after successful
   auto-combat. Narrate the persisted result.

**Enemy Turn — Auto-Combat (PREFERRED):**
1. Choose target (usually nearest/most damaged)
```bash
# Creature attacks player — auto-lookup creature attack + player AC + auto-damage
bash tools/dm-roll.sh --defend --from "goblin"
```
2. The same command accepts `attack_bonus`/`damage` and `atk`/`dmg` aliases,
   applies attacker PEN against player PROT, and persists player HP.
3. Never follow it with a manual damage roll or HP update.

**Fallback (no wiki entry):** Manual rolls as before:
```bash
bash tools/dm-roll.sh "1d20+4" --label "Goblin Attack" --ac 14
bash tools/dm-roll.sh "1d6+1" --label "Goblin Damage"
```

**Party NPC Combat:**
```bash
bash tools/dm-roll.sh "1d20+4" --label "Attack (Grimjaw)" --ac 13
bash tools/dm-roll.sh "1d8+2" --label "Damage (Grimjaw)"
bash tools/dm-world.sh combat-damage "creature:target" 7
bash tools/dm-npc.sh hp "Silara" +2     # Heal a party NPC
bash tools/dm-npc.sh party              # Check party status
```

Use `combat-damage` after a successful manual ally attack. It persists HP and
awards a defeated creature's configured XP to the active player exactly once.

### Narrative Combat Beat [MANDATORY]

Tool output is the mechanical audit trail, not the player-facing scene. After
the rolls and state writes, narrate the exchange before asking for another
action.

For each round or complete short fight, include:
- What appeared or changed in the environment and how combatants reacted
- How the attacks, misses, wounds, movement, and defenses looked in the fiction
- One brief ally or enemy reaction when a speaking combatant is present
- The immediate outcome and new tactical situation

Compress a one-round fight into one to three lively paragraphs: reveal,
exchange, result, reaction. Embed only the numbers that clarify stakes. Never
substitute a status table, bullet ledger, or raw tool transcript for narration
unless the player explicitly asks for a mechanical breakdown.

### Phase 4: Resolution

Auto-combat awards the defeated creature's configured `xp` exactly once when
its HP first reaches zero. Never add the same combat XP manually. See
[XP & Rewards](#xp--rewards) for non-combat awards and [Loot & Rewards](#loot--rewards)
for loot handling and post-combat recording.

### Combat Modifiers Quick Reference

| Situation | Effect |
|-----------|--------|
| Advantage | Roll 2d20, use higher |
| Disadvantage | Roll 2d20, use lower |
| Cover (half) | +2 AC and Dex saves |
| Cover (3/4) | +5 AC and Dex saves |
| Flanking | Advantage on melee attacks |
| Prone target | Advantage (melee), Disadvantage (ranged) |
| Critical Hit (nat 20) | Double ALL damage dice, then add modifiers |
| Critical Fail (nat 1) | Auto-miss; consider minor mishap (drop weapon, slip) |

### Death & Dying
- **0 HP** → Unconscious, start death saves
- **Death Save**: DC 10 Con save each turn
  - 3 successes = stabilized
  - 3 failures = death
  - Nat 20 = 1 HP and conscious
  - Nat 1 = 2 failures
- **Massive Damage**: Instant death if damage ≥ max HP

<!-- /slot:combat -->

---
