# /help - DM Command Reference

Display all available commands and tools.

---

## DISPLAY

```
================================================================
  DM ASSISTANT - Command Reference
================================================================

  CORE GAMEPLAY
  --------------------------------------------------------
  /dm              Play the game (handles everything)
  /dm save         Save current session state
  /dm character    Show character sheet & inventory
  /dm overview     View campaign state summary
  /dm mode         Switch narrative/interactive control
  /dm-mode         Get or set player-agency mode

  CAMPAIGN SETUP
  --------------------------------------------------------
  /new-game           Create a new campaign world
  /import             Import a PDF/document as campaign
  /create-character   Build a new player character
  /enhance            Enrich entities with source material

  UTILITY
  --------------------------------------------------------
  /reset           Clear campaign for fresh start
  /world-check     Validate campaign consistency
  /setup           Run installation (usually auto-detected)
  /help            This help message

================================================================

  CLI TOOLS (bash tools/dm-*.sh)
  --------------------------------------------------------
  dm-session.sh     Session management, save/restore
  dm-player.sh      Player character stats
  dm-npc.sh         Create and update NPCs
  dm-location.sh    Add and connect locations
  dm-consequence.sh Track future events
  dm-search.sh      Search world state
  dm-note.sh        Record world facts
  dm-enhance.sh     Enrich entities with RAG
  dm-overview.sh    Quick world summary
  dm-campaign.sh    Switch between campaigns
  dm-mode.sh        Switch player-agency mode

================================================================

  QUICK START
  --------------------------------------------------------
  New campaign:     /new-game
  Continue playing: /dm
  Import module:    /import

================================================================
```

---

## DETAILED HELP

If user asks for specific command help (e.g., `/help dm`), read and summarize that command file:

```bash
sed -n '1,80p' codex-skills/dm/references/commands/[command].md
```

Provide a brief summary of what the command does and its key options.
