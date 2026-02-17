# Encounter System — DM Rules

> These instructions tell the DM (Claude) when and how to call the encounter module.

## Architecture

**DM-as-Glue Pattern:** Session manager (`dm-session.sh move`) only moves the party and prints travel distance/time. The DM (Claude) reads these rules and calls `dm-encounter.sh` separately when needed.

This decouples encounter logic from CORE's session manager, allowing the module to be optional.

## When to Call

### Manual Encounter Check (Preferred)

When a party travels overland and `campaign_rules.encounter_system.enabled = true`:

```bash
bash .claude/modules/encounter-system/tools/dm-encounter.sh check "<from_loc>" "<to_loc>" <distance_meters> [terrain]
```

**Example:**
```bash
bash .claude/modules/encounter-system/tools/dm-encounter.sh check "Village" "Ruins" 2000 open
```

**The system will:**
1. Calculate number of segments (1-3 based on distance)
2. Roll encounter checks (d20 + character modifier vs DC)
3. For each triggered encounter, roll nature (Dangerous, Neutral, Beneficial, Special)
4. Prompt DM for encounter type (Combat, Social, Hazard, Loot, Flavor)
5. Create waypoints for Combat/Social/Hazard encounters
6. Auto-resolve Loot/Flavor encounters

### After dm-session.sh move

If the move output contains distance_meters in result JSON, extract it and call:

```bash
bash .claude/modules/encounter-system/tools/dm-encounter.sh check "$FROM" "$TO" $DISTANCE "$TERRAIN"
```

**Do NOT duplicate travel time calculation** - session manager already advanced time. Encounters only determine if/where journey is interrupted.

## Encounter Types

| Type | Creates Waypoint? | DM Action |
|------|-------------------|-----------|
| **Combat** | Yes | Describe enemies, initiate combat |
| **Social** | Yes | Describe NPC encounter, handle dialogue |
| **Hazard** | Yes | Describe obstacle (anomaly, trap, weather) |
| **Loot** | No | Describe find, add items with dm-player.sh |
| **Flavor** | No | Describe atmospheric event, continue |

## Waypoints

When Combat/Social/Hazard encounter occurs, system creates a temporary location midway on the journey.

**Player options at waypoint:**
- **Forward**: Continue to destination (remaining distance)
- **Back**: Return to origin (distance traveled so far)

**System automatically:**
- Creates waypoint location with coordinates
- Adds bidirectional connections (forward/back)
- Removes waypoint after player leaves

## Configuration

### Enable/Disable

```bash
bash .claude/modules/encounter-system/tools/dm-encounter.sh toggle
```

### Adjust Difficulty

```bash
# Lower base DC = more encounters
bash .claude/modules/encounter-system/tools/dm-encounter.sh set-base-dc 12

# Higher distance modifier = long journeys are more dangerous
bash .claude/modules/encounter-system/tools/dm-encounter.sh set-distance-mod 3
```

### Set Character Stat

```bash
# Use D&D ability
bash .claude/modules/encounter-system/tools/dm-encounter.sh set-stat dex

# Use D&D skill
bash .claude/modules/encounter-system/tools/dm-encounter.sh set-stat stealth

# Use custom stat
bash .claude/modules/encounter-system/tools/dm-encounter.sh set-stat custom:awareness
```

### Time-of-Day Modifiers

```bash
# Night is +4 harder to avoid encounters
bash .claude/modules/encounter-system/tools/dm-encounter.sh set-time-mod Night 4
```

## Check Status

```bash
bash .claude/modules/encounter-system/tools/dm-encounter.sh status
```

## Activation Check

At session start, check if `campaign_rules.encounter_system.enabled = true`.
If yes, load these rules and follow them for the duration of the session.

## When NOT to Call

- Do NOT call if `encounter_system.enabled = false`
- Do NOT call for distances < `min_distance_meters` (default 300m)
- Do NOT call for teleportation or instant travel
- Do NOT call for movement within same building/area

## Integration with Session Manager

**IMPORTANT:** After module extraction, session_manager.py NO LONGER calls encounter checks automatically. The DM must call dm-encounter.sh manually based on these rules.

This is intentional — it gives DM full control over when/how encounters are checked.
