# World Travel — DM Rules

## Navigation

```bash
bash tools/dm-session.sh move "Temple"
bash tools/dm-session.sh move "Temple" --speed-multiplier 1.5
```

Move = distance/time calc + clock advance + auto encounter check.
**Multi-hop**: if no direct connection, BFS finds shortest route through intermediate locations. Each hop: stats tick → encounter check → arrive. DM gets narrative opportunity at each stop.

### Adding World Locations [MANDATORY]

**NEVER** use CORE `dm-location.sh add` for world-level locations — it creates locations WITHOUT coordinates, invisible on GUI map.

**ALWAYS** use the world-travel navigation manager which auto-calculates coordinates from bearing + distance:

```bash
bash .claude/additional/modules/world-travel/tools/dm-navigation.sh add "New Place" "description" \
  --from "Known Location" --bearing 45 --distance 800 --terrain forest
```

This calculates coordinates from the origin location + bearing/distance, creates the connection, and ensures the location appears on the GUI map immediately.

- `--from` — any existing location with coordinates
- `--bearing` — degrees (0=N, 90=E, 180=S, 270=W)
- `--distance` — meters
- `--terrain` — terrain type for the connecting path

### Connections [MANDATORY]

**NEVER** use CORE `dm-location.sh connect` — it writes dict-format connections incompatible with world-travel's list format, resulting in invisible paths on GUI.

Use the navigation manager for additional connections between existing locations:

```bash
bash .claude/additional/modules/world-travel/tools/dm-navigation.sh connect "A" "B" --terrain forest --distance 2000
```

If `dm-navigation.sh connect` is unavailable, add connections via `dm-navigation.sh add` (which auto-creates origin→new connection) or manually in `locations.json` using the list format:

```json
"connections": [
  {"to": "Target", "path": "2000m на 45°", "distance_meters": 2000, "bearing": 45, "terrain": "forest"}
]
```

**ALWAYS specify `--terrain`**. Default is `open` but DM should pick the correct terrain type for the area.

**Route validation**: direct connections that pass through another location's radius are BLOCKED. Create intermediate connections instead (A→C, C→B).

Route decisions (no direct connection):
```bash
bash .claude/additional/modules/world-travel/tools/dm-navigation.sh decide "Village" "Temple"
```

Direction blocking:
```bash
bash .claude/additional/modules/world-travel/tools/dm-navigation.sh block "Cliff Edge" 160 200 "Steep cliff drop"
bash .claude/additional/modules/world-travel/tools/dm-navigation.sh unblock "Cliff Edge" 160 200
```

Map:
```bash
bash .claude/additional/modules/world-travel/tools/dm-map.sh             # ASCII
bash .claude/additional/modules/world-travel/tools/dm-map.sh --minimap   # nearby
bash .claude/additional/modules/world-travel/tools/dm-map.sh --gui       # Pygame GUI
```

---

## Random Encounters

Auto-fires after every `move`. Manual:
```bash
bash .claude/additional/modules/world-travel/tools/dm-encounter.sh check "Village" "Ruins" 2000 open
```

| Type | Waypoint? | Action |
|------|-----------|--------|
| Combat | Yes | Enemies, initiate combat |
| Social | Yes | NPC encounter, dialogue |
| Hazard | Yes | Obstacle (anomaly, trap) |
| Loot | No | Items found |
| Flavor | No | Atmosphere, continue |

Waypoint = temp location mid-journey. Player: **Forward** or **Back**. Removed after leaving.

DC: `base_dc + (segment_km × distance_modifier) + time_modifier`. Max 30.

Skip encounters when: system disabled, distance < 300m, teleportation, movement inside building, middleware already ran it.

---

## Hierarchical Locations

One flat `locations.json`, tree via `parent`/`children` fields.

| Type | Coordinates | Children | Examples |
|------|------------|----------|----------|
| `world` | Yes | No | Map point |
| `compound` | Yes (top-level) | Yes | City, ship, castle |
| `interior` | No | No | Room, hall |

### Create

```bash
# Compound
bash .claude/additional/modules/world-travel/tools/dm-hierarchy.sh create-compound "Город" --entry-points "Ворота"

# Rooms
bash .claude/additional/modules/world-travel/tools/dm-hierarchy.sh add-room "Ворота" --parent "Город" --entry-point
bash .claude/additional/modules/world-travel/tools/dm-hierarchy.sh add-room "Площадь" --parent "Город" --connections '[{"to": "Ворота"}]'

# Nested compound
bash .claude/additional/modules/world-travel/tools/dm-hierarchy.sh create-compound "Замок" --parent "Город" --entry-points "Ворота замка"
```

### Entry Points

Interior with `is_entry_point: true` + `entry_config`:
- `on_enter`/`on_exit` — DM hint (NOT automated)
- `locked` — blocked until key/solution
- `hidden` — DM knows, player doesn't yet

### Navigate

```bash
bash .claude/additional/modules/world-travel/tools/dm-hierarchy.sh enter "Город" --via "Ворота"
bash .claude/additional/modules/world-travel/tools/dm-hierarchy.sh move "Площадь"
bash .claude/additional/modules/world-travel/tools/dm-hierarchy.sh exit
```

### View

```bash
bash .claude/additional/modules/world-travel/tools/dm-hierarchy.sh tree
bash .claude/additional/modules/world-travel/tools/dm-hierarchy.sh tree "Город"
bash .claude/additional/modules/world-travel/tools/dm-hierarchy.sh validate
```

### Player Position

Player MUST always be on `interior`, never on `compound` directly. Auto-resolves to first entry point on `dm-session.sh start`/`context`.

`location_stack` tracks full path: `["Город", "Замок", "Тронный зал"]`.

NPCs use `tags.locations[]` — association tags, not positional tracking. DM decides sublocation by narrative.

### Interior Rules

- No `coordinates` — GUI uses force-directed layout
- Connections are canonical (stored once, read bidirectionally)
- `diameter_meters` on compounds = visual size on global map

### Interior Terrain [MANDATORY]

Every interior location MUST have a `terrain` field set to distinguish area types on the GUI map. The terrain value maps to `terrain_colors` in `module-data/world-travel.json`.

Common interior terrain types:

| Terrain | Use for | Example color |
|---------|---------|---------------|
| `outdoor` | Open areas, yards, gates, rooftops | [90, 110, 90] |
| `indoor` | Rooms, halls, shops, quarters | [70, 65, 55] |

These terrain types MUST be added to `terrain_colors` in `module-data/world-travel.json` during campaign creation. They are campaign-specific — different genres may use different interior types (e.g. `corridor`, `hangar`, `cave-room`).

When creating a compound with rooms:
1. Add `indoor`/`outdoor` (or genre-appropriate) colors to `terrain_colors`
2. Set `"terrain": "indoor"` or `"terrain": "outdoor"` on each interior location

```json
{
  "terrain_colors": {
    "outdoor": [90, 110, 90],
    "indoor": [70, 65, 55]
  }
}
```

### GUI

- **Global**: top-level locations only. Compounds = squares.
- **Interior**: click compound → select. Click again / Enter button → drill down. Radial tree layout. Node colors reflect terrain type (indoor vs outdoor).
- **Breadcrumb**: `World > City > Castle > Room`. Click = navigate.
- **Player location**: highlighted on both global (parent compound) and interior views.
- **ESC**: go up. **R**: refresh.

---

## Vehicles

Vehicles = compounds with `mobile: true`.

### Create

```bash
bash .claude/additional/modules/world-travel/tools/dm-vehicle.sh create kestrel spacecraft "Станция Кестрел"
bash .claude/additional/modules/world-travel/tools/dm-vehicle.sh add-room kestrel "Мостик" --from "Станция Кестрел" --bearing 90 --distance 10
```

`add-room` creates bidirectional connections automatically.

### Board / Exit

```bash
bash .claude/additional/modules/world-travel/tools/dm-vehicle.sh board kestrel
bash .claude/additional/modules/world-travel/tools/dm-vehicle.sh board kestrel --room "Мостик"
bash .claude/additional/modules/world-travel/tools/dm-vehicle.sh exit
```

Inside vehicle: `dm-session.sh move "Room"` is intercepted — no encounters, no time tick.

### Move Vehicle

```bash
bash .claude/additional/modules/world-travel/tools/dm-vehicle.sh move kestrel "Космостанция Зета-9"
bash .claude/additional/modules/world-travel/tools/dm-vehicle.sh move kestrel --x 5000 --y 3200
```

**To named location**: stops at `stopping_distance` (sum of radii) — never overlaps target.
**To coordinates**: places exactly.

On move: ALL external connections are wiped and rebuilt by proximity (`proximity_radius_meters`). New connections inherit terrain from nearby location. Player inside = travels with vehicle.

### Status

```bash
bash .claude/additional/modules/world-travel/tools/dm-vehicle.sh status
bash .claude/additional/modules/world-travel/tools/dm-vehicle.sh map kestrel
```

---

## Terrain

Campaign-defined in `module-data/world-travel.json`:

```json
{
  "terrain_colors": {
    "wasteland": [140, 120, 80],
    "forest": [50, 100, 50],
    "road": [160, 150, 110],
    "outdoor": [90, 110, 90],
    "indoor": [70, 65, 55]
  }
}
```

No defaults. DM creates types per campaign. Unknown types use `default` fallback color.

### Connection Terrain vs Location Terrain [MANDATORY]

Connection `terrain` = what you WALK THROUGH to get there. It controls the color of the path on the GUI map.

- Connection terrain must be a **traversable surface**: `wasteland`, `forest`, `road`, `swamp`, `plains`, `space`, etc.
- NEVER use destination-specific terrain on connections: `anomaly`, `ruins`, `radiation`, `cave` on a 5km path makes no sense.
- The destination itself can have special properties — handle those as location descriptions, subtypes, or interior terrain.

**Wrong:** `Outpost → Anomaly Field: terrain=anomaly` (5km of anomaly?)
**Right:** `Outpost → Anomaly Field: terrain=wasteland` (you walk through wasteland to reach it)

### Terrain type categories

| Category | Used on | Examples |
|----------|---------|---------|
| **World terrain** | Connections between locations | `wasteland`, `forest`, `road`, `swamp`, `plains`, `mountain`, `space` |
| **Interior terrain** | Interior locations inside compounds | `outdoor`, `indoor`, `corridor`, `hangar`, `cave-room` |

Do NOT mix these — world terrain on connections, interior terrain on compound rooms.

---

## Auto-Compound on Arrival [MANDATORY]

When the player arrives at a NEW location for the first time, evaluate whether it needs interior structure.

**Convert to compound if:**
- Settlement (village, outpost, camp, town, city)
- Building (bar, lab, bunker, warehouse, church)
- Vehicle/ship (boat, truck, helicopter, spaceship)
- Dungeon/cave system with distinct areas
- Any location with 2+ interesting areas inside

**Do NOT convert:**
- Wilderness (forest, field, swamp, wasteland) — uniform terrain, nothing to split
- Roads, bridges, rivers — transit locations
- Abstract/narrative waypoints

**On arrival at convertible location:**
1. Create compound structure (entry point + hub + key rooms)
2. Add `outdoor`/`indoor` terrain to each room
3. Set entry_config on the gate/door if guarded or hidden
4. Enter via entry point, navigate to hub
5. THEN narrate the scene

This ensures every meaningful location has explorable interior from the first visit.

---

## Arrival Awareness

On arrival at dangerous/unfamiliar locations, check passive Perception.

**Passive Perception** = 10 + Wisdom mod (+ proficiency if trained)

| Hidden Element | Typical DC |
|----------------|------------|
| Someone watching openly | 10 |
| Hidden watcher | 15 |
| Well-concealed trap | 15-18 |
| Secret door | 20+ |

- If passive beats DC → mention in description
- If passive fails → element remains hidden (note for later)
- If player actively searches → roll Perception vs DC

## Arrival Narration

Use [Narration](#narration) workflow for the new scene.
