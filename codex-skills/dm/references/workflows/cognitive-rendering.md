# 🧠 COGNITIVE RENDERING DISTANCE - World Detail Management

A systematic approach to world-building that provides rich detail for immediate areas while maintaining mystery and expansion potential for distant regions.

---

## CORE CONCEPT

Think of the world like a video game that renders detail based on proximity to the player. The closer something is to current action, the more detail it needs.

```
IMMEDIATE (100% Detail) ← ADJACENT (60% Detail) ← DISTANT (20% Detail) ← RUMORED (5% Detail)
        📍 Players Here          🚶 Can reach today        🐎 Days away           🌌 Legendary
```

---

## RENDERING LAYERS

### LAYER 0: IMMEDIATE ZONE (Current Location)
**Detail Level: 100% - Full Sensory Immersion**

Requirements:
- 100+ words of description
- All 5 senses engaged
- 3+ named NPCs with full personalities
- Interior and exterior described
- Hidden areas/secrets defined
- Current events happening NOW
- Weather, time of day effects
- Ambient sounds specified

Example:
```
The Crimson Drake Inn (118 words):
"Warm firelight dances across worn oak beams, casting shifting shadows over
the crowded common room. The air hangs thick with pipe smoke and the rich
aroma of Marta's famous lamb stew. Raucous laughter erupts from the corner
table where off-duty guards throw dice, their mail shirts clinking with each
enthusiastic gesture. Behind the bar, Garrett polishes a mug with practiced
efficiency, his one good eye scanning for trouble while his scarred hand never
stops moving. A bard strums lazily near the hearth, her melody barely audible
over the din. Upstairs, narrow corridors lead to six modest rooms, while a
locked door beside the kitchen conceals stairs to the wine cellar—and perhaps
more, if the rumors are true."
```

### LAYER 1: ADJACENT ZONE (Immediate Connections)
**Detail Level: 60% - Clear Features**

Requirements:
- 50-80 words of description
- Major features defined
- 1-2 named NPCs OR unnamed but described groups
- Purpose and atmosphere clear
- How to get there specified
- Current state/situation mentioned
- One interesting detail or hook

Example:
```
Temple of the Dawn (63 words):
"Rising from the town square's eastern edge, the Temple of the Dawn's white
marble spire catches first light each morning. Brother Marcus tends the
eternal flame while Sister Sarah offers healing to those who can donate.
The fountain in its courtyard runs clean and pure, though lately the water
has taken on a faint silver sheen that troubles the clergy. Stone steps
worn smooth by centuries of pilgrims lead up from the square."
```

### LAYER 2: DISTANT ZONE (Travel Required)
**Detail Level: 20% - Key Facts Only**

Requirements:
- 20-30 words of description
- General reputation/purpose
- Distance and direction
- One notable feature
- Why someone might go there
- No specific NPCs yet

Example:
```
The Thornwood (27 words):
"Three hours north, the Thornwood's twisted trees harbor wolves and worse.
Hunters venture there for rare shadowbark, worth its weight in silver,
but many don't return."
```

### LAYER 3: RUMORED ZONE (Legendary/Mythical)
**Detail Level: 5% - Mysteries and Legends**

Requirements:
- 10-15 words of description
- Exists in rumors only
- Contradictory information OK
- No confirmed location
- Massive plot potential

Example:
```
The Floating City (13 words):
"Merchants whisper of a city in the clouds, appearing only during certain celestial alignments."
```

---

## RENDERING TRIGGERS

### When to Increase Detail Level:

**DISTANT → ADJACENT**:
- Players announce intention to travel there
- NPC from that location arrives
- Event there affects current location

**ADJACENT → IMMEDIATE**:
- Players actually travel there
- Extended scene occurs there
- Becomes party's base of operations

**RUMORED → DISTANT**:
- Players acquire map or directions
- Multiple sources confirm existence
- Quest explicitly points there

### Detail Rendering Process:

1. **Identify Current Layer**
   - Where is it relative to players?
   - How much do we already know?

2. **Search for Connections**
   ```bash
   dm-search.sh "[location type] [related elements]"
   ```

3. **Add Appropriate Detail**
   - IMMEDIATE: Full sensory, multiple NPCs, secrets
   - ADJACENT: Clear purpose, key NPCs, one hook
   - DISTANT: Reputation, rumors, general danger/reward
   - RUMORED: Contradictions, legends, mystery

4. **Save to World State**
   ```bash
   bash tools/dm-location.sh describe "[Location]" "[appropriate detail level]"
   ```

---

## PRACTICAL EXAMPLES

### Starting a Campaign
```
IMMEDIATE: The Silver Stag Inn (party starts here)
ADJACENT: Market Square, Temple, Guard Barracks, Docks
DISTANT: Oldwood Forest, Mountain Pass, Ruined Tower
RUMORED: The Sunken City, Dragon's Lair
```

### After 3 Sessions (Party moved to Docks)
```
IMMEDIATE: The Docks (now fully detailed)
ADJACENT: Harbor Master's Office, The Siren's Call Tavern, Warehouse District
DISTANT: Smuggler's Cove, Lighthouse Island
RUMORED: Ghost Ship, Mermaid Kingdom
(Previous IMMEDIATE becomes ADJACENT)
```

### Expanding Outward
When party heads to Oldwood Forest:
- Oldwood moves from DISTANT → IMMEDIATE
- Add ADJACENT: Ranger Camp, Druid Grove, Bandit Fort
- Add DISTANT: Elven Realm, Dark Heart of the Forest
- Previous areas step back one layer

---

## WORLD BUILDER INSTRUCTIONS

When using world-builder agents with cognitive rendering:

### For IMMEDIATE Locations:
```
"Create [location] where the party currently is. Include full sensory details,
3+ named NPCs with personalities, interior/exterior descriptions, secrets,
and current events. Minimum 100 words. Draw inspiration from [source material]."
```

### For ADJACENT Locations:
```
"Create [location] connected to [immediate location]. Include major features,
1-2 key NPCs or groups, clear purpose, and one interesting hook. 50-80 words.
Style: [campaign tone]."
```

### For DISTANT Locations:
```
"Create [location] that's [distance] from [current area]. Include general
reputation, why someone might go there, and one notable feature. 20-30 words.
Keep mysterious but intriguing."
```

### For RUMORED Locations:
```
"Create legendary [location] that exists only in rumors. Include contradictory
information and mystery. 10-15 words. Should feel mythical and unreachable."
```

---

## BENEFITS OF COGNITIVE RENDERING

1. **Reduces Overwhelming Detail**: Players aren't bombarded with information about places they can't reach yet

2. **Maintains Mystery**: Distant places remain intriguing rather than fully mapped

3. **Efficient Prep**: Detail only what's needed for current/next session

4. **Natural Exploration**: World reveals itself as players explore

5. **Flexible Canon**: Distant places can be adjusted based on campaign needs

6. **Player Agency**: Their choices determine what gets detailed

---

## RENDERING CHECKLIST

When expanding your world, ask:

- [ ] How far is this from current player location?
- [ ] What layer should this be in?
- [ ] Have I provided appropriate detail for its layer?
- [ ] Are there enough ADJACENT locations for player choice?
- [ ] Do DISTANT locations provide future hooks?
- [ ] Are RUMORED locations maintaining mystery?
- [ ] Should any locations shift layers based on events?

---

## QUICK REFERENCE

| Layer | Distance | Words | NPCs | Secrets | Tool Priority |
|-------|----------|-------|------|---------|---------------|
| IMMEDIATE | Here | 100+ | 3+ named | Yes | Full detail |
| ADJACENT | <1 day | 50-80 | 1-2 | Hooks | Major features |
| DISTANT | Days | 20-30 | None | Rumors | Reputation only |
| RUMORED | Unknown | 10-15 | None | Mystery | Contradictions |

Remember: The world doesn't need to be fully detailed—it needs to FEEL fully detailed from where the players stand!