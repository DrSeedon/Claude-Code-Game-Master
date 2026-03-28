# /dm-save — Session Save + Consistency Check + Handoff

Auto-invoke when: player says "save", "сохранись", "сейв", "на сегодня всё", "закончим", session ending.

---

## STEP 1: SAVE SESSION STATE

```bash
bash tools/dm-session.sh end "[1-line summary of what happened this session]"
```

## STEP 2: DATA HOUSEKEEPING

```bash
bash tools/dm-consequence.sh check
bash tools/dm-plot.sh threads
```

- Resolve any consequences that triggered during session but weren't persisted
- Complete/fail quests that resolved but weren't marked
- Update NPC attitudes/events if any changes were narrated but not saved

## STEP 3: CONSISTENCY CHECK

Run ALL checks below. Fix issues SILENTLY — don't ask the player, just fix and note what was fixed.

### 3a: Cross-reference NPCs ↔ Quests
```bash
CAMPAIGN_DIR=$(bash tools/dm-campaign.sh path)
uv run python - "$CAMPAIGN_DIR" << 'PYEOF'
import json, sys
cd = sys.argv[1]
world = json.load(open(f"{cd}/world.json"))
nodes = world.get("nodes", {})
npcs = {k: v for k, v in nodes.items() if v.get("type") == "npc"}
quests = {k: v for k, v in nodes.items() if v.get("type") == "quest"}

completed_quests = {k for k, v in quests.items() if v.get("data", {}).get("status") in ("completed", "failed")}

issues = []
for npc_id, npc in npcs.items():
    npc_data = npc.get("data", {})
    npc_name = npc_data.get("name", npc_id)
    tagged_quests = npc_data.get("tags", {}).get("quests", [])
    for q in tagged_quests:
        if q in completed_quests:
            issues.append(f"NPC '{npc_name}' tagged to completed quest '{q}' — remove tag")

if issues:
    print("ISSUES FOUND:")
    for i in issues:
        print(f"  - {i}")
else:
    print("NPC-Quest cross-ref: OK")
PYEOF
```

If issues found: fix them with `dm-npc.sh` commands. Remove completed quest tags from NPCs.

### 3b: Orphan check
```bash
CAMPAIGN_DIR=$(bash tools/dm-campaign.sh path)
uv run python - "$CAMPAIGN_DIR" << 'PYEOF'
import json, sys
cd = sys.argv[1]
world = json.load(open(f"{cd}/world.json"))
nodes = world.get("nodes", {})
overview = json.load(open(f"{cd}/campaign-overview.json"))

npcs = {k: v for k, v in nodes.items() if v.get("type") == "npc"}
loc_ids = {k for k, v in nodes.items() if v.get("type") == "location"}

issues = []

cur_loc = overview.get("player_position", {}).get("current_location", overview.get("current_location", ""))
if cur_loc and cur_loc not in loc_ids:
    issues.append(f"Player at '{cur_loc}' but location not in world.json")

for npc_id, npc in npcs.items():
    npc_data = npc.get("data", {})
    npc_name = npc_data.get("name", npc_id)
    for loc in npc_data.get("tags", {}).get("locations", []):
        if loc not in loc_ids:
            issues.append(f"NPC '{npc_name}' tagged to non-existent location '{loc}'")

if issues:
    print("ORPHAN ISSUES:")
    for i in issues:
        print(f"  - {i}")
else:
    print("Orphan check: OK")
PYEOF
```

If issues found: create missing locations or remove stale tags.

### 3c: Character data sanity
```bash
CAMPAIGN_DIR=$(bash tools/dm-campaign.sh path)
uv run python - "$CAMPAIGN_DIR" << 'PYEOF'
import json, sys
cd = sys.argv[1]
world = json.load(open(f"{cd}/world.json"))
nodes = world.get("nodes", {})
player = next((v for v in nodes.values() if v.get("type") == "player"), {})
char = player.get("data", {})

issues = []
hp = char.get("hp", {})
if isinstance(hp, dict):
    if hp.get("current", 0) > hp.get("max", 1):
        issues.append(f"HP current ({hp['current']}) > max ({hp['max']})")
    if hp.get("current", 0) < 0:
        issues.append(f"HP current is negative ({hp['current']})")

money = char.get("money", 0)
if money < 0:
    issues.append(f"Money is negative ({money})")

if issues:
    print("CHARACTER ISSUES:")
    for i in issues:
        print(f"  - {i}")
else:
    print("Character sanity: OK")
PYEOF
```

If issues found: fix with `dm-player.sh` or `dm-inventory.sh`.

## STEP 4: WRITE HANDOFF

Write `world-state/campaigns/[campaign-name]/session-handoff.md` with this structure:

```markdown
# Session Handoff

## Scene
[WHERE is the party, WHAT just happened, WHAT TIME is it]

## Character State
[HP, key conditions, emotional state, recent decisions]

## Active Threads
[What the player is pursuing RIGHT NOW, immediate next steps]

## NPC States
[Key NPCs: current attitude, last interaction, what they want]

## Pending
[Unresolved consequences, approaching deadlines, things the player doesn't know yet]

## Player Intent
[What the player SAID they want to do next, their goals, their mood]
```

Be SPECIFIC. "Party resting" = BAD. "Вильгельм заснул в доме Гёрлицов после ремонта крыши, Кощей на подоконнике, завтра инспекция Бренцеля" = GOOD.

## STEP 5: REPORT

Print summary to player:

```
════════════════════════════════════════
  SESSION SAVED
  [Character] at [location] • [time]
  Fixes applied: [N] (or "none")
  Handoff written for next session.
  Until next time, adventurer.
════════════════════════════════════════
```
