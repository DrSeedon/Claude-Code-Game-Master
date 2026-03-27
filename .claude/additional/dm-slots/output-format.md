## Output Format <!-- slot:output-format -->

### Unicode Indicators
```
HP healthy (>50%)   → ████████░░░░ 18/24 ✓
HP wounded (25-50%) → █████░░░░░░░ 10/24 ⚠
HP critical (<25%)  → ██░░░░░░░░░░ 5/24 ⚠⚠

DAMAGE DEALT        → ▼5 HP
HEALING             → ▲8 HP

SUCCESS/HIT         → ✓ HIT! or ✓ SUCCESS
FAILURE/MISS        → ✗ MISS or ✗ FAIL
CRITICAL HIT        → ⚔ CRITICAL!
CRITICAL MISS       → 💀 FUMBLE!
```

### Currency Display
Format money using campaign's `currency.denominations` config from `campaign-overview.json`. Display as `Xg Ys Zc` (skip zero tiers if compact). Example: `2500 cp` → `25g 0s 0c`.

### Status Field Labels (Header Bar)
Use in the STATUS position of scene headers:
- `Normal` - No conditions
- `Poisoned` - Poisoned condition active
- `Wounded` - Below 50% HP
- `Critical` - Below 25% HP
- `Exhausted` - Exhaustion levels
- `Inspired` - Has Bardic Inspiration

### Enemy Condition Labels (Combat)
Use after enemy HP bars:
- `[Healthy]` - Full or near-full HP (>75%)
- `[Wounded]` - Below 75% HP
- `[Bloodied]` - Below 50% HP
- `[Critical]` - Below 25% HP
- `[Dead]` - 0 HP

### Standard Scene Template
```
================================================================
  LOCATION: [Location Name]              TIME: [Time of Day] ([HH:MM] if available)
  ────────────────────────────────────────────────────────────
  LVL: 5  │  HP: ████████░░░░ 18/24 ✓  │  XP: 1250  │  💰 27g 0s 0c  │  Normal
  [Custom Stats if present: Hunger: 72/100  │  Thirst: 58/100  │  Rad: 15/500]
================================================================

  [Narrative description - 2-3 sentences with sensory detail]

  ┌─────────────────────────────────────────────────────────┐
  │ [NPC NAME] says:                                        │
  │ "[Dialogue goes here]"                                  │
  └─────────────────────────────────────────────────────────┘

  [A]ction option  [B]ction option  [C]ction option

================================================================
  /dm save · /dm character · /help
================================================================
```

### Combat Template
```
================================================================
  ⚔ COMBAT ⚔  [Location Name]             ROUND [#]
  ────────────────────────────────────────────────────────────
  LVL: 5  │  HP: ██████░░░░░░ 14/24 ⚠  │  XP: 1250  │  💰 27g 0s 0c  │  Wounded
================================================================

  ENEMIES
  ├─ Orc Warrior ········ ████████░░░░ 18/22 HP ✓  [Healthy]
  └─ Goblin Scout ······· ░░░░░░░░░░░░ 0/7 HP 💀   [Dead]

  ────────────────────────────────────────────────────────────

  The orc's axe catches you across the shoulder. ▼5 HP

  🎲 Attack Roll: 17 + 5 = 22 vs AC 15 — ✓ HIT!

  ────────────────────────────────────────────────────────────
  YOUR TURN

  [A]ttack (Orc Warrior)  [M]ove  [C]ast spell  [D]odge

================================================================
```

### Dice Roll Display
Embed rolls in narrative for smooth flow:
```
  You attempt to pick the lock...
  🎲 Thieves' Tools: 14 + 3 = 17 vs DC 15 — ✓ SUCCESS

  The mechanism clicks softly. The door swings open.
```

### Dialogue Box
```
  ┌─────────────────────────────────────────────────────────┐
  │ GRIMJAW: "Who sent you?"                                │
  │                                                         │
  │ SILARA: "Easy, dwarf. This one's with me."              │
  └─────────────────────────────────────────────────────────┘
```

### Loot Box
```
  ┌─────────────────────────────────────────────────────────┐
  │ 💰 FOUND                                                │
  │    • 15 gold pieces                                     │
  │    • Rusty shortsword                                   │
  └─────────────────────────────────────────────────────────┘
```
**CRITICAL**: Persist loot BEFORE displaying this box.

### Session Start Header
Use when beginning a session:
```
================================================================
     ____  __  ____  _  _   __  _  _  ____    __  ____
    (    \(  )(  __)( \/ ) / _\/ )( \(  __)  (  )(  _ \
     ) D ( )(  ) _)  )  / /    ) \/ ( ) _)    )(  )   /
    (____/(__)(__)  (__/  \_/\_/\____/(____)  (__)(__\_)
================================================================
  Campaign: [Campaign Name]
  Character: [Character Name], Level [#] [Class]
  Last Session: [Date or "New Campaign"]
================================================================

  [Recap or opening narration]

================================================================
```

---
