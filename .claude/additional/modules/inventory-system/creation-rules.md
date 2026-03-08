# Inventory System — Creation Rules

> Instructions for DM (Claude) when building a new campaign with this module active.
> Run DURING character creation (after character stats are set).

---

## Step 1: Starting Equipment Philosophy

Based on campaign genre, suggest a starting loadout style:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  STARTING INVENTORY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

How does your character start?

  [1] POOR — minimal gear, must scavenge
      A knife, ragged clothes, 10 gold

  [2] STANDARD — balanced starting kit
      Basic weapon, light armor, 50 gold + adventuring gear

  [3] EQUIPPED — ready for action
      Quality weapon, medium armor, 150 gold + full kit

  [4] CUSTOM — define starting items manually

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

Genre presets:
- STALKER/Fallout: POOR or EQUIPPED (depending on character background)
- Fantasy adventurer: STANDARD
- Military operative: EQUIPPED
- Amnesiac/prisoner: POOR

---

## Step 2: Build Starting Inventory

Based on genre and choice, propose a concrete item list **with weights**.

**Sci-Fi Military EQUIPPED example:**
```
Stackable:
  Заряд DC-15A × 200  (0.02 kg each = 4.0 kg)
  Заряд DC-17 × 48     (0.02 kg each = 0.96 kg)
  Медпак × 3            (0.3 kg each = 0.9 kg)
  Паёк × 5              (0.5 kg each = 2.5 kg)

Unique:
  DC-15A (штурмовая, 2d6+2, PEN 3) [4.5kg]
  DC-17 (пистолет, 2d4+1, PEN 1) [1.2kg]
  Фаза I клон (AC 14, PROT 4) [12kg]

Total: ~26 kg / STR 15 × 7 = 105 kg capacity — Normal
Gold: 200 credits
```

**Fantasy STANDARD example:**
```
Stackable:
  Стрела × 20           (0.05 kg each = 1.0 kg)
  Зелье лечения × 2     (0.3 kg each = 0.6 kg)
  Факел × 5             (0.5 kg each = 2.5 kg)
  Рацион × 3            (0.5 kg each = 1.5 kg)

Unique:
  Короткий меч (1d6, фехтование) [1.0kg]
  Кожаный доспех (AC 11) [5.0kg]
  Рюкзак путника [2.5kg]

Total: ~14 kg / STR 12 × 7 = 84 kg capacity — Normal
Gold: 50 GP
```

Always show the list with weight totals and ask: **"Edit anything or looks good?"**

---

## Step 3: Write Inventory

Use dm-inventory.sh with weight parameters:

```bash
# Stackable: --add "Item" QTY WEIGHT_KG
bash .claude/additional/modules/inventory-system/tools/dm-inventory.sh update "[CharName]" \
  --gold 200 \
  --add "Заряд DC-15A" 200 0.02 \
  --add "Заряд DC-17" 48 0.02 \
  --add "Медпак" 3 0.3 \
  --add "Паёк" 5 0.5 \
  --add-unique "DC-15A (штурмовая, 2d6+2, PEN 3) [4.5kg]" \
  --add-unique "DC-17 (пистолет, 2d4+1, PEN 1) [1.2kg]" \
  --add-unique "Фаза I клон (AC 14, PROT 4) [12kg]"
```

Or via loot shorthand (Name:Qty:WeightKg):
```bash
bash .claude/additional/modules/inventory-system/tools/dm-inventory.sh loot "[CharName]" \
  --gold 200 --items "Заряд DC-15A:200:0.02" "Медпак:3:0.3" "Паёк:5:0.5"
```

---

## Step 4: Confirm with Preview

After writing, show inventory with weight:

```bash
bash .claude/additional/modules/inventory-system/tools/dm-inventory.sh show "[CharName]"
bash .claude/additional/modules/inventory-system/tools/dm-inventory.sh weigh "[CharName]"
```

---

## Notes

- Always use `dm-inventory.sh update` (not direct JSON) when inventory already exists — avoids clobbering other fields
- Inventory is stored in `module-data/inventory-system.json`, NOT in `character.json`
- Gold stays in `character.json` (it's a character stat)
- Unique items: include ALL stats in the name string + weight tag `[Xkg]`
- Stackable items: weight is per unit, stored as `{"qty": N, "weight": X}`
- If no weight specified, defaults by category: weapon 3.0, ammo 0.02, food 0.5, medicine 0.3, artifact 1.0, misc 0.5
- Carry capacity = STR × 7 kg. Overload = speed penalty + disadvantage
- If custom-stats module is also active, do NOT set custom_stats here — that's handled by custom-stats creation-rules
- Starting gold should feel appropriate to genre: medieval GP, post-apoc rubles/caps, sci-fi credits
