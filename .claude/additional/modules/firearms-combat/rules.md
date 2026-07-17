# Firearms Combat — DM Rules

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

- `single` — one physical round and one attack roll
- `burst` — hold the trigger for 1 second; spend `floor(RPM / 60)` rounds and resolve up to 3 salvos
- `full_auto` — hold the trigger for 3 seconds; spend `floor(RPM / 60 * 3)` rounds and resolve up to 6 salvos per target, 12 total

Physical rounds fired are capped by loaded ammo and weapon magazine capacity. Every fired round is deducted even when every salvo misses.

### Salvo Resolution

- Physical rounds are divided across targets, then grouped into a bounded number of salvos.
- Each salvo makes one attack roll, not one roll per bullet.
- Recoil is cumulative per salvo: `0, -2, -4...`; Sharpshooter uses `0, -1, -2...`.
- A normal hit lands 1 bullet.
- Beating AC by 5 lands 2 bullets; beating AC by 10 lands 3 bullets.
- A salvo cannot land more bullets than it physically contains.
- Natural 20 lands up to 2 bullets, but only the first bullet is critical.
- Natural 1 misses the entire salvo.

The result reports physical `shots_fired`, resolved `salvos_fired`, actual `bullets_hit`, magazine remainder, and whether a reload is required.

---

## Penetration vs Protection

| Condition | Damage |
|-----------|--------|
| PEN > PROT | 100% |
| PEN > PROT/2 | 50% |
| PEN <= PROT/2 | 25% |

---

## Critical Hits

Single fire doubles the damage dice on a natural 20. Automatic fire doubles only the first bullet in a natural-20 salvo; other bullets use normal damage.

---

## After Combat

The resolver automatically:
1. **Writes XP** to `player:active` in WorldGraph (25 XP per kill)
2. **Deducts ammo** from the `player:active` WorldGraph inventory
3. Reports a failed deduction when the ammunition stack is missing or insufficient

---

## Data Location

Fire mode and combat config lives in `module-data/firearms-combat.json` inside the campaign directory:
- `fire_modes` — duration, salvo limits, recoil, hit margin, and hit cap
- `combat_rules` — headshot, cover, suppression, bleed, morale
- `range_rules` — close/normal/long/beyond_long modifiers
- `penetration_vs_armor` — damage scaling rules (PEN vs PROT)
- `combat_style` — hybrid_lethal config

Weapons, armor, and creatures live in `world.json` as WorldGraph nodes. The module writes XP to the player node and deducts physical rounds fired from that node's inventory.

**Nothing stored in campaign-overview.json** — all data in module-data/.

---

## When NOT to Call

- Melee/thrown weapons — use standard D&D attack
- Magic attacks — use standard spell mechanics
- Narrative combat (chase scenes, intimidation) — no dice needed
- Large NPC-vs-NPC combat — use the mass-combat module
