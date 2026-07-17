# /dm-mode - Player Agency Mode

Get or change how much control the DM has over the player character.

```bash
bash tools/dm-mode.sh status
bash tools/dm-mode.sh narrative
bash tools/dm-mode.sh interactive
```

Aliases: `book` and `story` select narrative mode; `dnd` and `manual` select interactive mode.

Natural-language requests count as explicit mode selections. Changing mode never starts a session or advances game time. Follow the compiled `player-agency` slot during play.
