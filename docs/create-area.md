# World-Builder Area Creation Guide

When you need to expand the game world with new areas, follow this workflow using multiple world-builder agents in parallel.

## CRITICAL FIRST STEP: Enhance Current Location

**BEFORE creating any new areas, ALWAYS check the player's current location:**

1. If the current location description is less than 100 words, that becomes your FIRST priority
2. Use a dedicated world-builder agent to enhance the current location with:
   - Rich atmospheric description (minimum 150-200 words)
   - Incorporation of lore-booster atmospheric elements
   - Connection to campaign themes and current events
   - Sensory details (sights, sounds, smells)
   - Time-of-day specific elements
   - Hints at deeper mysteries

### Example Current Location Enhancement:
```
FIRST: Use the lore-booster tool to search for atmospheric details about "[current location type] [campaign theme] [current time/event]".

Enhance the existing [Current Location Name] description.

CONTEXT: [Player just arrived here / Current events / Time of day]

SCOPE: Enhance ONLY the existing location description to be rich and atmospheric. Do NOT create new locations or NPCs.

REQUIREMENTS:
- Expand description to 150-200 words minimum
- Include sensory details (what characters see, hear, smell)
- Reference current events (tournament, crisis, etc.)
- Incorporate lore-booster atmospheric elements
- Maintain consistency with existing connections

TONE: [Campaign tone matching existing world]
```

## Workflow Order

1. **FIRST**: Enhance current player location if needed (see above)
2. **SECOND**: Enhance any connected locations that lack detail
3. **THIRD**: Create new areas expanding outward from player location
4. **ALWAYS**: Work from the player's position outward, like ripples in a pond

## Pre-Creation Analysis (Required)

Before launching world-builder agents, gather context:

```bash
# 1. Search for relevant world facts
bash tools/dm-search.sh "[area type]"
bash tools/dm-search.sh "[nearby location]"
bash tools/dm-search.sh "[relevant faction/theme]"

# 2. Check active consequences that might affect the area
bash tools/dm-consequence.sh check

# 3. Note any world constraints (from facts.json):
# - Resource shortages (materials, food, magic)
# - Political tensions (conflicts, occupation, rebellion)
# - Environmental hazards (disasters, curses, invasions)
# - Economic conditions (trade routes, prosperity/poverty)
```

## World-Builder Agent Instructions Template

Use this template for EACH agent, customizing the specifics:

```
FIRST: Use the lore-booster tool to search for atmospheric and contextual details about "[search term relevant to your area]". Incorporate these details into your creation.

Create [specific node type] for [location name] in [parent area].

CONTEXT: [2-3 sentences about the current world state that affects this area. Include relevant facts like resource shortages, political situations, recent events, or environmental conditions that would impact how this area functions.]

SCOPE: Build ONLY the following elements:
- [Specific location 1]
- [Specific location 2]
- [2-3 specific NPCs with roles]
- [1-2 relevant facts]
- [Optional: 1 consequence if appropriate]

BOUNDARIES: Stay within [specific geographic limit]. Do not create anything beyond [boundary description]. Connect only to [existing location names].

TONE: [Campaign tone - gritty, high fantasy, cosmic horror, etc.]
```

## Parallel Execution Pattern

Launch 3-4 agents simultaneously for efficient world-building:

### Example: Creating a Commercial District

```python
# Agent 1: Commercial Core
"FIRST: Use the lore-booster tool to search for atmospheric and contextual details about '[relevant theme] [location type] [current crisis]'. Incorporate these details into your creation.

Create the merchant quarter for [District Name] of [City Name].

CONTEXT: [Current crisis/shortage affecting commerce]. [Political/social tensions]. [Recent events bringing opportunity/danger to merchants].

SCOPE: Build ONLY:
- The [Struggling Business] ([business owner dealing with crisis])
- [Information Hub Location] ([role in community])
- [Business Owner NPC] ([specific problem they face])
- [Information Broker NPC] ([their specialty])
- Fact: [Economic condition reflecting crisis]
- Consequence: [Business owner's motivation/need]

BOUNDARIES: Stay within [specific geographic boundaries]. Connect only to [existing location names].

TONE: [Campaign tone description]"

# Agent 2: Underworld Element
"FIRST: Use the lore-booster tool to search for atmospheric and contextual details about '[criminal organization] [opposing faction]'. Incorporate these details into your creation.

Create the criminal element for [District Name]'s [back areas].

CONTEXT: [Law enforcement response to current crisis]. [How crisis creates black market opportunities]. [Why current events make good targets available].

SCOPE: Build ONLY:
- The [Criminal Establishment] ([type of den/hideout])
- [Illegal Operation Location] ([hidden facility])
- [Criminal Leader NPC] ([their specialty/trade])
- [Information Broker NPC] ([what they know])
- Fact: [Authority limitation/blind spot]
- Consequence: [Criminal's knowledge/connection]

BOUNDARIES: Stay within [hidden areas between major locations]. Connect only to [existing underground/shadow locations].

TONE: [Criminal atmosphere with supernatural/political undertones]"

# Agent 3: Religious/Mystical
"FIRST: Use the lore-booster tool to search for atmospheric and contextual details about '[religious institution] [opposing mystical force]'. Incorporate these details into your creation.

Create the spiritual quarter for [District Name].

CONTEXT: [How current crisis affects faith/spirituality]. [Religious leaders' struggles with current events]. [Renewed interest in old/alternative spirituality].

SCOPE: Build ONLY:
- [Multi-faith or Specific Temple] ([community role])
- The [Mystical Service Provider] ([type of mystic])
- [Religious Leader NPC] ([their concern/struggle])
- [Mystic NPC] ([their supernatural insight])
- Fact: [Spiritual/supernatural manifestation]
- Consequence: [Religious figure's secret willingness to help]

BOUNDARIES: Stay within [religious district], between [boundary locations]. Connect only to [existing spiritual/community locations].

TONE: [Spiritual atmosphere with darkness/light struggle]"
```

## Node Types for Parallel Creation

When dividing an area, use these complementary node types:

1. **Commercial/Trade** - Shops, smithies, markets, inns
2. **Residential** - Homes, apartments, neighborhoods  
3. **Criminal/Underground** - Thieves' dens, black markets, hideouts
4. **Religious/Mystical** - Temples, shrines, mystic shops
5. **Civic/Military** - Guard posts, courts, administrative
6. **Entertainment** - Taverns, fighting pits, theaters
7. **Industrial** - Workshops, warehouses, crafthalls

## Integration Requirements

Each agent must receive these integration instructions:

1. **Use lore-booster first** for atmospheric consistency
2. **Reference existing NPCs** when appropriate ("supplies Brother Marcus at the temple")
3. **Reflect world facts** in every creation (iron shortage affects smithy)
4. **Create connections** that make sense ("tunnel connects to existing sewers")
5. **Maintain consistency** with established tone and theme
6. **Ground in consequences** ("cult activity makes guards nervous")

## Verification Checklist

After agents complete:

1. Check each node connects logically to existing world
2. Verify facts don't contradict established lore
3. Ensure NPCs have consistent voices (use voice IDs)
4. Confirm consequences have clear triggers
5. Validate tone consistency across all nodes
6. Verify lore-booster details were incorporated

## Example Combined Output

After parallel execution, you'll have an interconnected district:

- **Economic layer**: Struggling merchants, black market operations, resource conflicts
- **Social layer**: Class tensions, criminal networks, community bonds  
- **Mystical layer**: Religious conflicts, supernatural threats, ancient mysteries
- **All integrated**: NPCs reference each other, locations connect naturally, consequences interweave

## Quick Reference: Lore-Booster Search Terms

For best results with the lore-booster tool, use searches like:
- "[location type] [theme]" (e.g., "thieves den shadow organization")
- "[historical event] [location]" (e.g., "ancient war fortress city")
- "[atmosphere] [place type]" (e.g., "cursed temple forgotten gods")
- "[faction] [activity]" (e.g., "cult ritual underground")

## Future Consolidation Workflow

[Placeholder for synthesis step - reviewing all created content for conflicts and creating meta-connections between the parallel-created nodes]