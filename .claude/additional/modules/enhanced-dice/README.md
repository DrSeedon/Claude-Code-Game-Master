# enhanced-dice

Transparent dice rolling with labels, DC/AC checks, and cheat-proof output. Replaces the vanilla dice-rolling slot.

---

## What Is This

A middleware module that intercepts `tools/dm-roll.sh` and adds `--label`, `--dc`, and `--ac` flags. Every roll shows who rolled, what for, and whether they passed — all declared before the result appears. No more rolling first and deciding DC after.

**Works with any genre** — fantasy, sci-fi, modern, horror. Labels are freeform text.

---

## CORE vs enhanced-dice

| Feature | Vanilla CORE | enhanced-dice |
|---------|-------------|---------------|
| Basic roll | `uv run python lib/dice.py "1d20+5"` | `bash tools/dm-roll.sh "1d20+5" --label "..." --dc N` |
| Labels | None | `--label "Perception (Grimjaw)"` |
| DC check | DM declares separately, compares manually | `--dc 15` → auto `✓ SUCCESS` / `✗ FAIL` |
| AC check | DM declares separately, compares manually | `--ac 16` → auto `✓ HIT!` / `✗ MISS` |
| Nat 20/1 | Shows in CORE output | `⚔ CRITICAL!` / `💀 FUMBLE!` overrides DC/AC |
| Advantage modifier | Broken (modifier ignored) | Fixed via CORE bugfix |
| Transparency | Trust the DM | DC/AC baked into output line |

---

## Architecture

```
tools/dm-roll.sh                    <-- CORE bash wrapper (thin)
  └─ dispatch_middleware "dm-roll.sh"
       └─ enhanced-dice/middleware/dm-roll.sh
            └─ enhanced-dice/lib/enhanced_dice.py
                 └─ lib/dice.py (CORE DiceRoller)
```

- Middleware always intercepts (exit 0) — CORE `dice.py` CLI is never called directly
- `enhanced_dice.py` imports `DiceRoller` from CORE as a library
- No campaign data, no JSON files, no state — pure stateless tool

---

## Usage

```bash
# Skill check
bash tools/dm-roll.sh "1d20+4" --label "Perception (Grimjaw)" --dc 15
# 🎲 Perception (Grimjaw) vs DC 15: [16] +4 = 20 — ✓ SUCCESS

# Attack roll
bash tools/dm-roll.sh "1d20+5" --label "Longsword (Conan)" --ac 16
# 🎲 Longsword (Conan) vs AC 16: [20] +5 = 25 — ⚔ CRITICAL!

# Advantage
bash tools/dm-roll.sh "2d20kh1+5" --label "Attack (advantage)" --ac 14
# 🎲 Attack (advantage) vs AC 14: [17] (dropped 4) +5 = 22 — ✓ HIT!

# Damage (no DC/AC)
bash tools/dm-roll.sh "2d6+3" --label "Longsword Damage"
# 🎲 Longsword Damage: [4+6] +3 = 13

# Batch related rolls
bash tools/dm-roll.sh "1d20+4" --label "Perception (Рекс)" --dc 12 && \
bash tools/dm-roll.sh "1d20+7" --label "Perception (Асока)" --dc 12 && \
bash tools/dm-roll.sh "1d20+3" --label "Perception (Глюк)" --dc 12
```

---

## Flags

| Flag | Purpose |
|------|---------|
| `--label "text"` / `-l "text"` | Who and what (mandatory) |
| `--dc N` | Difficulty Class (skill checks, saves) |
| `--ac N` | Armor Class (attack rolls) |
