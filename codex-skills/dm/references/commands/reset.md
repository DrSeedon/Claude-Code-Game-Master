# /reset - Clear Campaign for Fresh Start

Quick command to reset the world state for a new campaign.

---

## STEP 1: CONFIRM INTENT

Display:
```
⚠️  CAMPAIGN RESET
━━━━━━━━━━━━━━━━━━

This will clear ALL world state:
  • NPCs
  • Locations
  • Facts
  • Consequences
  • Session history
  • Player characters

Options:
1. ARCHIVE - Save current world to git branch, then reset (safe)
2. HARD RESET - Delete everything permanently (destructive)
3. CANCEL - Abort reset

What would you like?
```

---

## STEP 2: EXECUTE BASED ON CHOICE

### If ARCHIVE:
```bash
bash tools/dm-reset.sh archive
```

This will:
- Create git branch `archive/[campaign-name]-[timestamp]`
- Commit current world state
- Clear all world-state files
- Return to main branch with empty world

### If HARD RESET:
```bash
bash tools/dm-reset.sh hard
```

This will:
- Delete all world-state content permanently
- No backup created
- Cannot be undone

### If CANCEL:
Display:
```
Reset cancelled. Your world is safe.
```

---

## STEP 3: CONFIRM COMPLETION

After successful reset, display:
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  World Reset Complete

  Ready for /new-game or /dm
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

If archived, also show:
```
  Archived to: archive/[branch-name]

  To restore later:
  git checkout [branch-name] -- world-state/
```

---

## QUICK RESET (No Confirmation)

If user runs `/reset hard` or `/reset archive` directly:
- Skip confirmation
- Execute immediately
- Show completion message
