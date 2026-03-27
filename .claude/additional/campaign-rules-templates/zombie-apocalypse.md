## id
zombie-apocalypse

## name
Zombie Apocalypse

## description
The dead walk. Civilization collapsed months ago. Small groups of survivors scavenge ruins, fortify shelters, and face impossible choices. Every supply run is a gamble. Every stranger is a threat. The horde never stops.

## genres
survival, horror, post-apocalyptic, zombie, walking-dead, last-of-us

## recommended_for
Campaigns focused on desperate survival, resource scarcity, moral dilemmas, tense combat encounters, and base-building under constant threat. Every session has stakes.

## rules

### Infection
The zombie virus is airborne — everyone is already infected. Death = reanimation in 1d4 minutes unless the brain is destroyed.

**Bite/scratch infection** accelerates the process:
- Bitten: CON save DC 15 every hour. Three failures = turn in 1d6 hours. No cure — only amputation within 10 minutes (if limb).
- Scratched: CON save DC 12 every 4 hours. Two failures = fever, then bite-level progression.
- Symptom stages: Fever → Sweating → Delirium → Aggression → Death → Reanimation

### Zombie types
| Type | HP | AC | Attack | Speed | Special |
|------|----|----|--------|-------|---------|
| Shambler | 8 | 8 | +2, 1d6 bite | 15ft | Basic, slow, numerous |
| Runner | 12 | 10 | +4, 1d6 bite | 40ft | Fast, attracted to noise |
| Bloater | 25 | 6 | +1, 1d8 slam | 10ft | Explodes on death: 10ft, DC 13 DEX or 2d6 acid + infection |
| Screamer | 6 | 9 | +2, 1d4 | 20ft | Scream: attracts all zombies within 500m, 1d4 rounds to arrive |
| Tank | 40 | 14 | +6, 2d8 slam | 20ft | Resistant to non-headshot damage. Only crits or called shots (DC 16) deal full damage |

**Headshot rule:** Called shot to the head: -5 to attack roll. If hits = instant kill on any zombie. Nat 20 = always headshot.

### Noise and hordes
Every loud action has a **Noise Level** (1-10):
| Action | Noise |
|--------|-------|
| Whisper, melee kill | 1 |
| Talking, breaking glass | 3 |
| Shouting, car alarm | 5 |
| Gunshot (suppressed) | 4 |
| Gunshot (unsuppressed) | 7 |
| Explosion | 10 |

**Horde check:** After any Noise 4+, roll d20. If result ≤ Noise Level, zombies are attracted:
- Noise 4-5: 1d6 shamblers arrive in 2d4 minutes
- Noise 6-7: 2d6 mixed (shamblers + runners) in 1d4 minutes
- Noise 8-9: 3d6 mixed + 1 special in 1d4 rounds
- Noise 10: Horde event — 5d10 zombies converge over next hour. Run or die.

### Survival resources
Three vital stats tracked via custom-stats:
- **Hunger**: -15/day without food. At 0: Exhaustion (-2 all rolls). Below 0 for 3 days: death.
- **Thirst**: -25/day without water. At 0: -3 all rolls, hallucinations. Below 0 for 2 days: death.
- **Morale**: drops from trauma, death of allies, failed missions. At 0: panic, desertion checks for NPCs.

**Scavenging:** Each building has a Loot Rating (d20):
- 1-5: Picked clean. Nothing useful.
- 6-10: Scraps. 1d4 random minor items.
- 11-15: Decent. 1d6 items including food/water/ammo.
- 16-19: Jackpot. Medical supplies, weapons, or rare find.
- 20: Cache. Someone's hidden stash — full supply drop.

Already-looted buildings: -5 to Loot Rating. Dangerous areas (hospitals, military bases): +5 but higher zombie density.

### Combat — ammunition matters
**Ammo is tracked per bullet.** No abstract "you have enough."

| Weapon | Damage | Noise | Ammo/shot | Notes |
|--------|--------|-------|-----------|-------|
| Knife/machete | 1d6 | 1 | — | Silent, reliable |
| Baseball bat | 1d8 | 2 | — | Breaks on nat 1 |
| Bow | 1d8 | 2 | 1 arrow | Recoverable 50% |
| Pistol | 1d10 | 7 | 1 | Common ammo |
| Pistol (suppressed) | 1d10 | 4 | 1 | Suppressor degrades: -1 per 20 shots |
| Shotgun | 2d8 | 8 | 1 shell | +2 vs groups, spread |
| Rifle | 1d12 | 7 | 1 | Range advantage |
| Molotov | 2d6 fire | 5 | — | Area, fire persists 1d4 rounds |

### Shelter and base
Survivors need a base. Base has stats:
- **Fortification** (0-100): how well defended. Zombies breach at 0.
- **Supplies** (days): food/water stockpile.
- **Population**: mouths to feed, hands to work.
- **Stealth** (0-20): how hidden. High stealth = fewer random attacks.

**Weekly base events** (d20):
- 1-3: Horde probe — Fortification test
- 4-6: Stranger arrives — trust check
- 7-9: Supply shortage — something critical runs out
- 10-12: Internal conflict — morale check
- 13-15: Quiet week — repairs and rest
- 16-18: Opportunity — nearby cache, trade caravan, or ally
- 19-20: Major event — military signal, cure rumor, rival faction move

### Human threat
Other survivors are often more dangerous than zombies:
- **Traders**: neutral, will trade fairly but won't help for free
- **Bandits**: rob at gunpoint. Fight = noise = zombies
- **Cults**: believe the dead are divine punishment. Unpredictable
- **Military remnants**: organized, armed, authoritarian. "Join or leave."
- **Trust system**: NPC trust earned slowly, lost instantly. Betrayal = permanent hostility.

### Weather and environment
- **Rain**: -2 Perception, tracks washed away, fires harder to start
- **Fog**: visibility 30ft, zombies get surprise on 1-3 (d6)
- **Night**: disadvantage on Perception, zombies +2 to stealth
- **Winter**: Thirst -15/day (snow = water), but Hunger -20/day (cold burns calories). Zombies slower (Speed /2) but don't freeze.

### Death and new characters
Character death is permanent. No resurrection in zombie apocalypse.
- New character: another survivor found/rescued. Starts with basic gear only.
- Dead character's gear: lootable if body is accessible.
- Reanimated PCs: become a zombie encounter for the group. DM controls.

### Modules
- **custom-stats**: hunger, thirst, morale tracking with auto-tick
- **firearms-combat** (optional): if you want detailed gun mechanics with burst/auto modes
