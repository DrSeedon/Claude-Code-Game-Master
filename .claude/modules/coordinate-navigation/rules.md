# Coordinate Navigation Module

Standalone module for coordinate-based location navigation, pathfinding, and map visualization.

## Purpose

Provides spatial positioning and navigation features for open-world campaigns:
- Coordinate calculations (polar coordinates with bearing + distance)
- Bearing-based location creation
- Route finding and path analysis
- Direction blocking (terrain obstacles, radiation zones, cliffs)
- ASCII and GUI map rendering
- Path decision caching

## Activation

**Per-campaign:** Locations have `coordinates` field in `locations.json`.

If coordinates don't exist → module is not used, standard location CRUD works via CORE.

## Dependencies

**From CORE:**
- `lib/json_ops.py` - JSON file operations
- `lib/connection_utils.py` - Canonical connection management

**Module provides:**
- `lib/pathfinding.py` - Coordinate math, bearing calculations, BFS routing
- `lib/path_manager.py` - Path preference caching, route analysis
- `lib/path_intersect.py` - Path-location intersection detection
- `lib/path_split.py` - Automatic path splitting through waypoints
- `lib/map_renderer.py` - ASCII map rendering
- `lib/map_gui.py` - Pygame GUI map (interactive zoom, pan, terrain colors)
- `lib/navigation_manager.py` - High-level API for coordinate navigation

## Tools

### dm-navigation.sh
```bash
# Interactive route decision (caches choice)
bash .claude/modules/coordinate-navigation/tools/dm-navigation.sh decide "Village" "Temple"

# Show all possible routes
bash .claude/modules/coordinate-navigation/tools/dm-navigation.sh routes "Village" "Temple"

# Block direction range (e.g., cliff to the south)
bash .claude/modules/coordinate-navigation/tools/dm-navigation.sh block "Cliff Edge" 160 200 "Steep cliff drop"

# Unblock direction range
bash .claude/modules/coordinate-navigation/tools/dm-navigation.sh unblock "Cliff Edge" 160 200
```

### dm-map.sh
```bash
# ASCII map (full)
bash .claude/modules/coordinate-navigation/tools/dm-map.sh

# ASCII map (colored)
bash .claude/modules/coordinate-navigation/tools/dm-map.sh --color

# Minimap (nearby locations only)
bash .claude/modules/coordinate-navigation/tools/dm-map.sh --minimap --radius 5

# Interactive GUI map (Pygame)
bash .claude/modules/coordinate-navigation/tools/dm-map.sh --gui
```

## Coordinate System

**Origin:** `(0, 0)` at campaign starting location
**Axes:**
- X-axis: West (negative) / East (positive)
- Y-axis: South (negative) / North (positive)
- Units: meters

**Bearing:**
- 0° = North
- 90° = East
- 180° = South
- 270° = West

## Adding Locations with Coordinates

**Via CORE dm-location.sh (calls module internally):**
```bash
# Auto-calculate coordinates from bearing + distance
bash tools/dm-location.sh add "Abandoned Farm" "Ruined homestead" \
  --from "Starting Village" \
  --bearing 90 \
  --distance 2500 \
  --terrain farmland
```

**What happens:**
1. Module calculates coordinates using polar math
2. Creates bidirectional connection with `distance_meters` field
3. Stores reverse bearing for return path
4. Adds terrain metadata

## Path Decision System

When a player tries to reach a location with no direct connection:

### Step 1: Check Cache
System automatically looks for previous routing decision in `path_preferences`.

### Step 2: If No Decision Exists
```bash
bash .claude/modules/coordinate-navigation/tools/dm-navigation.sh decide "Current Location" "Destination"
```

**Decision Options:**
1. **DIRECT PATH** - Straight line (may cross impassable terrain)
2. **USE EXISTING ROUTE** - Follow established connections
3. **BLOCK THIS ROUTE** - Permanently mark as inaccessible

**Caching:** Once decided, the system never asks again for that route pair.

## Directional Blocking

Prevent movement in specific angular ranges (e.g., cliffs, radiation zones):

```bash
# Block south-southeast arc (cliff)
bash .claude/modules/coordinate-navigation/tools/dm-navigation.sh block "Cliff Edge" 160 200 "Steep cliff drop"

# Remove block
bash .claude/modules/coordinate-navigation/tools/dm-navigation.sh unblock "Cliff Edge" 160 200
```

**Use Cases:**
- Cliffs (block south if cliff is to the south)
- Radiation zones (block entire arc toward reactor)
- Impassable terrain (mountains, lakes, walls)

## Map Visualization

### ASCII Map
```bash
# Full map
bash .claude/modules/coordinate-navigation/tools/dm-map.sh

# Custom size
bash .claude/modules/coordinate-navigation/tools/dm-map.sh --width 120 --height 50

# Minimap (nearby only)
bash .claude/modules/coordinate-navigation/tools/dm-map.sh --minimap --radius 5
```

**Map Symbols:**
```
@  = Current location
•  = Other locations
── = Connections
▓  = Fog of war (undiscovered)
```

### GUI Map (Pygame)
```bash
bash .claude/modules/coordinate-navigation/tools/dm-map.sh --gui
```

**Features:**
- Interactive zoom/pan
- Terrain-colored connections
- Click locations for info panel
- Refresh button (reloads JSON data)
- Blocked direction visualization

## Location Schema Example

```json
{
  "Agroprom": {
    "position": "Industrial complex north of starting point",
    "description": "Decaying Soviet-era agricultural facility",
    "coordinates": {
      "x": -1000,
      "y": 3000
    },
    "terrain": "industrial_ruins",
    "connections": [
      {
        "to": "Junkyard",
        "path_description": "Overgrown road",
        "distance_meters": 2000,
        "bearing": 135
      }
    ],
    "blocked_ranges": [
      {
        "from_bearing": 270,
        "to_bearing": 310,
        "reason": "Impassable radiation zone"
      }
    ]
  }
}
```

## When to Use Coordinates

**✅ Recommended For:**
- Open-world exploration (STALKER, Fallout-style)
- Hex-based or grid campaigns
- Tactical positioning matters
- Want visual map representation
- Realistic travel time based on distance

**❌ Not Recommended For:**
- Linear dungeon crawls
- Abstract concept-based locations ("The Dreamrealm")
- Theater-of-the-mind narrative style
- Locations are more thematic than physical

## Integration with CORE

**CORE dm-location.sh automatically detects and uses module when:**
- User provides `--from`, `--bearing`, `--distance` parameters
- Existing location has coordinates field

**Module never touches:**
- Basic location CRUD (handled by CORE `location_manager.py`)
- Connection utils (kept in CORE `lib/connection_utils.py`)
- JSON ops (CORE `lib/json_ops.py`)

**Module provides:**
- Coordinate calculations
- Route pathfinding
- Map rendering
- Navigation decisions

## Backward Compatibility

Standard D&D campaigns continue to work without modification. If locations don't have `coordinates` field, navigation features are simply not available. CORE location CRUD remains functional.

## See Also

- **Schema Reference:** `docs/schema-reference.md`
- **CORE DM Rules:** `CLAUDE.md`
