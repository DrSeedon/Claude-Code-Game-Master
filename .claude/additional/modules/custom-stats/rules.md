# Custom Stats — DM Rules

## ⚠️ MANDATORY: Always Pass --elapsed [NEVER SKIP]

Every `dm-time.sh` call MUST include `--elapsed <hours>`. Without it, custom stats do NOT tick.

```bash
bash tools/dm-time.sh "Late Morning" "Day 1" --elapsed 1.5        # ✅
bash tools/dm-time.sh "Morning" "Day 2" --elapsed 8 --sleeping    # ✅ sleep rates
bash tools/dm-time.sh "Late Morning" "Day 1"                      # ❌ stats broken
```

**Elapsed estimates:** conversation 0.5-1h, exploring 1-2h, short rest 1h, long rest/sleep 8h (`--sleeping`), half-day 4-6h, full day 12-16h. Travel via `dm-session.sh move --elapsed`.

## Ticking

- `dm-time.sh --elapsed` ticks stats automatically via post-hook (no manual `dm-survival.sh tick` needed)
- `dm-session.sh move --elapsed` also ticks automatically
- `--sleeping` flag uses `sleep_rate` for stats that have it configured
- Do NOT tick without `--elapsed` (teleportation, same-area movement)

## Status & Display

```bash
bash .claude/additional/modules/custom-stats/tools/dm-survival.sh status   # full status
bash .claude/additional/modules/custom-stats/tools/dm-survival.sh rates    # rate table
```

Include custom stats in scene headers: `Hunger: 72/100 │ Thirst: 58/100 │ Radiation: 15/500`

## Modifying Stats

### Via dm-inventory.sh (preferred — atomic transactions)

```bash
# Fixed value
bash tools/dm-inventory.sh update "Char" --stat hunger -10 --reason "ate rations"

# Dice expression (random)
bash tools/dm-inventory.sh update "Char" --stat radiation "1d6+2" --reason "exposed to waste"

# Negative dice: use "neg" prefix (CLI can't parse leading minus before dice)
bash tools/dm-inventory.sh update "Char" --stat radiation "neg1d3+2" --reason "anti-rad pill"
# Output: 📊 radiation: 29 → 25 (-4) 🎲-1d3+2=-4

# All-in-one: remove item + dice stat change + HP in single transaction
bash tools/dm-inventory.sh update "Char" \
  --remove "Anti-Rad Pill" 1 --stat radiation "neg1d3+2" --reason "anti-rad pill"
```

### Via dm-player.sh (simple changes)

```bash
bash tools/dm-player.sh custom-stat "Char" hunger +5 --reason "skipped meal"
```

**ALWAYS use `--reason`** — stat changes without reason are untraceable.

### Dice in --stat

- Any dice notation (`NdX`, `NdX+Y`, `2d6kh1`, etc.) is auto-detected
- Use `neg` prefix for negative rolls (CLI can't parse leading `-` before dice)
- Plain integers still work: `--stat hunger -5`
- Output shows 🎲 with formula and result for transparency

## Use Consumable (auto via wiki)

```bash
bash tools/dm-inventory.sh use "Char" "Healing Potion"           # use 1
bash tools/dm-inventory.sh use "Char" "Healing Potion" --qty 3   # use 3 at once
```

Auto: finds item in wiki.json → reads `use.effects` → removes from inventory → rolls dice → applies stat changes → shows narrative hint. **One command replaces 3** (remove + roll + stat change).

Wiki `use` format:
```json
"use": {
  "consume": true,
  "effects": [{"stat": "dark_power", "dice": "neg1d3+2"}],
  "hp": "-1d3",
  "hint": "Narrative hint for DM"
}
```

## Craft Item (auto via wiki recipe)

```bash
bash tools/dm-inventory.sh craft "Char" "healing-potion"            # craft 1
bash tools/dm-inventory.sh craft "Char" "healing-potion" --qty 3    # craft 3
bash tools/dm-inventory.sh craft "Char" "iron-ingot" --check        # check only
```

Auto: finds recipe in wiki.json → checks all ingredients in inventory → rolls skill vs DC (or auto-success) → deducts ingredients → adds product. **One command replaces 10+ flags.**

- Auto-success: if `1 + skill_bonus >= effective_DC`, no roll needed
- Fail/Fumble: ingredients lost
- `--check`: preview only, shows what's needed and success chance
- `--qty N`: craft multiple (ingredients multiplied)

**IMPORTANT:** Always use `--qty N` instead of calling multiple times. One command, not duplicates.

## Rate Modifiers

Temporary rate changes for environmental conditions:

```bash
bash .claude/additional/modules/custom-stats/tools/dm-survival.sh rate warmth +5      # adjust
bash .claude/additional/modules/custom-stats/tools/dm-survival.sh rate warmth set +8   # override
bash .claude/additional/modules/custom-stats/tools/dm-survival.sh rate warmth reset    # restore
```

Formula: `effective_rate = base_per_hour + rate_modifier`. Modifiers persist until changed.

## Timed Effects (Buffs/Debuffs)

Three types: `--rate-bonus` (modifies existing rate, subject to blocked_by), `--per-hour` (independent direct change), `--instant` (one-time).

```bash
# Add effects
dm-survival.sh effect add "Anti-Rad" --stat radiation --rate-bonus -10 --duration 4
dm-survival.sh effect add "Healing Potion" --stat hp --per-hour 5 --duration 3 --stackable
dm-survival.sh effect add "Venom" --stat hp --instant -10 --stat radiation --rate-bonus 3 --duration 6

# Remove / list
dm-survival.sh effect remove "Venom"
dm-survival.sh effects
```

- Without `--stackable`: same-name effect replaces (timer resets). With `--stackable`: instances stack
- `rate_bonus` = modifies how fast an existing process runs (affected by blocked_by)
- `per_hour` = separate source of change (bypasses blocked_by)

## Blocked-By Rules

Rules with `blocked_by` conditions zero positive rates when triggered. Negative rates (drain) are never blocked.

## Timed Consequences

```bash
bash tools/dm-consequence.sh add "Event description" "trigger" --hours 8
```

Auto-decrements with `dm-time.sh --elapsed`. At 0 → auto-triggers. Color indicators: 🟢 >6h, 🟡 2-6h, 🔴 <2h.

## Recurring Expenses

Configured in `module-data/custom-stats.json` → `recurring_expenses` array. Auto-deducts money on elapsed time.

Fields: `name`, `interval_hours` (24=daily), `cost` (fixed) or `cost_min`/`cost_max` (random range). All in base currency units. Edit JSON directly.

## Recurring Income

Configured in `module-data/custom-stats.json` → `recurring_income` array. Triggers automatically with `dm-time.sh --elapsed` when enough hours accumulate.

### Income with skill checks (recommended)

Each income source rolls a skill check vs DC. Outcome determines income amount and DM narrative hint.

```json
{
  "name": "Workshop: brackets for Fritz",
  "interval_hours": 168,
  "checks_per_interval": 1,
  "hours_per_check": 4,
  "check": {
    "dice": "1d20",
    "modifier": 5,
    "modifier_source": "Hammerschlag 100% + anvil + forge",
    "dc": 10
  },
  "outcomes": {
    "crit_fail":    {"income": -50,            "hint": "breakage: hammer/anvil/bones"},
    "fail":         {"income_dice": "1d4",     "hint": "defects, low sales"},
    "success":      {"income_dice": "1d10+5",  "hint": "normal week"},
    "crit_success": {"income_dice": "2d10+10", "hint": "big order!"}
  },
  "streak_threshold": 3,
  "streak_hint": "Fritz looks for another supplier.",
  "fail_streak": 0,
  "accumulated_hours": 0
}
```

### Fields

| Field | Purpose |
|-------|---------|
| `interval_hours` | Hours between triggers (84 = ~2x/week, 168 = weekly) |
| `checks_per_interval` | Rolls per trigger (2 = two work days per week) |
| `hours_per_check` | Real hours consumed per check (ticks stats: dp decay, food, etc.) |
| `check.modifier` | Skill bonus (levelable: better workers, tools, skills) |
| `check.dc` | Difficulty (raiseable for expensive products = more risk, more reward) |
| `outcomes.*` | Income + DM hint per outcome. `income` (fixed) or `income_dice` (roll) |
| `streak_threshold` | N consecutive fails before streak warning triggers |
| `streak_hint` | DM narrative for streak consequence |

### Outcome resolution

- **Nat 1** → `crit_fail` (disaster: breakage, loss, injury)
- **Below DC** → `fail` (reduced income, bad product)
- **DC or above** → `success` (normal income)
- **Nat 20** → `crit_success` (windfall: big order, new client, event)

### What's levelable

- `modifier`: better skeletons, equipment, skills → higher bonus
- `dc`: raise for premium products (more income on success, more risk on fail)
- `outcomes`: upgrade income dice when workshop improves
- `checks_per_interval`: more work days / clients = more rolls

### Time consumption

When `hours_per_check` is set, triggered income **ticks custom stats** for those hours (dp decay, food expenses, etc.). Work costs real time. Output shows:

```
💰 Notary (day 1/2): +1g 🎲[14]+6=20 vs DC 11 — ✓ SUCCESS
   ⏱️  8h spent
   [DM: good work. Full pay.]

⏱️  Work Time Effects (8h):
  📊 dark_power: 19.17 → 18.51 (-0.66)
```

### Simple income (no check)

For guaranteed passive income, use `income`, `income_dice`, or `income_min`/`income_max` without `check` block. No DC, always succeeds.

## Random Events

Auto-rolls a random event once per configured interval. DM receives event type + scope and narrates what happened. Configured in `module-data/custom-stats.json` → `random_events`.

```json
"random_events": {
  "enabled": true,
  "interval_hours": 168,
  "accumulated_hours": 0,
  "categories": [
    {"range": [1, 10], "type": "disaster", "emoji": "💀"},
    {"range": [11, 25], "type": "negative", "emoji": "⚠️"},
    {"range": [26, 50], "type": "neutral", "emoji": "📰"},
    {"range": [51, 75], "type": "opportunity", "emoji": "💡"},
    {"range": [76, 95], "type": "positive", "emoji": "🎁"},
    {"range": [96, 100], "type": "windfall", "emoji": "🌟"}
  ],
  "scopes": ["personal", "workshop", "npc", "city", "threat", "opportunity"]
}
```

Output:
```
🎲 RANDOM EVENT: 💡 OPPORTUNITY (d100=53)
Scope: threat (d6=5)
[DM: narrate an event based on type+scope above]
```

DM uses the type + scope to improvise a fitting narrative event:
- **type** = how good/bad (disaster → windfall)
- **scope** = what area of life it affects
- Categories and scopes are fully configurable per campaign

## Recurring Production (workshop/factory simulation)

Auto-rolls daily skill checks for skeleton workers. Each worker produces/consumes resources in a target NPC inventory (workshop stockpile). Configured in `module-data/custom-stats.json` → `recurring_production`.

```json
"recurring_production": [
  {
    "name": "Miner: ore extraction",
    "worker": "⛏️ Miner",
    "interval_hours": 24,
    "target_inventory": "Workshop",
    "check": {"dice": "1d20", "modifier": 4, "dc": 10},
    "outcomes": {
      "crit_fail": {"hint": "cave-in, pick broken", "produce": {}, "consume": {}},
      "fail":      {"hint": "hard rock, little ore", "produce": {"Iron ore (kg)": "1d4"}},
      "success":   {"hint": "good seam", "produce": {"Iron ore (kg)": "2d4+2"}},
      "crit_success": {"hint": "rich vein!", "produce": {"Iron ore (kg)": "4d4+5"}}
    },
    "accumulated_hours": 0
  },
  {
    "name": "Blacksmith: forging",
    "worker": "🔨 Blacksmith",
    "interval_hours": 24,
    "target_inventory": "Workshop",
    "check": {"dice": "1d20", "modifier": 7, "dc": 10},
    "outcomes": {
      "crit_fail": {"hint": "hammer cracked", "produce": {}, "consume": {"Iron ore (kg)": 3, "Firewood (kg)": 2}},
      "fail":      {"hint": "defects", "produce": {"Goods (nails)": "1d4"}, "consume": {"Iron ore (kg)": 3, "Firewood (kg)": 2}},
      "success":   {"hint": "smooth forging", "produce": {"Goods (nails)": "2d4+3"}, "consume": {"Iron ore (kg)": 3, "Firewood (kg)": 2}},
      "crit_success": {"hint": "masterwork!", "produce": {"Goods (nails)": "3d6+5"}, "consume": {"Iron ore (kg)": 3, "Firewood (kg)": 2}}
    },
    "accumulated_hours": 0
  }
]
```

### Fields

| Field | Purpose |
|-------|---------|
| `worker` | Display name with emoji |
| `interval_hours` | Hours between checks (24 = daily) |
| `target_inventory` | NPC name whose inventory receives produced items (must be party member) |
| `check` | Skill check: dice + modifier + dc |
| `outcomes.*.produce` | Items to ADD to target inventory. Dice expressions or fixed int. |
| `outcomes.*.consume` | Items to REMOVE from target inventory. Used for supply chains (ore→goods). |
| `outcomes.*.hint` | DM narrative hint |

### Supply chains

Workers can consume output of other workers. Example: Blacksmith consumes ore (from Miner) + firewood (from Woodcutter) and produces goods. If target inventory doesn't have enough resources, transaction fails silently.

### Selling produced goods

Production fills the workshop stockpile automatically. **Selling is manual** — the player character takes goods from workshop inventory and trades on market. Use `dm-inventory.sh transfer` or manual `update`.

### View workshop stockpile

```bash
bash tools/dm-inventory.sh show "Workshop"
```

### Output

```
🏭 Production:
  ✓ ⛏️ Miner: 🎲[10]+4=14 vs DC 10 — SUCCESS
     +7 Iron ore (kg)
     [DM: good seam]
  ✓ 🔨 Blacksmith: 🎲[6]+7=13 vs DC 10 — SUCCESS
     +7 Goods (nails)
     -3 Iron ore (kg)
     -2 Firewood (kg)
     [DM: smooth forging]
```

## Data Location

ALL data in `module-data/custom-stats.json` (per-campaign). Contains: `enabled`, `character_stats`, `rules`, `stat_consequences`, `recurring_expenses`, `recurring_income`, `recurring_production`, `random_events`. **NOT in character.json** — injected at runtime.
