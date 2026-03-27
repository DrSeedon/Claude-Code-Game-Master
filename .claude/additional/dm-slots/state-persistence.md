## State Persistence <!-- slot:state-persistence -->

**THE RULE**: If it happened, persist it BEFORE describing it to the player.

**Self-check after every state change:** "Did I WRITE it to a file, or just SAY it in narration?" If the answer is "just said it" — STOP and persist NOW. Skills → `character.json`. Abilities → `character.json`. Stats → `dm-player.sh` (custom stats via module dm-survival.sh if enabled). Items → `dm-inventory.sh`. Quests → `dm-plot.sh`. NPCs → `dm-npc.sh`. Facts → `dm-note.sh`.

**Ability costs MUST be charged immediately.** Every ability in `character.json` has a `"cost"` field. When the player uses an ability — charge the cost BEFORE narrating. Custom stat costs → `dm-player.sh custom-stat "<stat>" +N --reason "<ability used>"`. Do NOT forget costs during practice sessions — training uses abilities too.

### State Persistence Commands

| Change Type | Command |
|-------------|---------|
| XP | See [XP & Rewards](#xp--rewards) |
| Gold/Items/HP | See [Loot & Rewards](#loot--rewards) |
| Max HP changed | `bash tools/dm-player.sh hp-max "[name]" +6` (level up, blessing, curse) |
| Condition added | `bash tools/dm-condition.sh add "[name]" "[condition]"` |
| Condition removed | `bash tools/dm-condition.sh remove "[name]" "[condition]"` |
| Check conditions | `bash tools/dm-condition.sh check "[name]"` |
| NPC updated | `bash tools/dm-npc.sh update "[name]" "[event]"` |
| Location moved | `bash tools/dm-session.sh move "[location]" --elapsed N` |
| Future event | `bash tools/dm-consequence.sh add "[event]" "[trigger text]" --hours N` |
| Important fact | `bash tools/dm-note.sh "[category]" "[fact]"` |
| Party NPC HP | `bash tools/dm-npc.sh hp "[name]" [+/-amount]` |
| Party NPC condition | `bash tools/dm-npc.sh condition "[name]" add "[cond]"` |
| Party NPC equipped | `bash tools/dm-npc.sh equip "[name]" "[item]"` |
| NPC joins party | `bash tools/dm-npc.sh promote "[name]"` |
| Tag NPC to location | `bash tools/dm-npc.sh tag-location "[name]" "[location]"` |
| Tag NPC to quest | `bash tools/dm-npc.sh tag-quest "[name]" "[quest]"` |
| **Quest created** | `bash tools/dm-plot.sh add "[name]" --type [type] --description "[desc]" --objectives "[o1],[o2]"` |
| **Quest progress** | `bash tools/dm-plot.sh update "[name]" "[event]"` |
| **Quest objective done** | `bash tools/dm-plot.sh objective "[name]" "[objective]" complete` |
| **Quest completed** | `bash tools/dm-plot.sh complete "[name]" "[outcome]"` |

### Consequence Rules (MANDATORY — NO EXCEPTIONS)

- **Consequences are DM-ONLY knowledge.** NEVER reveal consequence text, timers, or remaining hours to the player. Consequences are hidden plot triggers — the player experiences them as surprise events when they fire. No "ticking clocks" in narration, no countdowns, no hints about remaining time.
- **EVERY consequence MUST have `--hours N`.** No exceptions. A consequence without `--hours` is BROKEN — it will never tick, never trigger, and silently rot in the JSON. If you catch yourself typing `dm-consequence.sh add` without `--hours` — STOP and add it. NOTE: `--hours` is implemented by the custom-stats module middleware. If custom-stats is disabled, timed consequences will not tick.
- `dm-time.sh "_" "<date>" --elapsed N` and `dm-time.sh "_" "<date>" --to HH:MM` automatically tick consequences and custom stats via post-hook.
- Conversion: "30 min" = `--hours 0.5`, "2 hours" = `--hours 2`, "1 day" = `--hours 24`, "3 days" = `--hours 72`, "1 week" = `--hours 168`, "next session" = `--hours 8`
- `immediate` = `--hours 0` (triggers on next tick)
- **ALWAYS use `--elapsed` or `--to` when advancing time.** Setting time without elapsed means consequences DON'T tick.

### Quest Rules (MANDATORY)

- **New storyline emerges** (NPC gives task, player discovers mystery, threat appears) → `dm-plot.sh add` with type, description, objectives, linked NPCs/locations.
- **Player makes progress** (finds clue, reaches location, talks to NPC about quest) → `dm-plot.sh update` to log the event.
- **Objective fulfilled** (specific goal achieved) → `dm-plot.sh objective "Quest" "Objective" complete`.
- **New goal discovered mid-quest** → `dm-plot.sh objective "Quest" "New goal" add`.
- **Quest resolved** → `dm-plot.sh complete` or `dm-plot.sh fail` with outcome description.
- **Every quest MUST have at least one objective.** A quest without objectives has no trackable progress.
- **Use `dm-plot.sh threads`** at session start to review active storylines and catch stale quests.
- Quests live in `plots.json`. Do NOT store quest/plot data in `facts.json` via `dm-note.sh`.

### Note Categories (ALLOWED)

Facts = **permanent truths about the world**. NOT a session diary.

| Category | What goes here | Example |
|----------|---------------|---------|
| `lore` | World history, magic rules, religion | "Shyish is the Wind of Death, one of 8 Winds of Magic" |
| `npc` | NPC backstory, relationships, secrets | "Elza is Hilda Krantz's daughter, burned at p.53" |
| `companion` | Companion behavior rules | "Koschei never talks, only clicks bones" |
| `economy` | Prices, jobs, trade routes, recurring income | "Brenczel: 2 days/week, 1g/day" |
| `rumors` | Unverified info the party heard | "Mueller's sheep gnawed at night" |
| `rules` | Campaign-specific homebrew rules | "Silver +1 vs undead in this setting" |
| `location` | Permanent location facts not in locations.json | "Wortbad catacombs — under cemetery, 2 levels" |
| `training` | Skills gained, teachers, training progress | "Hanna: knives +2, Otto: herbalism +2" |

**DO NOT write to facts:**
- Session events ("Wilhelm defeated the strig") → goes in `session-log.md` via `dm-session.sh end`
- Combat logs ("Combat: X vs Y") → goes in `session-log.md`
- Quest progress → goes in `plots.json` via `dm-plot.sh update`
- NPC events → goes in `npcs.json` via `dm-npc.sh update`

**Plot/quest data belongs in `plots.json` via `dm-plot.sh`, NOT in notes.**

### --reason Flag (MANDATORY for inventory)

ALL inventory changes MUST include `--reason` to label the cause:

```bash
bash tools/dm-inventory.sh update "Char" --gold -50 --hp -3 --reason "ambush on the road"
```

An inventory change without `--reason` is like a dice roll without `--label` — untraceable.

### Calendar & Game Clock

Game clock (`precise_time`, `game_date`) lives in `campaign-overview.json` (CORE). Config in `campaign-overview.json` → `"calendar"` section.

- `dm-time.sh --elapsed N` advances clock and ticks custom stats via post-hook
- `dm-time.sh --to HH:MM` sets exact time, auto-calculates elapsed
- `dm-time.sh --sleeping` uses sleep_rate for custom stat decay
- `dm-session.sh move --elapsed N` combines move + time advance (preferred for travel)
- Date auto-advances when clock crosses midnight
- Default: Gregorian. Campaign-specific: any custom calendar

### Session Handoff Format [MANDATORY AT SESSION END]

At session end, write `world-state/campaigns/[campaign-name]/session-handoff.md`. This is your briefing to the NEXT DM instance. Overwritten each session. **This is the most important thing you do before dying.**

**Be SPECIFIC.** "Party is at tavern" = FAIL. "Wilhelm and Elza are in bed at the Goerlitz house, Koschei guards the bedroom door, bone-anchor drying on the windowsill" = GOOD.

Template:

```markdown
# Session Handoff — [Campaign Name]
Last updated: [date, game date]

## Current Situation
[2-4 sentences: What is happening RIGHT NOW. Scene state, mood, what just happened.]

## Character Critical Notes
[Bullet points — things that get LOST in JSON and cause inconsistencies:]
- [Familiar details: species, behavior, where it stays]
- [Items being carried/worn that affect narrative]
- [Speech patterns, quirks, physical details]
- [What abilities the character HAS vs still learning]

## Relationships
[Key NPCs with REAL emotional state, not just attitude tag:]
- **[Name]** — [actual relationship: living together? romantic? tense? owes a debt?]

## Active Threats
[What's dangerous, what the player should feel pressure from:]
- [Threat] — [how urgent, what happens if ignored]

## Player Intent
[What the player SAID they want to do next session:]
- [Stated plan or goal]
- [Items in progress (crafting, reading, training)]

## Narrative Style Notes
[Things the next DM MUST match:]
- [Formatting rules: no italics, etc.]
- [Tone: dark/funny/gritty]
- [Running jokes or recurring elements]
```

---
