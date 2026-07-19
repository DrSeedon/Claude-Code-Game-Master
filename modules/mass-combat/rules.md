# Mass Combat — DM Rules

Mass combat tracks groups and zones while preserving individual HP, attacks,
conditions, and deaths. It owns battlefield scale; it does not define weapon
or armor semantics.

The compiled **Resolved Gameplay Profile** is authoritative for actions outside
this module and for any active combat profile. Never guess another resolver or
call one process per unit.

## When to Use

Use mass combat when a battle has multiple NPCs, squads, factions, tactical
zones, cover, or repeated group maneuvers. Use the individual route from the
resolved profile for a small duel or a single isolated attack.

## Resolution Contract

- One `round` call resolves one attacking group.
- Every participating unit rolls separately and applies damage separately.
- `combat_profile` is opaque provider data. Mass combat stores and forwards it
  but never interprets its fields.
- With no active damage provider, attacks use ordinary D&D AC, attack, and
  damage resolution.
- With an active damage provider, the provider runs inside the mass action.
- Initiative remains a CORE operation and is rolled once for the complete
  encounter.

## Setup

```bash
bash modules/mass-combat/tools/dm-mass-combat.sh templates
bash modules/mass-combat/tools/dm-mass-combat.sh init "Battle Name"

bash modules/mass-combat/tools/dm-mass-combat.sh add \
  --faction enemies --group Bandits-North \
  --template BanditRaider --count 6

bash modules/mass-combat/tools/dm-mass-combat.sh add \
  --faction allies --group KingsGuard \
  --template RoyalGuard --count 1 --names "Ser Aldric"

bash modules/mass-combat/tools/dm-mass-combat.sh add \
  --faction allies --group KingsGuard --type Veteran --count 1 \
  --ac 14 --hp 30 --atk 6 --dmg "2d6+3" --names "Gareth"
```

Only pass `--profile '<json>'` when the resolved gameplay profile defines the
active provider schema. The object is stored unchanged.

## Round Flow

1. Run `next-round`.
2. Resolve each enemy group with one `round` call.
3. Ask for the player's action and use the exact route in the resolved profile.
4. Resolve allied groups with one `round` call.
5. Run `status`.
6. Narrate the mechanical results without inventing extra attacks or damage.

## Commands

### Group attack

```bash
bash modules/mass-combat/tools/dm-mass-combat.sh round \
  Bandits-North --target-group KingsGuard

bash modules/mass-combat/tools/dm-mass-combat.sh round \
  Bandits-North --target-group KingsGuard --count 4

bash modules/mass-combat/tools/dm-mass-combat.sh round \
  RoyalGuard --target-faction enemies --advantage
```

### Named-unit attack

```bash
bash modules/mass-combat/tools/dm-mass-combat.sh attack \
  "Ser Aldric" --targets Bandit-01 Bandit-02

bash modules/mass-combat/tools/dm-mass-combat.sh attack \
  Archer-01 --targets BanditLeader-01 --atk 8 --dmg "2d10+4"
```

### Area and crewed attacks

```bash
bash modules/mass-combat/tools/dm-mass-combat.sh aoe "Alchemist Fire" \
  --targets Bandit-01 Bandit-02 Bandit-03 \
  --damage "5d6" --save-type DEX --save-dc 14

bash modules/mass-combat/tools/dm-mass-combat.sh turret \
  Catapult-01 --target-group Infantry
```

### State changes and maneuvers

```bash
bash modules/mass-combat/tools/dm-mass-combat.sh cover KingsGuard
bash modules/mass-combat/tools/dm-mass-combat.sh cover KingsGuard --remove
bash modules/mass-combat/tools/dm-mass-combat.sh move Guard-01 Guard-02 --to Gate
bash modules/mass-combat/tools/dm-mass-combat.sh damage "Ser Aldric" 5
bash modules/mass-combat/tools/dm-mass-combat.sh heal "Ser Aldric" 8
bash modules/mass-combat/tools/dm-mass-combat.sh kill Bandit-05
```

### Battle lifecycle

```bash
bash modules/mass-combat/tools/dm-mass-combat.sh status
bash modules/mass-combat/tools/dm-mass-combat.sh next-round
bash modules/mass-combat/tools/dm-mass-combat.sh end
```

## Tactical Rules

- Cover applies `+2 AC` to every unit in the group.
- `move --to` changes a unit's tactical group or zone.
- `--count`, `--type`, and `--exclude` limit which units act.
- Melee units must be moved into the target zone before attacking.
- Turrets marked as crewed cannot fire without a living crew member.
- AOE attacks roll damage once, then resolve saves and provider damage for each
  target.
- Direct `damage`, `heal`, and `kill` commands are state corrections or explicit
  effects; do not use them to duplicate resolved attack damage.

## Output Discipline

Narrate exactly the units that acted, their hit or miss results, HP changes,
deaths, cover, and movement. Do not collapse independent rolls into a fictional
squad total, and do not repeat a successful attack through another command.
