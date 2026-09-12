# /new-game - Create Your World

Create a complete D&D campaign world from scratch through a guided interview.

---

## PHASE 1: CAMPAIGN NAME

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  CREATE YOUR WORLD
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Let's build a unique campaign world together.

QUESTION 1 of 4: What's your campaign called?

This will be the name of your save folder.
```

Wait for user response. Store as `CAMPAIGN_NAME`.

### Check if Campaign Already Exists
```bash
bash tools/dm-campaign.sh list
```

If a campaign with this name already exists, ask user:
- Switch to existing campaign?
- Choose a different name?
- Delete and recreate? (requires confirmation)

### Create New Campaign
```bash
bash tools/dm-campaign.sh create "<CAMPAIGN_NAME>"
bash tools/dm-campaign.sh switch "<CAMPAIGN_NAME>"
```

---

## PHASE 1.5: MODULE SELECTION

Run after campaign is created and switched (so modules persist to campaign-overview.json).

### 1. List available modules
```bash
bash .claude/additional/infrastructure/tools/dm-module.sh list-verbose
```

### 2. Display module menu

```
================================================================
  ╔═══════════════════════════════════════════════════════════╗
  ║              CONFIGURE MODULES                            ║
  ╚═══════════════════════════════════════════════════════════╝
================================================================

  [1] ✅ <id>  — <description, 5 words max>  ← default
  [2] ❌ <id>  — <description, 5 words max>
  ...

  ────────────────────────────────────────────────────────────
  💡 RECOMMENDED FOR THIS CAMPAIGN:
  Based on campaign name and tone, suggest which modules make
  sense. E.g. for survival/STALKER → firearms-combat + world-travel.
  For open-world exploration → world-travel. For classic D&D → no extras.
  For large battles → mass-combat.
  Write 1-2 sentences why each suggested module fits the vibe.

  ℹ️  Custom stats (hunger, mana, sanity, reputation etc.) are CORE
  features — no module needed. Configure after world creation via
  dm-world.sh custom-stat-define or in campaign-rules.md.
  ────────────────────────────────────────────────────────────
  Type numbers to toggle (e.g. "1 2") or ENTER to keep current.

================================================================
```

### 3. Apply selection
```bash
bash .claude/additional/infrastructure/tools/dm-module.sh activate <module-name>    # for each enabled
bash .claude/additional/infrastructure/tools/dm-module.sh deactivate <module-name>  # for each disabled
```

### 4. Load module rules into context
```bash
bash .claude/additional/infrastructure/dm-active-modules-rules.sh
```

Rules are now in context — use them for all world-building that follows.

---

## PHASE 1.6: LOAD MODULE CREATION RULES
Load creation-specific instructions from active modules:

```bash
bash .claude/additional/infrastructure/dm-active-modules-creation-rules.sh
```

These rules tell you HOW to handle world-building for each active module:
- **firearms-combat**: Weapon presets and firearms system configuration
- **mass-combat**: Unit templates and battle setup
- **world-travel**: World scale, coordinates, travel speed, terrain, encounters, compounds, and vehicles

**Note:** Custom stats (hunger, mana, sanity, reputation etc.) are CORE features — no module needed. Define them via `dm-world.sh custom-stat-define` or in campaign-rules.md.

**The creation rules augment (not replace) the phases below.**
Follow module-specific instructions when they apply to that phase.

---

## PHASE 1.7: NARRATOR STYLE
### 1. List available styles
```bash
bash .claude/additional/infrastructure/dm-narrator.sh list
```

### 2. Get recommendation based on campaign genre
```bash
bash .claude/additional/infrastructure/dm-narrator.sh recommend "<genre>"
```
Genre hints from campaign name/tone: horror→horror-atmospheric, classic fantasy→epic-heroic, roguelike/comedy→sarcastic-puns, noir/drama→serious-cinematic.

### 3. Display menu

```
================================================================
  ╔═══════════════════════════════════════════════════════════╗
  ║              NARRATOR STYLE                               ║
  ╚═══════════════════════════════════════════════════════════╝
================================================================

  [1] epic-heroic        — Grand scale, legendary deeds
  [2] horror-atmospheric — Dread through implication, not gore
  [3] sarcastic-puns     — Terry Pratchett at a tavern
  [4] serious-cinematic  — Every scene is a film shot

  ────────────────────────────────────────────────────────────
  💡 RECOMMENDED FOR THIS CAMPAIGN:
  Based on campaign name and genre, suggest which style fits.
  Write 1 sentence why it fits the vibe.
  ────────────────────────────────────────────────────────────
  Type a number to select, or ENTER to accept recommendation.
  Type "skip" to use no defined style.

================================================================
```

### 4. Apply selected style
```bash
bash .claude/additional/infrastructure/dm-narrator.sh apply <style-id>
```

This writes the full narrator style object into `campaign-overview.json` under `narrator_style`.
The DM will load and follow these rules throughout every session.

### 5. If user provides a custom style file
If user points to a `.md` file with their own style:
- Read the file
- Manually extract voice/rules/forbidden into `narrator_style` in campaign-overview.json
- Follow the same structure as built-in styles

---

## PHASE 1.8: CAMPAIGN RULES TEMPLATE
### 1. Get recommendation based on campaign genre
```bash
bash .claude/additional/infrastructure/dm-campaign-rules.sh recommend "<genre>"
```
Genre hints: horror/investigation → horror-investigation, survival/stalker/metro/fallout → survival-zone, space/sci-fi/ftl → space-travel, political/intrigue → political-intrigue, civilization/tribe/4x → civilization.

### 2. List available templates
```bash
bash .claude/additional/infrastructure/dm-campaign-rules.sh list
```

### 3. Display menu

```
================================================================
  ╔═══════════════════════════════════════════════════════════╗
  ║              CAMPAIGN RULES TEMPLATE                      ║
  ╚═══════════════════════════════════════════════════════════╝
================================================================

  [1] civilization        — Eras, population, tech tree
  [2] survival-zone       — Resources, morale, hazards
  [3] space-travel        — Ships, FTL, crew
  [4] horror-investigation — Sanity, clues, dread
  [5] political-intrigue  — Factions, influence, secrets

  ────────────────────────────────────────────────────────────
  💡 RECOMMENDED FOR THIS CAMPAIGN:
  Based on campaign name and genre, suggest which template fits.
  Write 1 sentence why it fits the vibe.
  ────────────────────────────────────────────────────────────
  Type a number to select, or ENTER to accept recommendation.
  Type "skip" to use standard D&D rules (no custom mechanics).

================================================================
```

### 4. Apply selected template
```bash
bash .claude/additional/infrastructure/dm-campaign-rules.sh apply <template-id>
```

This writes template metadata into `campaign-overview.json` under `campaign_rules_template`
and creates `campaign-rules.md` in the campaign folder.
The DM will load and enforce these rules every session via `/dm-continue`.

**If "skip"**: no campaign-rules.md needed. Standard D&D applies.

### 5. If user wants custom rules
If user describes custom mechanics not covered by templates:
- Generate a `campaign-rules.md` manually based on their description
- Follow the same section structure as built-in templates (eras/resources/combat/diplomacy etc.)

---

## PHASE 1.85: CUSTOM RULES
### 1. List available custom rules
```bash
bash .claude/additional/infrastructure/dm-campaign-custom-rules.sh list
```

### 2. Display menu

```
================================================================
  ╔═══════════════════════════════════════════════════════════╗
  ║              CUSTOM RULES                                 ║
  ╚═══════════════════════════════════════════════════════════╝
================================================================

  [1] realistic-progression  — Skill growth through action, no XP tables
  [2] russian-language       — All content in Russian

  ────────────────────────────────────────────────────────────
  💡 RECOMMENDED FOR THIS CAMPAIGN:
  Based on campaign genre, suggest which rules fit.
  Multiple rules can be applied — they stack.
  E.g. survival/STALKER → realistic-progression + russian-language.
  Write 1 sentence why each suggested rule fits the vibe.
  ────────────────────────────────────────────────────────────
  Type numbers to select (e.g. "1 2"), ENTER to skip.

================================================================
```

Get genre-based recommendation:
```bash
bash .claude/additional/infrastructure/dm-campaign-custom-rules.sh recommend "<genre>"
```

### 3. Apply selected rules
```bash
bash .claude/additional/infrastructure/dm-campaign-custom-rules.sh apply <rule-id>
```
Run once per selected rule. Rules are appended to campaign-rules.md with markers.

### 4. If "skip", no custom rules applied.

---

## PHASE 1.9: CURRENCY & CALENDAR
Configure campaign-specific currency and calendar systems. Both use the same pattern: config in `campaign-overview.json`, defaults if skipped.

### Currency

Ask the user what currency system fits the setting:

```
================================================================
  CURRENCY SYSTEM
  ────────────────────────────────────────────────────────────
  Default: D&D standard (copper/silver/gold, 1:10:100)

  Options:
  [1] D&D standard (cp/sp/gp)
  [2] Single currency (e.g. credits, caps, coins)
  [3] Custom — define your own denominations

  Type number or ENTER for default.
================================================================
```

- **D&D standard**: skip, default already works
- **Single currency**: write `"currency"` to campaign-overview.json with one denomination
- **Custom**: ask user for denomination names, symbols, exchange rates. Write to `"currency"` section

Format: `{"base": "<smallest_id>", "denominations": [{"id": "...", "name": "...", "symbol": "...", "rate": N}, ...]}`
Rates are relative to base (smallest = 1).

### Calendar

Ask the user what calendar system fits the setting:

```
================================================================
  CALENDAR SYSTEM
  ────────────────────────────────────────────────────────────
  Default: Earth standard (January-December, Mon-Sun)

  Options:
  [1] Earth standard (Gregorian)
  [2] Warhammer Imperial Calendar
  [3] Custom — define your own months and weekdays

  Type number or ENTER for default.
================================================================
```

- **Earth standard**: skip, default already works
- **Warhammer**: write Warhammer calendar config to `"calendar"` in campaign-overview.json
- **Custom**: ask user for month names + days per month, weekday names, epoch name. Write to `"calendar"` section

Format: `{"epoch": "...", "months": [{"id": "...", "name": "...", "days": N}, ...], "weekdays": ["...", ...], "year_zero_weekday": 0}`

Set initial date: `"current_date"` in campaign-overview.json.

### Auto-detect from genre
If campaign genre/setting suggests a specific system, recommend it:
- Warhammer/Old World → Warhammer calendar + D&D-like currency
- Sci-fi/Cyberpunk → single currency (credits) + Earth calendar
- Post-apocalyptic → single currency (caps/barter) + Earth calendar
- Historical → Earth calendar + period-appropriate currency
- Custom fantasy → ask user

---

## PHASE 2: TONE

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  CREATE YOUR WORLD
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

QUESTION 2 of 4: What's the tone of your adventure?

  1) Heroic    - Classic fantasy, good vs evil, heroes rise
  2) Gritty    - Dark, morally gray, survival matters
  3) Whimsical - Lighthearted, humor, fairy-tale vibes
  4) Epic      - Grand scale, world-shaking consequences
```

Ask the user directly with these options:
- **Heroic** - Classic good vs evil, brave heroes, epic quests
- **Gritty** - Moral ambiguity, harsh consequences, survival
- **Whimsical** - Humor, silly situations, fairy-tale atmosphere
- **Epic** - Grand scale, legendary deeds, world-changing events

Store the user's choice as `TONE`.

---

## PHASE 3: MAGIC LEVEL

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  CREATE YOUR WORLD
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

QUESTION 3 of 4: How common is magic?

  1) Rare      - Magic is mysterious, feared, or forgotten
  2) Uncommon  - Magic exists but practitioners are special
  3) Common    - Magic is part of everyday life
  4) Wild      - Magic is everywhere and unpredictable
```

Ask the user directly with these options:
- **Rare** - Magic is feared and mysterious; mages are legends
- **Uncommon** - Magic exists but casters are special; items are valuable
- **Common** - Magic shops exist, many know cantrips
- **Wild** - Magic saturates everything; unpredictable effects

Store as `MAGIC_LEVEL`.

---

## PHASE 4: SETTING TYPE

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  CREATE YOUR WORLD
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

QUESTION 4 of 4: What kind of setting?

  1) Medieval Village  - Small town, local threats
  2) Frontier Outpost  - Edge of civilization, wilderness
  3) City Streets      - Urban intrigue, factions, crime
  4) Ancient Ruins     - Exploration, lost civilizations
  5) Coastal Port      - Trade, pirates, sea adventure
  6) Surprise me!      - Random based on your answers
```

Ask the user directly with these options:
- **Medieval Village** - Classic small town with local threats and familiar faces
- **Frontier Outpost** - Edge of civilization, wilderness dangers, pioneer spirit
- **City Streets** - Urban intrigue, political factions, criminal underworld
- **Ancient Ruins** - Exploration focus, mysteries of lost civilizations
- **Coastal Port** - Trade hub, pirates, sea adventures, diverse travelers
- **Surprise me!** - Generate a setting based on tone and magic choices

Store as `SETTING_TYPE`.

---

## PHASE 4.5: WEIGHTED SCENARIO SECRETS

Use this phase when the player wants a surprise, mystery, procedural uncertainty, or a campaign whose hidden truth should emerge through play.

### 1. Establish the fixed premise

Write a short player-facing premise containing only facts that are true in every possible scenario: starting place, visible faction, immediate role, and ordinary situation. The premise must remain valid regardless of the hidden result.

### 2. Propose the primary-secret table

- Create 3-8 mutually exclusive hidden explanations tailored to the premise, tone, genre, and selected modules.
- Give each explanation an integer probability. The primary probabilities MUST total exactly 100%.
- Each result must materially change factions, motives, threats, or future revelations rather than merely changing cosmetic details.
- Show the table and its probabilities to the player before rolling. Let the player adjust or approve it unless they already delegated the distribution.

### 3. Propose independent complications

- Create 3-8 complications, each with its own percentage chance.
- Complications are independent boolean rolls and may occur together or not at all. They do NOT need to total 100%.
- State clearly which facts are guaranteed by the fixed premise and which are only possible complications.
- Prefer complications that create new decisions: intervention by another faction, quarantine, betrayal, awakening technology, a deadline, or an uneasy alliance.

### 4. Roll and persist without spoilers

After approval, make one hidden `1d100` roll for the primary table and one hidden `1d100` roll per complication:

```bash
bash tools/dm-roll.sh 1d100 --label "Hidden primary scenario"
bash tools/dm-roll.sh 1d100 --label "Hidden complication: <name>"
```

Map the primary roll to contiguous non-overlapping ranges covering 1-100. A complication occurs when its roll is less than or equal to its configured chance.

Persist the complete result before generating the world:

```bash
bash tools/dm-note.sh "dm_secret" "Primary scenario: <result>; roll=<N>; table=<ranges>"
bash tools/dm-note.sh "dm_secret" "Complication <name>: active|inactive; roll=<N>; chance=<P>%"
```

Never reveal a hidden roll, selected explanation, or inactive complication in player-facing narration. Reveal the truth only through earned clues, discoveries, faction actions, and consequences. If the player explicitly requests an open roll, show the roll and treat the result as player knowledge.

### 5. Generate from the hidden truth

Use the selected primary scenario and active complications to shape secret facts, NPC motives, plot hooks, consequences, and distant entities. Keep the opening scene consistent with the fixed premise and avoid immediately confirming the hidden explanation.

---

## CAMPAIGN DESIGN PRINCIPLES

Apply these principles throughout world and character creation:

1. **Use setup as Session Zero.** Establish the campaign premise, player roles,
   expectations, boundaries, and a possible end condition before detailed prep.
2. **Start small and build outward.** Create the smallest playable area that
   supports immediate decisions. Expand the world when player choices reveal
   which people, places, and conflicts matter.
3. **Prepare situations, not predetermined plots.** Give factions and important
   NPCs goals, resources, pressures, relationships, and a next action if the
   players do nothing. Never assume a required sequence of player actions.
4. **Let content follow function.** Create NPCs, quests, locations, and
   consequences in quantities justified by the starting situation. A
   ready-to-play campaign must include NPCs, active quests, and scheduled
   consequences, but never add filler to satisfy an entity count.
5. **Build player investment.** Tie hooks to declared player roles and, after
   character creation, connect or revise world entities around character
   backgrounds, relationships, and goals.
6. **Provide multiple paths to essential discoveries.** Mysteries should
   normally provide three independent clues for each conclusion that play
   depends on. This is redundancy for player choice, not a quota for quests,
   locations, or NPCs.
7. **Plan an ending without scripting the route.** Define what victory, defeat,
   or campaign closure could mean, while allowing play to determine how the
   campaign reaches that state.

---

## PHASE 5: WORLD GENERATION

Display progress:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  GENERATING YOUR WORLD
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Campaign: "<CAMPAIGN_NAME>"
Tone: <TONE> | Magic: <MAGIC_LEVEL> | Setting: <SETTING_TYPE>

Building your world...

  ├─ Creating starting location.... [working]
  ├─ Populating with NPCs.......... [working]
  ├─ Weaving plot threads.......... [working]
  └─ Establishing connections...... [working]
```

### Generate Starting Location

Based on the setting type, create the starting location with full detail:
- 100+ word description with sensory details
- The named NPCs immediately required by the starting situation
- Connections to adjacent areas
- Local secrets and current events

```bash
bash tools/dm-location.sh add "[Starting Location Name]" "center of the settlement"
bash tools/dm-location.sh describe "[Starting Location Name]" "[detailed description]"
```

### Generate Supporting Locations

Create only the connected locations needed to support immediate choices and one
or more clear directions for later expansion. A useful supporting location
provides at least one concrete function, such as:
- Services or commerce
- Authority or knowledge
- Danger or mystery
- A faction presence
- A route into the next situation

```bash
bash tools/dm-location.sh add "[Location Name]" "[position relative to start]"
bash tools/dm-location.sh connect "[Start]" "[Location]" "[path description]"
```

### Generate NPCs

Create the interconnected NPCs required to make the starting situation
playable. Do not target a fixed count. Every created NPC must have:
- A current goal and something they can do to pursue it
- A relationship, dependency, or conflict with another world entity
- Information, authority, resources, danger, or emotional relevance
- A reason the players may choose to engage with them

Possible functions include a conflicting patron, service provider, source of
information, faction representative, antagonist, ally, or local personality.
Combine functions when one strong NPC can do the work of several shallow ones.

```bash
bash tools/dm-npc.sh create "[Name]" "[description]" "[attitude]"
bash tools/dm-npc.sh locate "[Name]" "[location]"
```

### Generate Plot Hooks

Create the actionable quests that emerge from the starting conflicts. Do not
target a fixed number or require local, regional, and campaign-long tiers when
the premise does not need them. A campaign can begin with one sharp problem or
several competing missions.

Every quest must define:
- The situation and relevant actors, without prescribing the solution
- Concrete stakes and what changes if the players ignore it
- At least one trackable objective
- An explicit XP reward proportional to the complete quest, not each objective
- A connection to a player role, background, relationship, or declared goal

For mysteries, record each essential conclusion and provide multiple
independent discovery paths, normally three clues per required conclusion.

```bash
bash tools/dm-plot.sh add "[Quest name]" --type side --desc "[situation, stakes, and ignored outcome]" --xp 100
bash tools/dm-plot.sh objective "[Quest name]" add "[objective]"
```

### Schedule Consequences

Schedule consequences for independent actors, threats, or opportunities that
can advance without player intervention. Do not target a fixed count. Each
consequence must follow from the prepared situation and change future choices
instead of merely adding unrelated activity.

```bash
bash tools/dm-consequence.sh add "[Actor advances a goal]" "next session" --hours 8
```

### Initialize Player Node

Create an empty player node in world.json for character creation to fill later:

```bash
bash tools/dm-world.sh add-node "player:active" --name "Player" --type player --data '{"level": 1, "hp": {"current": 10, "max": 10}, "ac": 10, "money": 0, "xp": {"current": 0, "next_level": 300}, "stats": {}, "skills": {}, "save_proficiencies": [], "conditions": [], "equipment": {"armor": {}, "weapons": []}, "custom_stats": {}, "timed_effects": []}'
```

### Initialize Economy Node

Create economy node for recurring mechanics (expenses, income, production, random events):

```bash
bash tools/dm-world.sh add-node "misc:economy" --name "Economy & Events" --type misc --data '{"expenses": [], "income": [], "production": [], "random_events": {"enabled": false}}'
```

### Setup Custom Stats (if campaign template defines them)

Based on campaign rules template, define relevant custom stats:

```bash
# Examples by genre:
# Survival: hunger, thirst, morale, radiation
bash tools/dm-world.sh custom-stat-define hunger --value 100 --max 100 --min 0 --rate -5
# Horror: sanity, dread
bash tools/dm-world.sh custom-stat-define sanity --value 100 --max 100 --min 0 --rate -1
# Dark fantasy: dark_power, suspicion
bash tools/dm-world.sh custom-stat-define dark_power --value 0 --max 100 --min 0 --rate -0.08
```

### Update Status

As each element completes:
```
  ├─ Creating starting location.... done
  ├─ Populating with NPCs.......... done (situation-driven roster)
  ├─ Weaving plot threads.......... done (active conflicts)
  └─ Establishing connections...... done
```

---

## PHASE 6: UPDATE CAMPAIGN OVERVIEW

```bash
CAMPAIGN_DIR=$(bash tools/dm-campaign.sh path)

uv run python -c "
import json
from datetime import datetime

# Load existing campaign overview
with open('$CAMPAIGN_DIR/campaign-overview.json', 'r') as f:
    data = json.load(f)

# Update with world-building details
data.update({
    'current_date': '1st day of Springrise, Year 1000',
    'time_of_day': 'Morning',
    'player_position': {
        'current_location': '[Starting location name]',
        'previous_location': None
    },
    'current_character': None,
    'session_count': 0
})

with open('$CAMPAIGN_DIR/campaign-overview.json', 'w') as f:
    json.dump(data, f, indent=2)
"
```

---

## PHASE 7: INITIALIZE SESSION LOG

```bash
CAMPAIGN_DIR=$(bash tools/dm-campaign.sh path)
cat > "$CAMPAIGN_DIR/session-log.md" << EOF
# Session Log - [CAMPAIGN_NAME]

**Tone**: [TONE]
**Magic Level**: [MAGIC_LEVEL]
**Setting**: [SETTING_TYPE]
**Started**: $(date -u +"%Y-%m-%d")

---

## Session 0: World Creation
**Date**: $(date -u +"%Y-%m-%d %H:%M:%S UTC")

### World Summary
- **Starting Location**: [Location name]
- **Initial NPCs**: [List the NPCs created for the starting situation]
- **Active Quests**: [List the quests created from active conflicts]

Ready for character creation.

---
EOF
```

---

## PHASE 8: DISPLAY SUMMARY

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  YOUR WORLD IS READY!
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Campaign: "[CAMPAIGN_NAME]"
Tone: [TONE] | Magic: [MAGIC_LEVEL] | Setting: [SETTING_TYPE]

Starting Location: [Location Name]
   [First sentence of description]

Key NPCs:
   • [NPC 1] - [role]
   • [NPC 2] - [role]
   • [...] - [include only NPCs currently relevant to play]

Active Plot Hooks:
   • [Quest]: [One-line situation and stakes]
   • [...] [include every active starting quest]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## PHASE 9: TRANSITION TO CHARACTER CREATION

Display:

```
Your world awaits its hero!

Now let's create your character...
```

Then automatically run `/create-character` to guide the user through character creation.

---

## ERROR RECOVERY

**Campaign already exists**: Offer to switch, rename, or recreate

**NPC/location creation fails**: Retry with different name

**JSON file corruption**: Reinitialize empty file structure

---

## COMPLETION CHECKLIST

Before transitioning to character creation, verify:

- [ ] world.json exists with player node, locations, NPCs, quests
- [ ] Player node in world.json (player:active)
- [ ] Economy node in world.json (`misc:economy`)
- [ ] Starting location plus only the supporting locations needed for play
- [ ] All locations connected via paths
- [ ] Starting NPCs have goals, relationships, relevance, and locations
- [ ] Active conflicts are tracked as quests with objectives
- [ ] Relevant independent actors and threats have scheduled consequences
- [ ] No filler entities were created to satisfy a numeric quota
- [ ] Essential discoveries have multiple independent paths
- [ ] Character backgrounds and goals are connected to world entities
- [ ] Custom stats defined (if campaign template requires them)
- [ ] Session log initialized
- [ ] Campaign overview updated with settings
- [ ] Narrator style selected or skipped
- [ ] Campaign rules template applied or skipped
- [ ] Custom rules selected and applied or skipped
- [ ] Currency system configured or default accepted
- [ ] Calendar system configured or default accepted
- [ ] Module-specific creation steps completed
