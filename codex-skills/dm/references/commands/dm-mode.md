# /dm-mode - Player Agency Mode

Get or change how much control the DM has over the player character.

## Commands

```bash
bash tools/dm-mode.sh status
bash tools/dm-mode.sh narrative
bash tools/dm-mode.sh interactive
bash tools/dm-mode.sh hybrid
```

Aliases:

- `book`, `story` -> `narrative`
- `dnd`, `manual` -> `interactive`
- `balanced` -> `hybrid`

Natural-language requests such as "switch to book mode" or "use D&D mode" count as explicit mode selections. Run the matching command immediately, report the active mode, and do not start or advance a session.

The compiled `player-agency` slot defines the behavioral contract for all three modes. Do not duplicate or reinterpret it here.
