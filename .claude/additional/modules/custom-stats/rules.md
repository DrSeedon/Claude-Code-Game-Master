# Survival Stats — DM Rules

> These instructions tell the DM (Claude) when and how to call the survival module.

## When to Call

### After every `dm-session.sh move`

If the move output contains `[ELAPSED]` with hours:

```bash
bash .claude/additional/modules/custom-stats/tools/dm-survival.sh tick --elapsed <hours>
```

### After every `dm-time.sh` with elapsed hours

Stats tick **automatically** via middleware when `--elapsed` is passed to `dm-time.sh`:

```bash
bash tools/dm-time.sh "Night" "Day 3" --elapsed 4
bash tools/dm-time.sh "Morning" "Day 4" --elapsed 8 --sleeping
```

No need to call `dm-survival.sh tick` separately — the post-hook handles it.

### During sleep/long rest

Add `--sleeping` flag to `dm-time.sh`:

```bash
bash tools/dm-time.sh "Morning" "Day 4" --elapsed 8 --sleeping
```

The `--sleeping` flag:
- **sleep** stat: uses `sleep_restore_per_hour` (default +12.5/h) instead of drain
- Other stats with `sleep_rate` configured: uses that rate instead of `per_hour` (e.g., hunger drains slower during sleep)
- Stats without `sleep_rate`: drain at full speed (backward compatible)

## When NOT to Call

- Do NOT call after `dm-session.sh move` if no `[ELAPSED]` line was printed (e.g., teleportation, same-area movement)
- Do NOT call if `module-data/custom-stats.json` does not exist or has `enabled = false`

## Checking Status

To show the player's current custom stats:

```bash
bash .claude/additional/modules/custom-stats/tools/dm-survival.sh status
```

## Display in Scene Header

When custom stats exist, include them in the status bar:

```
LVL: 5  │  HP: ████████░░░░ 18/24 ✓  │  XP: 1250  │  GP: 27
Hunger: 72/100  │  Thirst: 58/100  │  Rad: 15/500
```

## Rate Modifiers

When environmental conditions change stat drain/recovery rates, use rate modifiers:

```bash
# Player puts on warm clothing → warmth drains slower
bash .claude/additional/modules/custom-stats/tools/dm-survival.sh rate warmth +5

# Player enters a heated building → warmth recovers fast
bash .claude/additional/modules/custom-stats/tools/dm-survival.sh rate warmth set +8

# Player leaves the building → back to base rate
bash .claude/additional/modules/custom-stats/tools/dm-survival.sh rate warmth reset
```

Formula: `effective_rate = base_per_hour + rate_modifier`

Rate modifiers persist in `character.json` until changed. Use `reset` when the temporary condition ends.

## Rate Table

To inspect all effective rates (base + modifier + activity + blocked status):

```bash
bash .claude/additional/modules/custom-stats/tools/dm-survival.sh rates
```

Use this before time advances to verify rates make sense for the current scene.

## Blocked-By Rules

Rules with `blocked_by` conditions will have their positive rate zeroed when the condition is met. Example: health regen blocked when hunger <= 30. Negative rates (drain) are never blocked.

## Timed Effects (Buffs/Debuffs)

When a character uses an item, spell, or encounters an environmental effect with a temporary duration, use timed effects.

### Three effect types

**`--rate-bonus N`** — modifies the EXISTING rate of a stat. Becomes part of the rate formula, subject to `blocked_by` rules. Use when the effect speeds up or slows down an already-ticking stat.

**`--per-hour N`** — direct stat change each hour, INDEPENDENT of campaign rules. Ignores `blocked_by`, ignores conditions. Use when the effect should work regardless of other mechanics.

**`--instant N`** — one-time change applied immediately when the effect is added. Not repeated.

### When to use rate_bonus vs per_hour

The key difference: `rate_bonus` is part of the rate system (affected by `blocked_by`), `per_hour` bypasses it.

Example: health regens +2/h but is `blocked_by: hunger <= 0`.

- Healing potion with `--rate-bonus +5`: hungry character gets effective rate 2+5=7, but blocked_by triggers → 0. **Potion wasted.**
- Healing potion with `--per-hour +5`: blocked_by zeroes the base rate, but per_hour applies separately → +5/h. **Potion works despite hunger.**

Rule of thumb:
- Effect modifies HOW FAST an existing process runs → `rate_bonus` (anti-radiation slowing radiation buildup)
- Effect is a separate source of healing/damage → `per_hour` (healing potion, poison DOT)

### Commands

```bash
# Anti-radiation drug: slows existing radiation rate for 4 hours
bash .claude/additional/modules/custom-stats/tools/dm-survival.sh effect add "Антирадин" --stat radiation --rate-bonus -10 --duration 4

# Healing potion: direct +5 hp/h for 3 hours (independent of rules)
bash .claude/additional/modules/custom-stats/tools/dm-survival.sh effect add "Хилка" --stat hp --per-hour 5 --duration 3 --stackable

# Poison: instant -10 hp + ongoing radiation rate increase
bash .claude/additional/modules/custom-stats/tools/dm-survival.sh effect add "Яд" --stat hp --instant -10 --stat radiation --rate-bonus 3 --duration 6

# Remove all effects with a given name
bash .claude/additional/modules/custom-stats/tools/dm-survival.sh effect remove "Яд"

# List active effects with remaining time
bash .claude/additional/modules/custom-stats/tools/dm-survival.sh effects
```

### Stacking

Without `--stackable`: re-applying an effect with the same name REPLACES the old one (timer resets).
With `--stackable`: multiple instances stack (two healing potions = double healing).

### Formula

`effective_rate = base_per_hour + rate_modifier + sum(effect_rate_bonus)`

`per_hour` effects are applied separately after the rate formula, not part of it.

## Activation Check

At session start, check if `module-data/custom-stats.json` exists and has `enabled = true`.
If yes, load these rules and follow them for the duration of the session.

## Data Location

ALL module data is stored at `module-data/custom-stats.json` (per-campaign), NOT in `campaign-overview.json` or `character.json`.

The file contains:
- `enabled` — module active flag
- `character_stats` — current stat values (hunger, thirst, radiation, sleep, rep_*, etc.)
- `rules` — tick rules (per_hour, sleep_rate, conditions)
- `stat_consequences` — threshold triggers (starvation, dehydration, radiation sickness)

**Character values are NOT in character.json** — they are injected at runtime from module-data.
