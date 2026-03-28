# 🔍 WORLD CHECK - Campaign Consistency Validator

This command validates your generated world for completeness and consistency. Run after world generation or when debugging issues.

---

## PHASE 1: STRUCTURAL VALIDATION

### Step 0: Get Active Campaign Path
```bash
CAMPAIGN_DIR=$(bash tools/dm-campaign.sh path)
echo "Checking campaign: $(bash tools/dm-campaign.sh active)"
echo "Path: $CAMPAIGN_DIR"
```

### Step 1: Run Schema Validator (Preferred)
```bash
# Validates the active campaign against lib/schemas.py
uv run python lib/schemas.py
```

### Step 2: Check Session Log
```bash
CAMPAIGN_DIR=$(bash tools/dm-campaign.sh path)
if [ -f "$CAMPAIGN_DIR/session-log.md" ]; then
    lines=$(wc -l < "$CAMPAIGN_DIR/session-log.md")
    if [ $lines -gt 3 ]; then
        echo "✅ session-log.md - Has content ($lines lines)"
    else
        echo "⚠️ session-log.md - Minimal content"
    fi
else
    echo "❌ session-log.md - Missing"
fi
```

---

## PHASE 2: CONTENT VALIDATION

### Step 1: Campaign Overview Completeness
Covered by the schema validator above. Only add custom checks here if needed.

### Step 2: Location Analysis
```bash
CAMPAIGN_DIR=$(bash tools/dm-campaign.sh path)
uv run python -c "
import json, sys
campaign_dir = sys.argv[1]
world = json.load(open(f'{campaign_dir}/world.json'))
nodes = world.get('nodes', {})
locations = {k: v for k, v in nodes.items() if v.get('type') == 'location'}

print(f'📍 LOCATIONS: {len(locations)} total')

for loc_id, node in locations.items():
    data = node.get('data', {})
    name = data.get('name', loc_id)
    desc_len = len(data.get('description', ''))
    conn_count = len(data.get('connections', []))

    status = '✅' if desc_len > 50 else '⚠️'
    print(f'{status} {name}: {desc_len} chars, {conn_count} connections')

    if conn_count == 0:
        print(f'   ⚠️ No connections - orphaned location!')
" "$CAMPAIGN_DIR"
```

### Step 3: NPC Analysis
```bash
CAMPAIGN_DIR=$(bash tools/dm-campaign.sh path)
uv run python -c "
import json, sys
campaign_dir = sys.argv[1]
world = json.load(open(f'{campaign_dir}/world.json'))
nodes = world.get('nodes', {})
npcs = {k: v for k, v in nodes.items() if v.get('type') == 'npc'}

print(f'🎭 NPCS: {len(npcs)} total')

for npc_id, node in npcs.items():
    data = node.get('data', {})
    name = data.get('name', npc_id)
    desc_len = len(data.get('description', ''))
    tags = data.get('tags', {})

    desc_status = '✅' if desc_len > 80 else '⚠️'
    location_tags = tags.get('locations', [])
    quest_tags = tags.get('quests', [])

    print(f'{desc_status} {name}:')
    print(f'   Description: {desc_len} chars')
    print(f'   Attitude: {data.get(\"attitude\", \"unknown\")}')
    if location_tags:
        print(f'   📍 Locations: {location_tags}')
    if quest_tags:
        print(f'   📜 Quests: {quest_tags}')
" "$CAMPAIGN_DIR"
```

### Step 4: Plot Structure Check
```bash
CAMPAIGN_DIR=$(bash tools/dm-campaign.sh path)
uv run python -c "
import json, sys
campaign_dir = sys.argv[1]
world = json.load(open(f'{campaign_dir}/world.json'))
nodes = world.get('nodes', {})
quests = {k: v for k, v in nodes.items() if v.get('type') == 'quest'}

print('📜 PLOT STRUCTURE:')

if not quests:
    print('❌ No quests in world.json')
    sys.exit(0)

by_type = {}
for quest_id, node in quests.items():
    data = node.get('data', {})
    name = data.get('name', quest_id)
    t = data.get('type', 'other')
    by_type.setdefault(t, []).append(name)

for t in ['main', 'side', 'mystery', 'threat']:
    names = by_type.get(t, [])
    if names:
        print(f'✅ {t}: {len(names)} — {\", \".join(names)}')
    else:
        print(f'⚠️  {t}: none')

active = sum(1 for node in quests.values() if node.get('data', {}).get('status') == 'active')
print(f'📊 Total: {len(quests)} ({active} active)')
" "$CAMPAIGN_DIR"
```

### Step 5: Consequences Timeline
```bash
CAMPAIGN_DIR=$(bash tools/dm-campaign.sh path)
uv run python -c "
import json, sys
campaign_dir = sys.argv[1]
world = json.load(open(f'{campaign_dir}/world.json'))
nodes = world.get('nodes', {})
consequences = {k: v for k, v in nodes.items() if v.get('type') == 'consequence'}

active = [v for v in consequences.values() if v.get('data', {}).get('status') != 'resolved']
resolved = [v for v in consequences.values() if v.get('data', {}).get('status') == 'resolved']

print(f'⏰ CONSEQUENCES:')
print(f'   Active: {len(active)}')
print(f'   Resolved: {len(resolved)}')

if active:
    print('\n   Scheduled Events:')
    for node in active:
        data = node.get('data', {})
        trigger = data.get('trigger', 'unknown')
        desc = data.get('consequence', data.get('description', ''))[:50]
        print(f'   • {trigger}: {desc}...')
" "$CAMPAIGN_DIR"
```

---

## PHASE 3: RELATIONSHIP VALIDATION

### Step 1: Location Connectivity
```bash
CAMPAIGN_DIR=$(bash tools/dm-campaign.sh path)
uv run python -c "
import json, sys
campaign_dir = sys.argv[1]
world = json.load(open(f'{campaign_dir}/world.json'))
nodes = world.get('nodes', {})
locations = {k: v for k, v in nodes.items() if v.get('type') == 'location'}
loc_names = {v.get('data', {}).get('name', k) for k in locations}
loc_ids = set(locations.keys())

print('🔗 LOCATION CONNECTIONS:')

connections = {}
for loc_id, node in locations.items():
    data = node.get('data', {})
    name = data.get('name', loc_id)
    connections[name] = []
    for conn in data.get('connections', []):
        target = conn.get('to', '')
        if target:
            connections[name].append(target)
            if target not in loc_ids and target not in loc_names:
                print(f'❌ {name} connects to non-existent {target}')

orphaned = [name for name, conns in connections.items() if len(conns) == 0]
if orphaned:
    print(f'⚠️ Orphaned locations (no connections): {orphaned}')
else:
    print('✅ All locations connected')
" "$CAMPAIGN_DIR"
```

### Step 2: NPC Location Verification
```bash
CAMPAIGN_DIR=$(bash tools/dm-campaign.sh path)
uv run python -c "
import json, sys
campaign_dir = sys.argv[1]
world = json.load(open(f'{campaign_dir}/world.json'))
nodes = world.get('nodes', {})
npcs = {k: v for k, v in nodes.items() if v.get('type') == 'npc'}
loc_ids = {k for k, v in nodes.items() if v.get('type') == 'location'}
loc_names = {v.get('data', {}).get('name', k) for k in loc_ids}

print('🏠 NPC LOCATION TAGS:')

issues = []
for npc_id, node in npcs.items():
    data = node.get('data', {})
    name = data.get('name', npc_id)
    location_tags = data.get('tags', {}).get('locations', [])
    if not location_tags:
        issues.append(f'⚠️ {name} has no location tags')

if issues:
    for issue in issues[:5]:
        print(issue)
else:
    print('✅ All NPCs have location tags')
" "$CAMPAIGN_DIR"
```

---

## PHASE 4: COMPLETENESS REPORT

### Generate Summary Report
```bash
CAMPAIGN_DIR=$(bash tools/dm-campaign.sh path)
echo "
═══════════════════════════════════════════════════════
                 WORLD VALIDATION REPORT
═══════════════════════════════════════════════════════
Campaign: $(bash tools/dm-campaign.sh active)
"

# Quick stats
echo "📊 QUICK STATS:"
uv run python -c "
import json
world = json.load(open('$CAMPAIGN_DIR/world.json'))
nodes = world.get('nodes', {})
locs = sum(1 for v in nodes.values() if v.get('type') == 'location')
npcs = sum(1 for v in nodes.values() if v.get('type') == 'npc')
quests = sum(1 for v in nodes.values() if v.get('type') == 'quest' and v.get('data', {}).get('status') == 'active')
cons = sum(1 for v in nodes.values() if v.get('type') == 'consequence' and v.get('data', {}).get('status') != 'resolved')
print(f'   Locations: {locs}')
print(f'   NPCs: {npcs}')
print(f'   Active Plots: {quests}')
print(f'   Consequences: {cons}')
"

echo "
🎯 READINESS CHECKLIST:
"

# Campaign ready check
uv run python -c "
import json, sys
campaign_dir = sys.argv[1]
world = json.load(open(f'{campaign_dir}/world.json'))
nodes = world.get('nodes', {})
overview = json.load(open(f'{campaign_dir}/campaign-overview.json'))
ready = True
issues = []

if not overview.get('campaign_name'):
    issues.append('❌ No campaign name set')
    ready = False
if not overview.get('player_position', {}).get('current_location'):
    issues.append('❌ No starting location set')
    ready = False

locations = [v for v in nodes.values() if v.get('type') == 'location']
if len(locations) < 3:
    issues.append('❌ Less than 3 locations')
    ready = False

npcs = [v for v in nodes.values() if v.get('type') == 'npc']
if len(npcs) < 4:
    issues.append('❌ Less than 4 NPCs')
    ready = False

if issues:
    print('\n'.join(issues))
else:
    print('✅ World is ready for play!')
    print('✅ Run /dm to begin!')
" "$CAMPAIGN_DIR"
```

---

## QUICK FIX COMMANDS

Based on validation results, here are quick fixes:

### Orphaned Locations
```bash
# Connect orphaned location to nearest
bash tools/dm-location.sh connect "[Orphaned]" "[Nearby Location]" "a winding path"
```

### Missing Descriptions
```bash
# Use world-builder agent to enhance
# Launch with Task tool targeting specific location/NPC
```

### No Plots
```bash
# Quick plot generation
bash tools/dm-plot.sh add "Strange Disappearances" --type side --description "People vanish from the town at night" --objectives "Investigate the disappearances,Find the source"
bash tools/dm-plot.sh add "Weakening Seals" --type mystery --description "Ancient seals are failing across the land" --objectives "Discover a broken seal,Research the cause"
bash tools/dm-plot.sh add "The Dark Star" --type threat --description "A dark star approaches, heralding change" --objectives "Learn about the prophecy"
```

---

## SUCCESS CRITERIA

Your world is ready when:
- ✅ All files valid JSON
- ✅ Campaign overview complete
- ✅ Starting location defined
- ✅ 4+ locations with descriptions
- ✅ All locations connected
- ✅ 4+ NPCs with descriptions and attitudes
- ✅ Three-tier plot structure
- ✅ 2+ active consequences
- ✅ Session log initialized

---

Run this check after world generation and before starting play!
