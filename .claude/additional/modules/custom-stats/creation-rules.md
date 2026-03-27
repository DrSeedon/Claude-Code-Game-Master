# Custom Stats — Creation Rules

> Instructions for DM (Claude) when building a new campaign with this module active.
> Run AFTER the user defines tone/setting, BEFORE generating world details.

---

## Step 1: Suggest Stats Based on Genre

Based on the campaign's tone and setting, propose a stat set. Show examples, let the user pick.

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  CUSTOM STATS SETUP
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Based on your [GENRE] campaign, here are stat suggestions:

  SURVIVAL (Hunger/Thirst/Radiation)
  Tracks resource depletion in a harsh world.
  Drain per hour, consequences at zero.

  MENTAL (Sanity/Stress/Morale)
  Psychological pressure builds over time.
  Events trigger spikes, rest partially restores.

  MAGICAL (Mana/Corruption/Attunement)
  Mana regenerates during rest, corruption grows with dark magic.

  CUSTOM — define your own stats

  → Type numbers to enable (e.g. "1 3") or describe custom stats.
  → Type SKIP to use no custom stats.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

**Genre presets:**
- Survival (STALKER/Fallout/Metro): Hunger, Thirst, Radiation
- Horror (CoC/Delta Green): Sanity, Stress
- Fantasy: Mana, Fatigue
- Sci-fi: Oxygen, Power, Hull
- Strategy/Civilization: Population, Food, Materials, Knowledge, Faith, Culture
- Custom: ask user what stats matter in their world

> **IMPORTANT**: All stats — character, civilization, faction — go into `module-data/custom-stats.json` under `character_stats`.
> Do NOT create separate fields like `civilization_stats` in campaign-overview. Single source of truth — `character_stats`.

---

## Step 2: For Each Stat, Ask How It Behaves

For each selected stat, clarify:

1. **Scale**: 0–100 (default) or something else?
2. **Starting value**: Full (100)? Partial? Zero?
3. **Drain rate**: How fast does it drop per hour?
4. **Recovery**: Restored by sleep/rest? By items? Automatically?
5. **Consequences**: What happens at 0 (or max, for accumulation stats)?

Show a summary before writing:

```
  hunger:    0–100, starts 80, -5/hr, items restore, starvation at 0 → -2 HP/hr
  thirst:    0–100, starts 85, -8/hr, items restore, dehydration at 0 → -3 HP/hr
  radiation: 0–∞,  starts 0,  +2/hr in hot zones, anti-rad restores, poisoning at 80

  Confirm? [Y / edit]
```

---

## Step 3: Write Config to Campaign

### 3a. Write EVERYTHING to `module-data/custom-stats.json`

Both rules AND character stat values go in the same file:

```bash
CAMPAIGN_DIR=$(bash tools/dm-campaign.sh path)
mkdir -p "$CAMPAIGN_DIR/module-data"
```

```json
{
  "enabled": true,
  "character_stats": {
    "hunger":    {"current": 80, "min": 0, "max": 100},
    "thirst":    {"current": 85, "min": 0, "max": 100},
    "radiation": {"current": 0,  "min": 0, "max": 500}
  },
  "rules": [
    {"stat": "hunger", "per_hour": -5, "sleep_rate": -1},
    {"stat": "thirst", "per_hour": -8, "sleep_rate": -1},
    {"stat": "radiation", "per_hour": -1}
  ],
  "stat_consequences": {
    "starvation": {
      "condition": {"stat": "hunger", "operator": "<=", "value": 0},
      "effects": [
        {"type": "hp_damage", "amount": -2, "per_hour": true},
        {"type": "message", "text": "Hunger takes its toll."}
      ]
    }
  }
}
```

**Do NOT put custom_stats in character.json** — the engine reads/writes `character_stats` from module-data only.

---

## Step 4: Confirm and Show Preview

```
  Custom Stats Configured:
  ├─ hunger:    80/100  (-5/hr)
  ├─ thirst:    85/100  (-8/hr)
  └─ radiation: 0       (+2/hr in hot zones)

  Consequences: starvation at hunger=0, dehydration at thirst=0
  Sleep recovery: thirst+hunger do NOT restore during sleep
                  fatigue DOES restore during sleep (-20/hr)
```

---

## Notes

- If user picks SKIP → do NOT set `time_effects.enabled`, do NOT add `custom_stats` to character
- Accumulation stats (radiation, corruption) have no `max` — they climb indefinitely
- Always confirm the config summary before writing
- Stats interact with world narrative: mention them in scene descriptions

---

## Population-Scaled Food (Civilization campaigns)

For civilization/tribe campaigns where food consumption scales with population automatically.

Use `per_hour_formula` instead of `per_hour` — the engine evaluates it each tick using current `custom_stats` values as variables:

```json
{
  "stat": "food",
  "per_hour_formula": "-(population * 2) / 24",
  "description": "Food consumption: population people * 2 portions / 24h"
}
```

- Any custom stat name can be used as a variable in the formula
- Evaluated every hour — always reflects current population
- food stored in **absolute units** (portions), NOT percentages
- `max` = storage capacity (e.g. 12000 = 120 days for 50 people at 2/day)

**When food is added** (hunt/trade/harvest):
```bash
bash .claude/additional/modules/custom-stats/tools/dm-survival.sh custom-stat food +[amount]
```

---

## Recurring Expenses During World-Building

After setting up custom stats, ask the player about living costs. Propose defaults based on setting:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  RECURRING EXPENSES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  These auto-deduct from your money as game time passes:

  [1] Food & Water — 2-4 copper/day (random)
  [2] Room Rent — 30 copper/month
  [3] Custom — define your own

  → Type numbers to enable, or SKIP for no expenses.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

**Genre presets:**
- Fantasy (D&D): Food 2-4c/day, Room 20-50c/month
- Survival (STALKER): Food 5-10c/day, Shelter 30c/week, Ammo upkeep 10c/day
- Sci-fi: Life support 5c/day, Fuel 20c/week, Docking fees 50c/month
- Civilization: Food scaled by population (use custom stat formula instead)

Write to `module-data/custom-stats.json` under `recurring_expenses`:

```json
"recurring_expenses": [
  {
    "name": "Food & Water",
    "interval_hours": 24,
    "cost_min": 2,
    "cost_max": 4,
    "accumulated_hours": 0
  },
  {
    "name": "Room Rent",
    "interval_hours": 720,
    "cost": 30,
    "accumulated_hours": 0
  }
]
```

**Fields:**
- `interval_hours` — deduction interval (24 = daily, 168 = weekly, 720 = monthly)
- `cost` — fixed amount in base currency units (copper)
- `cost_min` / `cost_max` — random range per trigger (use instead of `cost`)
- `accumulated_hours` — always starts at 0

All costs in base currency units. Auto-deducted every `tick(--elapsed N)`. If not enough money → warning printed, DM decides consequences (debt, hunger, eviction).

---

## Timed Consequences During World-Building

When scheduling future events during world creation, use `--hours N` to make them tick automatically with game time:

```bash
# Event triggers after 8 game hours
bash tools/dm-consequence.sh add "Patrol arrives at the gate" "8 hours" --hours 8

# Event triggers after 2 days
bash tools/dm-consequence.sh add "Storm hits the southern sector" "2 days" --hours 48

# Event triggers next session (~8 hours of game time)
bash tools/dm-consequence.sh add "Merchant offers a bounty over drinks" "next session" --hours 8
```

Conversion table: "30 min" = `--hours 0.5`, "2 hours" = `--hours 2`, "1 day" = `--hours 24`, "3 days" = `--hours 72`, "1 week" = `--hours 168`.

Every `dm-time.sh --elapsed` automatically decrements remaining hours. When a consequence reaches 0 → auto-resolves and the DM is notified with `⚠️ Timed Consequences Triggered`.
