## id
realistic-progression

## name
Realistic Progression (Project Zomboid style)

## description
No classes, no XP tables. Skills grow from doing. Books accelerate learning. NPCs provide training bonuses. Stats grow through sustained activity.

## genres
survival, post-apocalyptic, horror, stalker, realistic, gritty

## recommended_for
Campaigns where character growth should feel earned through in-world actions, not abstract XP.

## rules

### Skill Growth Through Action (Project Zomboid style)
No XP table. No class levels. No abstract progression. Character grows ONLY through doing.

**Skill formula:**
`1d20 + stat_mod + skill_bonus + training_bonuses` vs `DC - tool_modifiers - book_modifiers`

**Sources of growth:**

| Source | Bonus | How to get |
|--------|-------|-----------|
| Stat mod | based on stat | Grows very slowly through sustained activity |
| Skill practice | +1 per milestone | DM awards when character has meaningfully practiced (days of use, critical moments, breakthroughs) |
| NPC training | +1 or +2 | Lesson from someone skilled (costs time + payment/favor). Better teacher = bigger bonus |
| Book knowledge | DC -1 to -3 | Read a relevant book. Beginner books = -1, Advanced = -2, Master-level = -3 |
| Tools/equipment | DC -1 to -2 | Quality tools reduce difficulty. Masterwork = -2. Improvised = no bonus |
| Notes/journal | DC -1 | Character writes down methods, recipes, observations |

**Skill storage format:**
```json
"melee": {
  "total": 3,
  "breakdown": {"bat practice (1 week)": 1, "Meatball training": 2},
  "dc_mod": -2,
  "dc_breakdown": {"combat manual": -1, "good baseball bat": -1}
}
```

**Bonuses stack without limits.** Natural limiters: no teacher better than you = slower growth. No new challenges = stagnation. Repeating easy tasks does not improve skill.

**Stat growth:** Stats (STR, DEX, CON, INT, WIS, CHA) grow VERY slowly. Months of daily relevant activity for +1. Max +3 total growth per stat from training. STR from carrying/fighting, DEX from agility/shooting, CON from endurance/hardship, INT from study/crafting, WIS from observation/survival, CHA from leadership/persuasion.

**HP growth:** Max HP does not increase from levels. Two paths:
- CON improvement → HP recalculates
- Survival hardening: DM rolls d20 after near-death experience, 18+ = +1 max HP (body adapts to trauma)

**"Level" is a label**, not a mechanic. DM assigns level-up when character has grown across multiple skills. Level determines proficiency bonus (+2 at L1-4, +3 at L5-8). No class features — only what the character actually learned in-world.

**Auto-success:** If minimum roll (1 + all bonuses) >= DC, no roll needed. Routine tasks don't require dice.
