# Firearms Combat — DM Rules [DEPRECATED — uses old managers, pending WorldGraph migration]

---

## When to Use

When player fires a ranged weapon in combat. Call `dm-combat.sh resolve` instead of standard D&D attack rolls.

**Skip when:** melee combat, magic, single thrown weapons, narrative-only outcomes.

---

## Resolving Combat

```bash
bash .claude/additional/modules/firearms-combat/tools/dm-combat.sh resolve \
  --attacker "[char]" \
  --weapon "AK-74" \
  --fire-mode full_auto \
  --ammo 30 \
  --targets "Bandit:13:20:2" "Bandit:13:20:2"
```

**Target format:** `Name:AC:HP:PROT`

Use `--test` to preview without writing changes.

---

## Fire Modes

- `single` — one shot, no penalty, 1 ammo
- `burst` — 3 shots (or less if low ammo), progressive penalty: -3/-6 per shot (Sharpshooter: -2/-4)
- `full_auto` — RPM-based shot count, max 10 shots per target, progressive -3 per shot (Sharpshooter: -2)

### Full Auto Balance Rules

Full auto is capped at **10 shots per target** regardless of RPM or ammo. This prevents spray-and-pray from being an instant kill button. Penalty is steep: by shot 4 a normal shooter is at -9 to attack. Sharpshooter fares better but still degrades fast.

Effective shots (where hit chance > 50%) for AK-74 vs AC 13:
- Normal (+5 base): ~2-3 shots
- Sharpshooter (+8 base): ~4-5 shots

---

## Penetration vs Protection

| Condition | Damage |
|-----------|--------|
| PEN > PROT | 100% |
| PEN > PROT/2 | 50% |
| PEN <= PROT/2 | 25% |

---

## Critical Hits

Natural 20 on any shot -> double damage dice (modifiers unchanged). Natural 1 -> auto-miss.

---

## After Combat

The resolver automatically:
1. **Writes XP** to character file (25 XP per kill)
2. **Deducts ammo** via CORE inventory (dm-inventory.sh)
3. If inventory is not available, prints manual deduction note

---

## Data Location

ALL firearms config lives in `module-data/firearms-combat.json` inside the campaign directory:
- `weapons` — weapon stats (damage, pen, rpm, magazine, type)
- `fire_modes` — penalty values, max_shots_per_target
- `armor` — armor types with PROT and AC bonus
- `bestiary` — enemy types with HP, AC, PROT, attack, damage, speed, CR, XP
- `combat_rules` — headshot, cover, suppression, bleed, morale
- `range_rules` — close/normal/long/beyond_long modifiers
- `penetration_vs_armor` — damage scaling rules (PEN vs PROT)
- `combat_style` — hybrid_lethal config

The module writes XP to `character.json` and deducts ammo via CORE inventory.

**Nothing stored in campaign-overview.json** — all data in module-data/.

---

## When NOT to Call

- Melee/thrown weapons — use standard D&D attack
- Magic attacks — use standard spell mechanics
- Narrative combat (chase scenes, intimidation) — no dice needed
- NPC-vs-NPC combat — resolve narratively, no resolver call
