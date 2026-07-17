# /import - Import Your Adventure

Import a D&D book, adventure module, or any document and extract it into a playable campaign.

## Usage

```
/import <file-path> [campaign-name]
```

**Arguments:**
- `file-path` - Path to PDF, DOCX, TXT, or MD file
- `campaign-name` - Optional name (defaults to filename)

---

## Step 1: Get File Information

If arguments weren't provided, first check the source-material folder:

```bash
ls -la source-material/ 2>/dev/null | grep -E '\.(pdf|docx|txt|md)$'
```

**If files are found**, display them as options:
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  IMPORT YOUR ADVENTURE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Found documents in source-material/:

  1) [filename.pdf]
  2) [filename2.docx]
  ...

  Or: Drag/drop a different file, or paste a path

Supported formats: PDF, DOCX, TXT, MD
```

Ask the user directly with these options:.

**If no files in source-material/**, display:
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  IMPORT YOUR ADVENTURE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Drag and drop your file here, or paste the file path.
(Tip: You can also place files in source-material/)

Supported formats: PDF, DOCX, TXT, MD
```

Then ask for campaign name (or use filename as default).

---

## Step 2: Vectorize the Document

Show progress as the document is prepared:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  PREPARING: "<filename>"
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Reading your adventure and preparing it for play...
```

Run the prepare command:
```bash
bash tools/dm-extract.sh prepare "<file-path>" "<campaign-name>"
```

After completion, display what was processed:
```
  ├─ Extracting text............... done
  ├─ Splitting into sections....... done
  ├─ Building search index......... done
  └─ Ready for extraction!
```

---

## Step 3: Preview What's In The Book

Run sample queries to show the user what content is available:

```bash
# Sample queries to detect content types
bash tools/dm-search.sh --rag-only "character name person NPC" 5
bash tools/dm-search.sh --rag-only "location place room dungeon" 5
bash tools/dm-search.sh --rag-only "item treasure weapon magic" 5
bash tools/dm-search.sh --rag-only "quest mission objective plot" 5
```

Display a preview:
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  DOCUMENT READY!
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

I've scanned your adventure. Here's what I found:

  Characters mentioned:  ~[count] names detected
    ([sample names from query results]...)

  Locations described:   ~[count] places
    ([sample locations from query results]...)

  Items & Treasures:     ~[count] references
    ([sample items from query results]...)

  Quests & Hooks:        ~[count] storylines
    ([sample plot elements from query results]...)
```

---

## Step 4: Offer Extraction Options

Ask the user what to extract:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  WHAT SHOULD I EXTRACT?
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

I can pull out detailed information for:

  [x] NPCs - Characters with descriptions & personalities
  [x] Locations - Places with connections & features
  [x] Items - Treasures, magic items, equipment
  [x] Quests - Story hooks, objectives, rewards

  1) Extract all (recommended)
  2) Let me choose which ones
  3) Skip extraction - I'll reference the book myself
```

Ask the user directly with these options:
- "Extract all (Recommended)" - Extract NPCs, locations, items, and quests
- "Let me choose" - Show checkboxes for each type
- "Skip extraction" - Just use the search index, no structured extraction

---

## Step 5: Run Extraction Agents

Display extraction progress:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  EXTRACTING CONTENT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Four extraction specialists are reading your adventure...

  NPCs ............ [working]
  Locations ....... [working]
  Items ........... [working]
  Quests .......... [working]

Independent extraction jobs may run in parallel when subagents are available; otherwise run them locally one by one.
```

**CRITICAL**: Read the four matching files under `../specialists/`. If subagents are permitted, launch four independent jobs in parallel. Otherwise execute the same extraction playbooks locally and write the same outputs:

```
Specialist: extractor-npcs
prompt: "Extract characters from: world-state/campaigns/<campaign-name>/chunks/
         Read all chunk files and extract every character/NPC/person.
         Write output to: world-state/campaigns/<campaign-name>/extracted/npcs.json"

Specialist: extractor-locations
prompt: "Extract places from: world-state/campaigns/<campaign-name>/chunks/
         Read all chunk files and extract every location/setting/scene.
         Write output to: world-state/campaigns/<campaign-name>/extracted/locations.json"

Specialist: extractor-items
prompt: "Extract objects from: world-state/campaigns/<campaign-name>/chunks/
         Read all chunk files and extract every item/object/prop.
         Write output to: world-state/campaigns/<campaign-name>/extracted/items.json"

Specialist: extractor-plots
prompt: "Extract story elements from: world-state/campaigns/<campaign-name>/chunks/
         Read all chunk files and extract every quest/scene/theme/plot point.
         Write output to: world-state/campaigns/<campaign-name>/extracted/plots.json"
```

As each agent completes, update the display:
```
  NPCs ............ done! (23 found)
  Locations ....... done! (15 found)
  Items ........... done! (42 found)
  Quests .......... done! (8 found)
```

---

## Step 5.5: Validate Extraction Results

**CRITICAL**: After ALL agents report completion, validate their output before proceeding.

```bash
bash tools/dm-extract.sh validate "<campaign-name>"
```

This checks that all 4 extraction files exist and contain valid JSON.

**If validation passes** (all files present with entities):
- Continue to Step 6

**If validation fails** (missing files, invalid JSON, or all empty):

Display:
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  ⚠️  EXTRACTION INCOMPLETE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Some extraction agents failed or returned empty results.

  [validation output showing which files failed]

What would you like to do?
```

Ask the user directly with these options:
- **"Retry failed extractions"** - Re-launch agents only for missing/empty types
- **"Continue with partial data"** - Proceed with whatever was extracted
- **"Cancel import"** - Stop the import process

**Do NOT proceed silently with missing data.** The whole point of import is to extract content from the source material. If extraction failed, the user must be informed and given options.

---

## Step 6: Import Extracted Data into WorldGraph

After all agents complete, import extracted JSON files into world.json:

```bash
CAMPAIGN_DIR="world-state/campaigns/<campaign-name>"

# Import extracted data into world.json via Python
uv run python -c "
import json, re, sys
sys.path.insert(0, 'lib')
from world_graph import WorldGraph

g = WorldGraph()
cd = '$CAMPAIGN_DIR'

TRANSLIT = {'а':'a','б':'b','в':'v','г':'g','д':'d','е':'e','ё':'yo','ж':'zh','з':'z','и':'i','й':'y','к':'k','л':'l','м':'m','н':'n','о':'o','п':'p','р':'r','с':'s','т':'t','у':'u','ф':'f','х':'kh','ц':'ts','ч':'ch','ш':'sh','щ':'sch','ъ':'','ы':'y','ь':'','э':'e','ю':'yu','я':'ya'}
def slug(name):
    s = name.lower()
    out = [TRANSLIT.get(ch, ch) for ch in s]
    return re.sub(r'[^a-z0-9]+', '-', ''.join(out)).strip('-') or 'unknown'

# NPCs
try:
    npcs = json.load(open(f'{cd}/extracted/npcs.json'))
    for name, data in npcs.items():
        g.npc_create(name, data.get('description', ''), data.get('attitude', 'neutral'))
    print(f'  NPCs: {len(npcs)}')
except: pass

# Locations
try:
    locs = json.load(open(f'{cd}/extracted/locations.json'))
    for name, data in locs.items():
        g.location_create(name, data.get('description', data.get('position', '')))
    print(f'  Locations: {len(locs)}')
except: pass

# Plots
try:
    plots = json.load(open(f'{cd}/extracted/plots.json'))
    for pid, data in plots.items():
        g.quest_create(data.get('description', pid)[:60], data.get('type', 'side'), data.get('description', ''))
    print(f'  Quests: {len(plots)}')
except: pass

# Items
try:
    items = json.load(open(f'{cd}/extracted/items.json'))
    for name, data in items.items():
        nid = f'item:{slug(name)}'
        g.add_node(nid, 'item', name, data)
    print(f'  Items: {len(items)}')
except: pass
"

# Archive the extracted/ folder (temporary working directory)
bash tools/dm-extract.sh archive "<campaign-name>"
```

**Note**: The `extracted/` folder is a temporary working directory. Data is imported into `world.json`. Archive after import.

---

## Step 7: Switch to Campaign and Show Summary

```bash
bash tools/dm-campaign.sh switch "<campaign-name>"
```

Count and display what was extracted:

```bash
CAMPAIGN_DIR=$(bash tools/dm-campaign.sh path)
bash tools/dm-world.sh stats
```

Display the summary:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  YOUR WORLD IS READY!
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Campaign: "<campaign-name>"

  [count] NPCs ready to meet
     [sample 3-4 NPC names from the extracted data]...

  [count] Locations to explore
     [sample 3-4 location names]...

  [count] Items & Treasures
     [sample 3-4 item names]...

  [count] Quest Hooks active
     [sample 3-4 quest names]...

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## Step 7.5: Batch RAG Enhancement (CRITICAL FOR QUALITY)

**This step primes all extracted entities with source material context.**

Display progress:
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  ENHANCING ENTITIES WITH SOURCE MATERIAL
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Connecting extracted entities to original text passages...
This ensures rich, authentic gameplay context.
```

Run the batch enhancement:
```bash
bash tools/dm-enhance.sh batch
```

This will:
1. Query RAG for each extracted entity (NPCs, locations, items, plots)
2. Store the top matching passages with each entity
3. Enable rich scene descriptions during gameplay

Display completion:
```
  Enhancement complete!
  ├─ [X] entities enhanced with source passages
  └─ Ready for authentic gameplay

Your world now has deep connections to the source material.
NPCs will speak with their original voices, locations will
feel true to the book.
```

**Why this matters:**
- Without enhancement, entities are just names and brief descriptions
- With enhancement, each entity has 3-5 source passages attached
- During gameplay, the DM can draw on this context for authentic narration

---

## Step 8: Transition to Character Creation

Display:

```
The book IS your world - all the NPCs, locations, items, and
quests from your adventure are now ready to play.

Now let's create your character for this adventure!
```

Then automatically run `/create-character` to guide the user through character creation.

---

## Output Location

All content is stored in:

```
world-state/campaigns/<campaign-name>/
├── chunks/              # Text chunks from document
├── vectors/             # ChromaDB embeddings for RAG queries
├── extracted/           # Individual agent outputs (temporary)
│   ├── npcs.json
│   ├── locations.json
│   ├── items.json
│   └── plots.json
├── world.json           # Unified entity graph (imported from extracted/)
├── campaign-overview.json
├── session-log.md
└── current-document.txt # Full extracted text
```

---

## Content-Type Adaptation

The agents automatically detect and adapt to your content:

| Document Type | Characters | Places | Objects | Story Elements |
|---------------|------------|--------|---------|----------------|
| **D&D Modules** | NPCs, enemies | Rooms, dungeons | Magic items, treasure | Quests, plot hooks |
| **Fiction/Books** | Characters | Settings, scenes | Notable objects | Themes, plot points |
| **Scripts** | Characters | Scenes, locations | Props | Scenes, dialogue |
| **Notes** | People mentioned | Places mentioned | Things mentioned | Ideas, concepts |

---

## Troubleshooting

**No chunks created**: The document may be empty or unreadable. Check `current-document.txt`.

**Agents fail**: Check that chunk files exist in `chunks/` directory.

**Missing content**: Run individual agents again with more specific prompts, or use `bash tools/dm-search.sh --rag-only "search terms"` to search directly.

**Want to enhance extracted entities**: Use `/enhance` to add more detail from source material via RAG.
