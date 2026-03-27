<!-- slot:loot-and-rewards -->
# Inventory System — DM Rules

Replaces core Loot & Rewards slot. Use `dm-inventory.sh` for ALL inventory/gold/HP/XP/stat changes — never edit JSON files manually.

**ALWAYS combine everything into ONE command.** Multiple flags in a single call — never split into separate invocations:
```bash
# ✅ RIGHT — one call
bash tools/dm-inventory.sh update "Char" --gold -810 --add-unique "Longsword +1 [3.5kg]" --add "Arrows" 30 0.01 --add "Healing Potion" 1 0.3

# ❌ WRONG — five separate calls for the same transaction
bash tools/dm-inventory.sh update "Char" --gold -810 ...
bash tools/dm-inventory.sh update "Char" --add "Arrows" 30 ...
bash tools/dm-inventory.sh update "Char" --add "Healing Potion" 1 ...
```

**Data storage:** Inventory (stackable + unique items) is stored in `module-data/inventory-system.json` (CORE). Character stats (HP, XP, money, abilities) remain in `character.json`. Custom stats live in `module-data/custom-stats.json`.

**Currency:** Money is stored as a single integer in base units (copper pieces for D&D). Campaign denominations are defined in `campaign-overview.json` under `"currency"`. Display: `2537 cp` → `25g 3s 7c`. The `--gold` flag accepts base units (copper) or a string like `"2gp 5sp"`.

**--reason flag:** ALWAYS use `--reason` to label inventory changes:
```bash
bash tools/dm-inventory.sh update "Char" --gold -50 --hp -3 --reason "ambush on the road"
# Output: INVENTORY UPDATE: Char — ambush on the road
```

---

## Weight System

Every item has weight in kilograms. Carry capacity = **STR × 7 kg**.

### Encumbrance Tiers

| Load | Threshold | Speed Penalty | Disadvantage |
|------|-----------|---------------|--------------|
| Normal | 0–100% capacity | none | no |
| Encumbered | 100–130% | −5 ft | no |
| Heavy | 130–160% | −10 ft | no |
| Overloaded | 160–200% | −15 ft | YES (attacks) |
| Immobile | >200% | cannot move | YES |

### Item Weight Format

**Stackable items** — stored as `{"qty": N, "weight": X}` (weight per unit in kg):
```json
"Medkit": {"qty": 5, "weight": 0.3}
```

**Unique items** — weight tag `[Xkg]` at end of string:
```
"Greatsword (2d6+3, heavy) [6kg]"
```

**Default weights** (used when no explicit weight):
| Category | Default weight |
|----------|---------------|
| weapon | 3.0 kg |
| ammo | 0.02 kg |
| food | 0.5 kg |
| medicine | 0.3 kg |
| artifact | 1.0 kg |
| misc | 0.5 kg |

### Remove Items

To remove items from inventory (sold, destroyed, consumed, dropped):

```bash
bash tools/dm-inventory.sh remove "[char]" "[item]" --qty 1
bash tools/dm-inventory.sh remove "[char]" "[item]" --unique
```

Items are permanently removed from inventory. If narratively dropped at a location, DM should note it with `dm-note.sh`.

---

## After Combat / Loot Found

### 1. Persist with dm-inventory.sh [PERSIST BEFORE NARRATING]

```bash
# All-in-one after combat (with optional weight per item)
# --gold value is in base currency units (copper): 250 cp = 2g 5s 0c
bash tools/dm-inventory.sh loot "[char]" \
  --gold 250 --xp 150 --items "Medkit:2:0.3" "Arrows:60:0.02"
```

Format: `Name:Qty` or `Name:Qty:WeightKg`

### 2. Record & Advance
```bash
bash tools/dm-note.sh "combat" "[Character] defeated [X] [enemies] at [location]"
bash tools/dm-time.sh "_" "[date]" --elapsed 0.5
```

---

## Core Commands

### Player uses item

```bash
bash tools/dm-inventory.sh update "[char]" \
  --remove "Medkit" 1 --hp +20
```

### Player buys / sells

```bash
# --gold -500 = subtract 500 cp (= 5g); also accepts --gold "-5gp"
bash tools/dm-inventory.sh update "[char]" \
  --gold -500 --add-unique "Platemail Armor (AC 18) [30kg]"
```

### Player takes damage / gains XP

```bash
bash tools/dm-inventory.sh update "[char]" \
  --hp -10 --xp +200
```

### View inventory (with weight)

```bash
bash tools/dm-inventory.sh show "[char]"
```

### Full weight breakdown

```bash
bash tools/dm-inventory.sh weigh "[char]"
```

---

## Flags Reference

| Flag | Purpose |
|------|---------|
| `--gold N` | Add/subtract money in base units (copper), or string `"2gp 5sp"` (fails if insufficient) |
| `--hp N` | Modify HP (clamped to 0–max) |
| `--xp N` | Add XP |
| `--add "Item" N [W]` | Add stackable item (qty, optional weight in kg) |
| `--remove "Item" N` | Remove stackable item (fails if insufficient) |
| `--add-unique "Item [Xkg]"` | Add unique item with weight tag |
| `--unique-weight "Item" W` | Set weight for unique item being added |
| `--remove-unique "Item"` | Remove unique item (fuzzy match) |
| `--stat name N` | Modify custom stat (hunger, radiation, etc.) |
| `--test` | Preview only — validate without writing |

---

## Validation

All-or-nothing: if any part fails (not enough gold, item missing, stat out of bounds) — **nothing is written**. Use `--test` to check before committing.

After adding items, system warns if encumbered but does NOT block the transaction. DM decides whether to enforce.

---

## Party NPC Inventories

Party members (promoted via `dm-npc.sh promote`) have full inventory + weight tracking. Data stored in `module-data/inventory-party.json`.

### View NPC inventory
```bash
bash tools/dm-inventory.sh show "Grimjaw"
bash tools/dm-inventory.sh weigh "Silara"
```

### Modify NPC inventory
```bash
bash tools/dm-inventory.sh update "Healer" \
  --add "Medkit" 3 0.3 --remove "Bandage" 1
```

### View entire party
```bash
bash tools/dm-inventory.sh party
```

---

## Transfer Items

Transfer items between player and NPC (real bidirectional):

```bash
# Player → NPC
bash tools/dm-inventory.sh transfer "Grimjaw" \
  --item "Medkit" 2 --unique "Spyglass"

# NPC → Player
bash tools/dm-inventory.sh transfer "Player" \
  --from "Grimjaw" --item "Arrows" 30

# NPC → NPC
bash tools/dm-inventory.sh transfer "Silara" \
  --from "Healer" --item "Medkit" 1
```

Items are actually moved — removed from source, added to target with weight preserved.

---

## Category Filter

View inventory filtered by category:

```bash
bash tools/dm-inventory.sh show "[char]" --category weapon
bash tools/dm-inventory.sh show "[char]" --category ammo
```

Categories: `weapon`, `ammo`, `food`, `medicine`, `artifact`, `misc`. Auto-detected by item name keywords.

---

## Item Types

- **Stackable** — consumables with quantity and weight: `{"qty": 5, "weight": 0.3}`
- **Unique** — named items with stats and weight tag: `"Longsword +1 (1d8+3, versatile) [3.5kg]"`
- **Backward compatible** — old format `"Medkit": 5` still works, uses default weight by category
