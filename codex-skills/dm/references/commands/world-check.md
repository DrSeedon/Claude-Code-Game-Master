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

### Step 1: Validate JSON Structure
```bash
# The repository has no campaign-wide schema validator. Verify that the
# authoritative JSON files parse before running the content checks below.
CAMPAIGN_DIR=$(bash tools/dm-campaign.sh path)
uv run python -m json.tool "$CAMPAIGN_DIR/world.json" >/dev/null
uv run python -m json.tool "$CAMPAIGN_DIR/campaign-overview.json" >/dev/null
echo "Campaign JSON: valid"
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
Check the required overview fields explicitly because JSON parsing validates syntax, not campaign completeness.

### Step 2: Location Analysis
```bash
CAMPAIGN_DIR=$(bash tools/dm-campaign.sh path)
uv run python -c "
import json, sys
campaign_dir = sys.argv[1]
world = json.load(open(f'{campaign_dir}/world.json'))
nodes = world.get('nodes', {})
edges = world.get('edges', [])
locations = {k: v for k, v in nodes.items() if v.get('type') == 'location'}

print(f'📍 LOCATIONS: {len(locations)} total')

for loc_id, node in locations.items():
    data = node.get('data', {})
    name = node.get('name', loc_id)
    desc_len = len(data.get('description', node.get('description', '')))
    conn_count = sum(
        1 for edge in edges
        if edge.get('type') == 'connected'
        and loc_id in (edge.get('from'), edge.get('to'))
    )

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
edges = world.get('edges', [])
npcs = {k: v for k, v in nodes.items() if v.get('type') == 'npc'}

print(f'🎭 NPCS: {len(npcs)} total')

for npc_id, node in npcs.items():
    data = node.get('data', {})
    name = node.get('name', npc_id)
    desc_len = len(data.get('description', ''))

    desc_status = '✅' if desc_len > 80 else '⚠️'
    location_tags = [
        nodes.get(edge.get('to'), {}).get('name', edge.get('to'))
        for edge in edges
        if edge.get('from') == npc_id and edge.get('type') == 'at'
    ]
    quest_tags = [
        nodes.get(edge.get('from'), {}).get('name', edge.get('from'))
        for edge in edges
        if edge.get('to') == npc_id and edge.get('type') == 'involves'
        and nodes.get(edge.get('from'), {}).get('type') == 'quest'
    ]

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
    name = node.get('name', quest_id)
    t = data.get('quest_type', 'other')
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
edges = world.get('edges', [])
locations = {k: v for k, v in nodes.items() if v.get('type') == 'location'}
loc_ids = set(locations.keys())

print('🔗 LOCATION CONNECTIONS:')

connected_edges = [edge for edge in edges if edge.get('type') == 'connected']
for edge in connected_edges:
    for endpoint in (edge.get('from'), edge.get('to')):
        if endpoint not in loc_ids:
            print(f'❌ Connection references non-location {endpoint}')

orphaned = [
    node.get('name', loc_id)
    for loc_id, node in locations.items()
    if not any(loc_id in (edge.get('from'), edge.get('to')) for edge in connected_edges)
]
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
edges = world.get('edges', [])
npcs = {k: v for k, v in nodes.items() if v.get('type') == 'npc'}
loc_ids = {k for k, v in nodes.items() if v.get('type') == 'location'}

print('🏠 NPC LOCATION EDGES:')

issues = []
for npc_id, node in npcs.items():
    name = node.get('name', npc_id)
    location_edges = [
        edge for edge in edges
        if edge.get('from') == npc_id and edge.get('type') == 'at'
        and edge.get('to') in loc_ids
    ]
    if not location_edges:
        issues.append(f'⚠️ {name} has no valid location edge')

if issues:
    for issue in issues[:5]:
        print(issue)
else:
    print('✅ All NPCs have valid location edges')
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
if not locations:
    issues.append('❌ No locations')
    ready = False

npcs = [v for v in nodes.values() if v.get('type') == 'npc']
if not npcs:
    issues.append('❌ No NPCs')
    ready = False

quests = [v for v in nodes.values() if v.get('type') == 'quest' and v.get('data', {}).get('status') == 'active']
if not quests:
    issues.append('❌ No active quests')
    ready = False
elif any(not quest.get('data', {}).get('objectives') for quest in quests):
    issues.append('❌ Active quest without objectives')
    ready = False
elif any(
    not isinstance(quest.get('data', {}).get('xp_reward'), int)
    or isinstance(quest.get('data', {}).get('xp_reward'), bool)
    or quest.get('data', {}).get('xp_reward') < 0
    for quest in quests
):
    issues.append('❌ Active quest without a non-negative integer XP reward')
    ready = False

consequences = [
    v for v in nodes.values()
    if v.get('type') == 'consequence'
    and v.get('data', {}).get('status') != 'resolved'
    and v.get('data', {}).get('hours_remaining') is not None
]
if not consequences:
    issues.append('❌ No scheduled consequences with timers')
    ready = False

if 'player:active' not in nodes:
    issues.append('❌ No active player node')
    ready = False
if 'misc:economy' not in nodes:
    issues.append('❌ No economy node')
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
# Create the conflict justified by the starting situation, then add objectives.
bash tools/dm-plot.sh add "Strange Disappearances" --type mystery --desc "People vanish from the town at night; if ignored, another resident disappears" --xp 150
bash tools/dm-plot.sh objective "Strange Disappearances" add "Investigate the disappearances"
```

---

## SUCCESS CRITERIA

Your world is ready when:
- ✅ All files valid JSON
- ✅ Campaign overview complete
- ✅ Starting location defined
- ✅ Starting and supporting locations have useful descriptions
- ✅ All locations connected
- ✅ Every starting NPC has a description, attitude, goal, relationship, and location
- ✅ Active conflicts are quests with trackable objectives
- ✅ Relevant independent actors or threats have timed consequences
- ✅ Entity quantities follow the starting situation rather than numeric quotas
- ✅ Session log initialized

---

Run this check after world generation and before starting play!
