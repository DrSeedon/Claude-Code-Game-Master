# /enhance - Entity Enhancement from Source Material

Enhance entities or search for source material using RAG.

## Arguments

$ARGUMENTS - Entity name OR search keywords (e.g., "Grimjaw", "second floor monsters", "dungeon layout")

## Philosophy

**DM judges relevance, not the code.** The RAG system returns semantically similar passages without strict filtering. You (the DM) decide what's useful. This prevents filtering out valuable content due to naming mismatches (e.g., "Floor 2" vs "second floor").

## Workflow

### Step 1: Determine Entity Type

First, find what kind of entity we're enhancing:

```bash
bash tools/dm-enhance.sh find "$ARGUMENTS"
```

This returns one of:
- `npc` - Character enhancement
- `location` - Place enhancement
- `dungeon` - Dungeon with room structure potential
- `item` - Magic item or treasure
- `plot` - Quest or story hook

If no entity found, use **Option A: Exploratory Search** instead.

---

### Option A: Exploratory Search (No Specific Entity)

Use when searching for general information:

```bash
bash tools/dm-enhance.sh search "$ARGUMENTS" -n 15
```

Examples:
- `search "dungeon second level"` - Find dungeon content
- `search "Grimjaw background personality"` - Learn about an NPC
- `search "boss monster final encounter"` - Find boss info

**Process the results:**
1. Read through returned passages
2. Extract relevant details for the current scene/entity
3. Weave information naturally into gameplay or entity updates

---

### Option B: NPC Enhancement

When entity type is `npc`:

#### Step 1: Query Source Passages

```bash
bash tools/dm-enhance.sh query "$ARGUMENTS" --type npc
```

#### Step 2: Propose Enhancements

Present to the DM:

```
**NPC Found:** [Name]

**Current State:**
- Description: [current description or "None"]
- Context passages: [count]

**From Source Material:**
Based on [X] passages, I can add:
- [Personality trait from source]
- [Background detail from source]
- [Relationship or motivation]
- [N context passages for future reference]

**Apply these enhancements?**
```

#### Step 3: Apply If Approved

```bash
bash tools/dm-enhance.sh apply "$ARGUMENTS" --context "passage 1" --context "passage 2"
```

For description updates:
```bash
--description "Enhanced description text"
```

---

### Option C: Dungeon Enhancement

When entity type is `dungeon`:

#### Step 1: Check Existing Structure

```bash
bash tools/dm-enhance.sh dungeon-check "$ARGUMENTS"
```

This returns:
- `room_count` - Number of rooms defined
- `has_structure` - Whether rooms exist in world.json as location nodes
- `rooms` - List of existing rooms

#### Step 2: Query Source Passages

```bash
bash tools/dm-enhance.sh query "$ARGUMENTS" --type dungeon -n 15
```

#### Step 3: Present Options

**If NO room structure exists:**

```
**Dungeon Found:** [Name]
**Room Structure:** None defined

**From Source Material:**
Found [X] passages about this dungeon. I can extract:
- Theme: [extracted theme]
- Notable rooms mentioned: [room names from source]
- Inhabitants: [monsters/NPCs mentioned]
- Key features: [traps, treasures, secrets]

**Options:**
[G] Generate room structure - Spawn dungeon-architect with source passages
[E] Enhance description only - Add context without generating rooms
[S] Skip - Do nothing
```

**If structure already exists:**

```
**Dungeon Found:** [Name]
**Existing Rooms:** [count] rooms defined

**Current Rooms:**
1. [Room 1 name] [discovered/cleared status]
2. [Room 2 name] ...

**From Source Material:**
Found [X] additional passages. I can:
- Add context passages to dungeon entry
- Update room descriptions with source details

**Apply context enhancements?**
```

#### Step 4: Generate Structure (If Chosen)

When user chooses [G]enerate:

1. Tell the player to wait:
   ```
   **Generating dungeon structure...**
   Please wait while I create the room layout from source material.
   ```

2. Spawn dungeon-architect agent in **foreground** with source passages:

   ```
   Task(dungeon-architect):
     "Generate dungeon '[Dungeon Name]' using these source passages:

     PASSAGE 1: '[text from RAG]'
     PASSAGE 2: '[text from RAG]'
     ...

     Theme from source: [extracted theme]
     Mentioned rooms: [room names from passages]
     Mentioned inhabitants: [monsters/NPCs]

     Generate room structure that matches the source:
     - Use room names from source exactly
     - Include mentioned monsters/NPCs
     - Add traps/secrets mentioned
     - Only improvise for gaps

     Return complete JSON for all rooms."
   ```

3. Display generated rooms for approval:
   ```
   **Generated [N] rooms:**

   1. [Room Name] - [brief description]
   2. [Room Name] - [brief description]
   ...

   **Save to world.json?**
   ```

4. If approved, add rooms as location nodes in world.json via `dm-location.sh` or `dm-world.sh`

---

## Proactive Dungeon Generation

**IMPORTANT:** When a player enters a dungeon location:

1. Check if room structure exists:
   ```bash
   bash tools/dm-enhance.sh dungeon-check "[Dungeon Name]"
   ```

2. If `has_structure: false`:
   - Tell the player: "Please wait a moment while I generate the dungeon layout..."
   - Run the dungeon enhancement flow automatically
   - Generate rooms from source material (or improvise if no source)
   - Show the entry room description when ready

This ensures dungeons have proper room structures before exploration begins.

---

## Command Reference

| Command | Use For |
|---------|---------|
| `search "keywords"` | Exploratory queries, concepts, general info |
| `find "name"` | Locate a specific entity and determine type |
| `query "name"` | Get passages for a known entity |
| `apply "name"` | Save enhancements to entity |
| `summary "name"` | Full entity + passages report |
| `list-unenhanced` | Find entities needing enhancement |
| `dungeon-check "name"` | Check dungeon room structure |

## Notes

- Requires a populated vector store (run `/import` first)
- Uses additive merging - existing context is preserved
- Context passages capped at 20 per entity
- Works for NPCs, locations, items, plots, dungeons
- **No strict name filtering** - DM judges all passage relevance
- **RAG Priority**: Use source material for accuracy over improvisation
- **Dungeon auto-generation**: When player enters a dungeon without rooms, generate structure proactively
