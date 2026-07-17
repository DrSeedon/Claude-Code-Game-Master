# Python Runtime API

Use the domain methods on `WorldGraph`; do not create new flat gameplay files.

```python
from lib.world_graph import WorldGraph

graph = WorldGraph(campaign_dir)

with graph.transaction():
    npc_id = graph.npc_create("Guide", "A tired surveyor", "friendly")
    location_id = graph.location_create("Mine", "An abandoned mine")
    graph.npc_locate(npc_id, location_id)
    graph.fact_add("lore", "The mine predates the colony")
```

The transaction loads `world.json` once and commits once. An exception before
exit leaves the file unchanged.

## Combat State

Use normalized combatants instead of branching on player, NPC, and creature
storage shapes:

```python
target = graph.combatant_stats("creature:infested-miner")
transition = graph.apply_damage(target["id"], 4)
```

At the shell boundary, one auto-combat call owns lookup, attack, damage,
PEN/PROT scaling, and HP persistence:

```bash
bash tools/dm-roll.sh --target "goblin"
bash tools/dm-roll.sh --defend --from "goblin"
```

The firearms module additionally owns fire-mode salvos and ammunition:

```bash
bash .claude/additional/modules/firearms-combat/tools/dm-combat.sh resolve \
  --attacker "Ada" --weapon "C-14" --fire-mode burst \
  --target "creature:hydralisk"
```

Do not follow these commands with a manual damage roll or a second HP update.

## Metadata

Use `JsonOperations` only for non-entity JSON such as
`campaign-overview.json`:

```python
from lib.json_ops import JsonOperations

ops = JsonOperations(campaign_dir)
with ops.transaction("campaign-overview.json") as overview:
    overview["play_mode"] = "narrative"
```

Do not implement `load_json` followed later by `save_json` for partial metadata
changes. That pattern can overwrite a concurrent clock, position, or module
update.

## Module Data

```python
from lib.module_data import ModuleDataManager

data = ModuleDataManager(campaign_dir)
with data.transaction("my-module") as config:
    config["enabled_feature"] = True
```

Module IDs must match `[a-z0-9][a-z0-9-]*`. Module configuration belongs here;
NPCs, locations, items, and other gameplay entities belong in WorldGraph.

## Campaign Context

`DM_ACTIVE_CAMPAIGN` scopes a process to one campaign. If it is absent, runtime
tools use `world-state/active-campaign.txt`. Resolve campaign paths through
`lib.campaign_context`; never concatenate unvalidated user input into a path.

## Public Shell Boundary

Agents and game rules should call `tools/*.sh`. The shell wrappers dispatch
optional module middleware and then invoke the same Python domain methods.
Exit code `64` means a middleware did not handle the action; any other nonzero
code is a real failure and must not fall through to CORE.
