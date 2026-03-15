## id
roguelike-missions

## name
Roguelike: Base & Missions

## description
XCOM/Darkest Dungeon/FTL universal template: a home base where you heal, upgrade, and recruit — then deploy on missions with clear objectives, loot, and consequences. Death is real. Every mission is a story. Configurable for any setting.

## genres
roguelike, tactical, missions, base-management, squad, progression, permadeath

## recommended_for
Any setting where gameplay loops between a safe hub and dangerous deployments. Works for: military sci-fi (XCOM), post-apocalyptic (STALKER), dark fantasy (Darkest Dungeon), cyberpunk, medieval mercenary company, space exploration, zombie survival — anything with a base and field ops.

## configuration

During campaign creation (`/new-game`), the DM and player define these setting-specific parameters:

```
SETTING:          [genre/world — e.g. "STALKER Zone", "Space Marines", "Witcher School"]
BASE_NAME:        [home base — e.g. "Outpost", "Ship", "Guild Hall"]
CURRENCY:         [gold/caps/credits/etc]
SQUAD_MODE:       solo | duo | squad(3-4) | platoon(5+)
PERMADEATH:       true | soft (mission restart) | legacy (inherit some progress)
DIFFICULTY:       brutal | hard | standard
META_TREE:        [what upgrades between missions — tech/base rooms/faction rep/etc]
MISSION_TYPES:    [list of mission archetypes for this setting]
THREAT_NAME:      [what the overarching danger is — "Zone expansion", "Alien invasion", etc]
THREAT_ESCALATION: true | false
```

These values are stored in `campaign-overview.json` under `campaign_rules.roguelike_config` and referenced throughout play.

## rules

### Core Loop

```
BASE PHASE → BRIEFING → DEPLOYMENT → MISSION → EXTRACTION → DEBRIEF → BASE PHASE
```

This loop repeats. Every cycle = one session or more (long missions span multiple sessions).

---

### BASE PHASE

The base is a safe zone. No combat, no random encounters. Time passes freely.

#### Available Actions (per base visit)

| Action | What it does |
|--------|-------------|
| **Rest** | Full HP/resource recovery. Cost: time (setting-dependent) |
| **Shop** | Buy/sell gear, consumables, ammo. Prices scale with difficulty |
| **Recruit** | Hire NPCs for squad. Cost varies. NPCs have stats, personality, loyalty |
| **Upgrade** | Spend resources on META_TREE (base rooms, tech, faction rep) |
| **Train** | Improve a skill or stat. 1 training per base visit. Diminishing returns |
| **Mission Board** | View available missions. Pick one. Prepare loadout |
| **Intel** | Gather info on next mission (scout reports, NPC rumors). Reduces unknown risk |
| **Craft** | Build items from salvage/components (if setting supports it) |

#### Base Upgrades (META_TREE)

Base starts minimal. Upgrades unlock new actions and bonuses. Structure is setting-dependent but follows tiers:

| Tier | Cost multiplier | Examples |
|------|----------------|---------|
| 1 | 1x | Basic medbay (+25% heal speed), armory (unlock weapon tier 2), workshop (basic crafting) |
| 2 | 3x | Advanced medbay (revive downed), radar (reveal mission intel), training ground (+1 stat cap) |
| 3 | 8x | Lab (research enemy weaknesses), black market (rare items), war room (squad size +1) |
| 4 | 20x | Setting-specific endgame upgrades |

Each upgrade costs CURRENCY + SALVAGE (mission loot). DM defines exact costs during campaign creation.

#### Recruitment

NPCs available for hire rotate after each mission. Pool depends on base reputation and upgrades.

| Quality | Cost | Stats | Loyalty |
|---------|------|-------|---------|
| Rookie | 1x | Basic, 1 skill | Low — may flee at <25% HP |
| Veteran | 3x | Solid, 2 skills | Medium — holds the line |
| Elite | 8x | Strong, 3 skills + special ability | High — follows orders |
| Named/Unique | Quest reward | Exceptional | Story-dependent |

NPCs have **Loyalty** (0-100). Below 30: may refuse dangerous orders. Below 10: desertion risk. Loyalty rises from shared victories (+5-10), fair loot split (+5), saving their life (+15). Drops from: casualties in squad (-10), no pay (-5/mission), reckless orders (-10).

---

### MISSION BOARD

Missions appear on the board. 2-4 available at a time. Board refreshes after completing/failing a mission.

#### Mission Card Format

```
================================================================
  MISSION: [Name]
  ────────────────────────────────────────────────────
  Type: [Exterminate / Retrieve / Escort / Recon / Defend / Sabotage / Boss]
  Size: [S / M / L]
  Threat: [★☆☆☆☆ to ★★★★★]
  ────────────────────────────────────────────────────
  OBJECTIVE: [clear description of success condition]
  LOCATION: [where]
  INTEL: [what you know — may be incomplete]
  REWARD: [currency + items + XP + reputation]
  PENALTY: [what happens if you fail or abandon]
  TIME LIMIT: [none / X turns / before event Y]
================================================================
```

#### Mission Sizes

| Size | Duration | Encounters | Complexity |
|------|----------|------------|------------|
| **S** (Quick Op) | 1-2 encounters | 1 combat or 1 objective | Straightforward. In and out |
| **M** (Standard) | 3-5 encounters | 2-3 combats + 1-2 objectives | Choices matter. Side objectives |
| **L** (Campaign) | 6+ encounters | Multiple combats + puzzle/story | Multi-part. Rest points inside. Boss at end |

#### Mission Types

| Type | Objective | Typical hazard |
|------|-----------|---------------|
| **Exterminate** | Kill all hostiles in area | Waves, reinforcements |
| **Retrieve** | Find and extract target item | Traps, guardians, time pressure |
| **Escort** | Get VIP from A to B alive | Ambushes, VIP is fragile |
| **Recon** | Explore area, gather intel, return | Stealth-focused, detection = combat |
| **Defend** | Hold position for X rounds | Waves from multiple directions |
| **Sabotage** | Destroy/disable target | Infiltration, alarm systems |
| **Boss** | Defeat unique powerful enemy | Boss mechanics, phases, arena hazards |
| **Rescue** | Extract captured NPC/ally | Time limit, guards, escape route |

DM customizes types per setting during campaign creation.

---

### DEPLOYMENT

Before mission start:

1. **Select squad** (if SQUAD_MODE allows)
2. **Loadout check** — equip gear, consumables, ammo from inventory
3. **Intel review** — what you know about the mission
4. **Point of no return** — once deployed, you're committed. No shop access until extraction

#### Loadout Weight

Total carry weight affects performance:
- **Light** (<50% capacity): no penalty, +1 initiative
- **Normal** (50-80%): no penalty
- **Heavy** (80-100%): -1 initiative, -5 speed
- **Overloaded** (>100%): -2 to all physical rolls, half speed

---

### MISSION EXECUTION

#### Structure

Every mission is a sequence of **rooms/encounters**. DM generates them based on mission type and size.

```
[Entry] → [Encounter 1] → [Encounter 2] → ... → [Objective] → [Extraction]
```

Between encounters:
- Short rest possible (if no time pressure)
- Use consumables
- Reposition / plan next move

#### Encounter Types

| Type | What happens |
|------|-------------|
| **Combat** | Enemies. Roll initiative. Fight |
| **Hazard** | Environmental danger — traps, anomalies, terrain. Skill checks to navigate |
| **Social** | NPC interaction — negotiate, intimidate, deceive. May avoid combat |
| **Loot** | Cache/stash found. Roll loot table or DM places specific items |
| **Event** | Story beat — narrative choice with consequences |
| **Rest Point** | Safe spot (M/L missions only). Short rest. Resupply from what you carry |

#### Fog of War

Players don't see the full mission map. Each room/area is revealed on entry. Intel (from base) may reveal some rooms in advance.

#### Retreat

At any point during a mission, the squad can attempt retreat:
- **Ordered retreat**: move back through cleared rooms. No penalty except mission failure
- **Emergency retreat**: DC 14 + number of enemies nearby. Failure = opportunity attacks from all enemies
- **Failed mission**: lose mission reward. May lose reputation. Board refreshes

---

### COMBAT RULES

Standard D&D 5e combat with these mission-specific additions:

#### Cover System

| Cover | AC bonus | Available |
|-------|----------|-----------|
| None | +0 | Open ground |
| Half | +2 | Low wall, furniture, thin tree |
| Three-quarters | +5 | Doorway, thick wall with gap, vehicle |
| Full | Untargetable | Behind solid wall (can't attack either) |

Taking cover = free action on your turn. Leaving cover to attack = lose cover until next turn.

#### Ammo Tracking

If setting uses firearms/ranged:
- Each weapon has magazine size
- Track shots fired
- Reload = 1 action (or bonus action with proficiency)
- Running out mid-fight = switch weapon or melee

#### Morale (Enemies)

Enemies have morale. When conditions are met, DM rolls morale check (DC 10 + CHA mod of scariest party member):
- Lost 50% of their force
- Leader killed
- Surprised / flanked

Failed morale = enemies flee, surrender, or reposition defensively.

#### Down But Not Out

At 0 HP:
- **Player character**: death saves as normal. 3 fails = DEAD (permadeath or mission restart per config)
- **Squad NPC**: 0 HP = incapacitated. Stabilize with DC 10 Medicine or medkit. If not stabilized in 3 rounds = dead permanently
- **Carrying wounded**: half speed, one hand occupied. Can't fight while carrying

---

### EXTRACTION

Mission objective complete (or retreat called). Getting out:

- **Clean extraction**: objective done, path clear. Walk out. Full reward
- **Hot extraction**: enemies pursuing. Skill challenge (3 successes before 2 failures) or running fight to exit
- **Failed extraction**: didn't reach exit. Captured / stranded (DM decides consequences)

---

### DEBRIEF

After returning to base:

```
================================================================
  MISSION DEBRIEF: [Mission Name]
  ────────────────────────────────────────────────────
  Status: [SUCCESS / PARTIAL / FAILED]
  ────────────────────────────────────────────────────
  Casualties: [names of dead/wounded]
  Loot: [items found]
  Reward: [currency + XP + reputation]
  Intel: [new information discovered]
  Consequence: [what changes in the world]
  ────────────────────────────────────────────────────
  [Notable moments from the mission]
================================================================
```

#### XP Distribution

| Event | XP |
|-------|-----|
| Mission complete (S) | 50-100 |
| Mission complete (M) | 150-300 |
| Mission complete (L) | 400-800 |
| Each enemy killed | Standard CR XP |
| Bonus objective | +25-50% mission XP |
| Flawless (no one downed) | +50% mission XP |
| Creative solution | +25% mission XP (DM discretion) |

XP splits evenly across surviving squad.

---

### DIFFICULTY SCALING

#### Threat Escalation (if enabled)

A global **THREAT_LEVEL** starts at 1 and increases over time:
- +1 after every 3 completed missions
- +1 after a failed mission (the enemy adapts)
- +1 on story milestones

Effects per threat level:
- Enemy HP: ×(1 + THREAT_LEVEL × 0.1)
- Enemy count: +1 per 3 threat levels
- New enemy types unlock at thresholds
- Mission board shows harder missions

#### Difficulty Presets

| Setting | Enemy HP | Prices | Healing | Permadeath |
|---------|----------|--------|---------|------------|
| **Brutal** | ×1.3 | ×1.5 | 50% effectiveness | Hard — dead is dead |
| **Hard** | ×1.1 | ×1.2 | 75% effectiveness | Soft — restart mission or new character |
| **Standard** | ×1.0 | ×1.0 | 100% | Soft — restart mission |

---

### PERMADEATH MODES

| Mode | On death |
|------|----------|
| **true** | Character gone. New character from scratch. Base/meta progress preserved |
| **soft** | Restart current mission from base. Lose mission consumables spent. Keep character |
| **legacy** | New character inherits: 25% gold, 1 item, base stays, reputation halved |

---

### LOOT SYSTEM

After each combat/encounter, DM rolls loot:

```bash
bash tools/dm-roll.sh "1d20" --label "Loot quality" --dc 10
```

| Roll | Quality | Examples |
|------|---------|---------|
| 1-5 | Nothing | Pockets empty |
| 6-10 | Junk | Salvage components, 1d6 currency |
| 11-15 | Standard | Ammo, consumable, 2d6 currency |
| 16-19 | Good | Weapon/armor, rare consumable, 4d6 currency |
| 20 | Excellent | Unique/rare item, large currency haul |

Mission-specific loot tables override generic rolls. Boss loot is always guaranteed and curated.

#### Salvage

Junk items can be broken down into **salvage** — the universal crafting/upgrade currency alongside gold:
- Salvage is used for: base upgrades, crafting, weapon mods
- Heavier items = more salvage but more carry weight
- Decision: carry loot vs carry ammo/meds

---

### CAMPAIGN PROGRESSION

#### Story Arcs

Missions aren't random — they form arcs:

```
[Intro missions (S)] → [Rising action (M)] → [Climax mission (L/Boss)] → [New arc]
```

Each arc has:
- A narrative thread connecting missions
- Escalating difficulty
- A boss or major event at the end
- Consequences that carry to next arc

#### Victory Conditions

Defined during campaign creation. Examples:
- **Survive X missions** — endurance run
- **Defeat final boss** — story climax
- **Reach reputation threshold** — political/faction victory
- **Accumulate X resources** — economic victory
- **Discover the truth** — mystery/investigation arc

---

### SESSION FLOW SUMMARY

```
1. BASE PHASE
   - Rest / heal
   - Shop / craft / upgrade
   - Check mission board
   - Select mission + loadout

2. BRIEFING
   - Mission card displayed
   - Intel review
   - Last chance to prepare

3. DEPLOYMENT
   - Travel to mission area (may have encounters)
   - Point of no return

4. MISSION
   - Room-by-room / encounter-by-encounter
   - Combat, hazards, events, loot
   - Objective completion

5. EXTRACTION
   - Clean or hot exit
   - Carry wounded / loot

6. DEBRIEF
   - Results displayed
   - XP / loot / reputation distributed
   - Story consequences revealed

7. → Back to BASE PHASE
```
