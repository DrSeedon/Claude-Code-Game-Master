# Inventory System — DM Rules

Replaces core Loot & Rewards slot. Use `dm-inventory.sh` for ALL inventory/gold/HP/XP/stat changes — never edit JSON files manually.

**Data storage:** Inventory (stackable + unique items) is stored in `module-data/inventory-system.json`. Character stats (HP, XP, gold, abilities, custom_stats) remain in `character.json`.

---

## After Combat / Loot Found

### 1. Persist with dm-inventory.sh [PERSIST BEFORE NARRATING]

```bash
# All-in-one after combat
bash .claude/additional/modules/inventory-system/tools/dm-inventory.sh loot "[char]" \
  --gold 250 --xp 150 --items "Medkit:2" "Ammo 5.56mm:60"
```

### 2. Record & Advance
```bash
bash tools/dm-note.sh "combat" "[Character] defeated [X] [enemies] at [location]"
bash tools/dm-time.sh "[new_time]" "[date]"
bash tools/dm-consequence.sh check
```

---

## Core Commands

### Player uses item

```bash
bash .claude/additional/modules/inventory-system/tools/dm-inventory.sh update "[char]" \
  --remove "Medkit" 1 --hp +20
```

### Player buys / sells

```bash
bash .claude/additional/modules/inventory-system/tools/dm-inventory.sh update "[char]" \
  --gold -500 --add-unique "Platemail Armor (AC 18)"
```

### Player takes damage / gains XP

```bash
bash .claude/additional/modules/inventory-system/tools/dm-inventory.sh update "[char]" \
  --hp -10 --xp +200
```

### View inventory

```bash
bash .claude/additional/modules/inventory-system/tools/dm-inventory.sh show "[char]"
```

---

## Flags Reference

| Flag | Purpose |
|------|---------|
| `--gold N` | Add/subtract gold (fails if insufficient) |
| `--hp N` | Modify HP (clamped to 0–max) |
| `--xp N` | Add XP |
| `--add "Item" N` | Add stackable item (merges with existing) |
| `--remove "Item" N` | Remove stackable item (fails if insufficient) |
| `--add-unique "Item"` | Add unique item (weapon, armor, quest) |
| `--remove-unique "Item"` | Remove unique item (fuzzy match) |
| `--stat name N` | Modify custom stat (hunger, radiation, etc.) |
| `--test` | Preview only — validate without writing |

---

## Validation

All-or-nothing: if any part fails (not enough gold, item missing, stat out of bounds) — **nothing is written**. Use `--test` to check before committing.

---

## Transfer Items

Give items from character to NPC (narratively):

```bash
bash .claude/additional/modules/inventory-system/tools/dm-inventory.sh transfer "[char]" \
  --item "Medkit" 2 --unique "AK-74 (5.45mm)"
```

Items are removed from character inventory. NPC receives them narratively (no NPC inventory tracking).

---

## Category Filter

View inventory filtered by category:

```bash
bash .claude/additional/modules/inventory-system/tools/dm-inventory.sh show "[char]" --category weapon
bash .claude/additional/modules/inventory-system/tools/dm-inventory.sh show "[char]" --category ammo
```

Categories: `weapon`, `ammo`, `food`, `medicine`, `artifact`, `misc`. Auto-detected by item name keywords.

---

## Item Types

- **Stackable** — consumables with quantity: Medkit, Ammo, Food, Potions
- **Unique** — named items with full stats in the name: `"AK-74 (5.56mm, 2d6+2, PEN 3)"`, `"Leather Armor (AC 11)"`
