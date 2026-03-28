# Firearms Combat — Creation Rules

> Instructions for DM (Claude) when building a new campaign with this module active.
> Run DURING Phase 2 of /new-game (world/tone setup), before character creation.

---

## Step 1: Pick Weapon Preset or Customize

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  FIREARMS SYSTEM SETUP
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Select weapon set for your campaign:

  [1] STALKER / POST-SOVIET
      AKM, AK-74, SVD, PM Pistol, SPAS-12
      Armor: leather jacket -> military armor -> exoskeleton

  [2] MODERN MILITARY
      M4A1, SCAR-H, MP5, Glock 17, M249 SAW
      Armor: plate carrier -> full plate -> EOD suit

  [3] SCI-FI / CYBERPUNK
      Plasma rifle, railgun, smart pistol, heavy bolter
      Armor: light mesh -> combat armor -> powered exo

  [4] CUSTOM — define weapons manually

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## Step 2: Customize Weapons (if needed)

For each weapon the user wants to add or modify, gather:

| Field | Question |
|-------|----------|
| `damage` | Dice notation? (e.g. `2d8+2`) |
| `pen` | Armor penetration rating? (1-10 scale) |
| `rpm` | Rounds per minute? (pistol ~30, rifle ~600, SMG ~800) |
| `magazine` | Magazine size? (reference only) |
| `type` | assault_rifle / pistol / sniper_rifle / shotgun / smg |

Show a preview table before writing:

```
  Weapon          Damage    PEN   RPM   Type
  ─────────────────────────────────────────
  AK-74           2d6+2     3     650   assault_rifle
  SVD Dragunov    2d10+4    5     30    sniper_rifle
  PM Pistol       2d4+1     1     30    pistol
```

---

## Step 3: Write Firearms Config to Campaign

Write ONLY fire_modes config into `module-data/firearms-combat.json` (weapons go to world.json — see Step 7):

```bash
CAMPAIGN_DIR=$(bash tools/dm-campaign.sh path)
mkdir -p "$CAMPAIGN_DIR/module-data"
```

```json
{
  "enabled": true,
  "fire_modes": {
    "single": {
      "attacks": 1,
      "ammo": 1,
      "penalty": 0
    },
    "burst": {
      "penalty_per_shot": -3,
      "penalty_per_shot_sharpshooter": -2
    },
    "full_auto": {
      "penalty_per_shot": -3,
      "penalty_per_shot_sharpshooter": -2,
      "max_shots_per_target": 10
    }
  },
  "penetration_vs_armor": {
    "pen_greater": "PEN > PROT = full damage",
    "pen_equal_or_less": "PEN <= PROT = half damage",
    "pen_half_or_less": "PEN <= PROT/2 = quarter damage"
  },
  "range_rules": {
    "close": "+2 attack", "normal": "+0", "long": "-2", "beyond_long": "Disadvantage"
  },
  "combat_style": {
    "style": "hybrid_lethal",
    "comment": "Small fights = 1-3 rolls narrative. Serious fights = full turn-based."
  }
}
```

Save this to `$CAMPAIGN_DIR/module-data/firearms-combat.json`.

Use the template at `templates/modern-firearms-campaign.json` as reference — it has full STALKER presets with weapons, armor, enemies, and subclasses.

---

## Step 4: Set Character Subclass

If the character is a combat specialist, ask:

```
Combat subclass?

  [1] Sharpshooter (Fighter)
      +2 attack bonus on ranged
      Full-auto/burst penalty: -2/shot instead of -3

  [2] Sniper (Rogue)
      Crit on 19-20 (roleplay rule)
      Double range without penalty

  [3] None — standard D&D attack

```

Write to character.json if subclass selected:
```python
char['subclass'] = 'Стрелок'  # or 'Sniper'
```

---

## Step 5: Confirm Armor Scale

Show the armor protection table for this campaign:

```
  Armor                  AC    PROT
  ────────────────────────────────
  No armor               10    0
  Light jacket           11    1
  Body armor (soft)      13    3
  Military plate         15    5
  Powered exoskeleton    17    7
```

Ask: "Does this fit your setting, or adjust armor ratings?"

---

## Step 6: Starting Loadout

Ask the player what weapon(s) they start with. Confirm ammo count.

If `inventory-system` module is also active — ammo will be tracked there. If not, ammo is passed as `--ammo` argument each combat and tracked narratively.

---

## Step 7: Add Weapons, Armor & Bestiary to world.json

Reference data goes into world.json as nodes. Use `dm-world.sh` to add them:

**Weapons** — one node per weapon:
```bash
bash tools/dm-world.sh add-node "weapon:ak-74" --name "AK-74 (5.45x39mm)" --type weapon --data '{"damage":"2d6+2","pen":3,"rpm":650,"magazine":30,"weapon_type":"assault_rifle","ammo_type":"5.45x39mm","source_module":"firearms-combat"}'
bash tools/dm-world.sh add-node "weapon:akm" --name "AKM (7.62x39mm)" --type weapon --data '{"damage":"2d8+3","pen":4,"rpm":600,"magazine":30,"weapon_type":"assault_rifle","ammo_type":"7.62x39mm","source_module":"firearms-combat"}'
bash tools/dm-world.sh add-node "weapon:svd" --name "SVD Dragunov (7.62x54mm)" --type weapon --data '{"damage":"2d10+4","pen":5,"rpm":30,"magazine":10,"weapon_type":"sniper_rifle","ammo_type":"7.62x54mm","source_module":"firearms-combat"}'
bash tools/dm-world.sh add-node "weapon:pm-pistol" --name "PM Pistol (9x18mm)" --type weapon --data '{"damage":"2d4+1","pen":1,"rpm":30,"magazine":8,"weapon_type":"pistol","ammo_type":"9x18mm","source_module":"firearms-combat"}'
```

Node ID format: `weapon:<kebab-id>` — must be lowercase, hyphens only (e.g. `weapon:glock-17`, `weapon:m4a1`).

Required fields in `data`: `damage` (dice notation), `pen` (1-10), `rpm`, `magazine`, `weapon_type`.
Optional: `ammo_type` (for auto-deduct), `source_module` (for filtering).

**Armor** — one node per armor type:
```bash
bash tools/dm-world.sh add-node "armor:leather-jacket" --name "Leather Jacket" --type armor --data '{"ac_bonus":1,"prot":1,"weight":"light","source_module":"firearms-combat"}'
bash tools/dm-world.sh add-node "armor:military-plate" --name "Military Plate Armor" --type armor --data '{"ac_bonus":5,"prot":5,"weight":"heavy","source_module":"firearms-combat"}'
bash tools/dm-world.sh add-node "armor:exoskeleton" --name "Powered Exoskeleton" --type armor --data '{"ac_bonus":7,"prot":7,"weight":"powered","source_module":"firearms-combat"}'
```

**Bestiary** — one node per enemy type:
```bash
bash tools/dm-world.sh add-node "creature:bandit" --name "Bandit" --type creature --data '{"hp":20,"ac":13,"prot":2,"attack":"+3","damage":"2d4+1","pen":1,"speed":30,"cr":"1/2","xp":100,"source_module":"firearms-combat"}'
bash tools/dm-world.sh add-node "creature:mercenary" --name "Mercenary" --type creature --data '{"hp":30,"ac":16,"prot":3,"attack":"+5","damage":"2d6+2","pen":3,"speed":30,"cr":"2","xp":450,"source_module":"firearms-combat"}'
```

**Combat rules** — add to `module-data/firearms-combat.json` under `"combat_rules"`:
```json
"combat_rules": {
  "headshot": "Natural 20 on firearms = triple damage",
  "cover": "Full +5 AC, partial +2 AC",
  "suppression": "Full auto suppression zone 15ft, DEX DC 14 or Prone",
  "bleed": "Crit from claws/fangs = 1d4 bleed/round until Medicine DC 12",
  "morale": "50%+ allies dead: WIS DC 10 or flee"
}
```

Adapt bestiary and combat rules to fit the campaign genre.

---

## Data Written

After creation, the module's data lives in:
- `module-data/firearms-combat.json` — **config only**: fire_modes, penetration_vs_armor, range_rules, combat_style, combat_rules
- `world.json` — **reference data**: weapon nodes (`weapon:*`), armor nodes (`armor:*`), creature/bestiary nodes (`creature:*`)
- `character.json` -> `subclass` field (if Sharpshooter/Sniper selected)

Config MUST be in `module-data/firearms-combat.json` — the resolver will error if missing.
Weapons, armor, bestiary MUST be in world.json as nodes — the resolver reads ONLY from there.

---

## Notes

- If user picks CUSTOM weapons: ask for each weapon one by one, keep the table running
- Firearms system is ONLY active when `module-data/firearms-combat.json` exists in the campaign directory
- Ammo for starting loadout is handled by inventory-system creation-rules — coordinate if both modules active
- Fire mode penalties are configurable per-campaign via `fire_modes` in `module-data/firearms-combat.json`
