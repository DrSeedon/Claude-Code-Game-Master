## XP & Rewards <!-- slot:xp-rewards -->

### Automatic Combat XP [MANDATORY]

Every combat creature must define an integer `xp` reward. Player auto-combat
awards that XP in the same transaction as the killing blow and marks the
creature reward as paid. Repeated attacks, repeated narration, and repeated
status checks never award it again.

Do not call `dm-player.sh xp` after an auto-combat kill.

### Automatic Quest XP [MANDATORY]

Every quest must be created with an explicit non-negative reward:

```bash
bash tools/dm-plot.sh add "[quest]" --type side --desc "[situation and stakes]" --xp 100
```

`dm-plot.sh complete "[quest]"` awards the stored reward exactly once. Repeating
the completion command reports that XP was already awarded.

### Manual Non-Combat XP

Use manual XP only for an ad hoc achievement or milestone that is not already
represented by a creature or completed quest:

```bash
bash tools/dm-player.sh xp "[character]" +[amount]
```

**XP by Challenge Rating:**
| CR | XP | CR | XP | CR | XP | CR | XP |
|----|-----|----|----|----|----|----|----|
| 0 | 10 | 3 | 700 | 7 | 2,900 | 13 | 10,000 |
| 1/8 | 25 | 4 | 1,100 | 8 | 3,900 | 14 | 11,500 |
| 1/4 | 50 | 5 | 1,800 | 9 | 5,000 | 15 | 13,000 |
| 1/2 | 100 | 6 | 2,300 | 10 | 5,900 | 17 | 18,000 |
| 1 | 200 | | | 11 | 7,200 | 20 | 25,000 |
| 2 | 450 | | | 12 | 8,400 | | |

Apply clever tactics, creative solutions, and social victories as manual
non-combat awards only when they are not already included in a quest reward.

**Non-Combat XP Awards (DM Discretion):**
| Category | XP Range | Examples |
|----------|----------|----------|
| Minor | 10-25 XP | Good roleplay moment, clever idea, minor puzzle |
| Moderate | 50-100 XP | Overcome non-combat challenge, excellent RP, gather key intel |
| Major | 100-250 XP | Solve complex puzzle, diplomatic victory, avoid deadly combat |
| Epic | 250-500 XP | Story milestone, major character growth, significant discovery |

---
