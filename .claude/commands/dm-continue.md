# /dm-continue - Play the Game

---

## SUBCOMMAND ROUTING

| Subcommand | Action |
|------------|--------|
| (none) | Continue to MANDATORY STARTUP CHECKLIST |
| save | Run `/dm-save` skill |
| character | Jump to CHARACTER DISPLAY |
| overview | Jump to CAMPAIGN OVERVIEW |
| status | Run `bash tools/dm-overview.sh` and display |
| end | Run `/dm-save` skill |

---

## 🔒 MANDATORY STARTUP CHECKLIST

### Hook Context Architecture

The UserPromptSubmit hooks have loaded into your context:
- **Campaign state** (location, time, character, custom stats, module status)
- **Session context** (consequences, active quests, last session summary, session handoff)
- **Rules pointer** — DM rules compiled to `/tmp/dm-rules.md` (NOT in context — must read)

### Step 1: Load Rules + Register Session (TWO tool calls, parallel)
```bash
# Call 1: Read compiled rules (85KB — rules, campaign rules, narrator style)
Read /tmp/dm-rules.md

# Call 2: Register session
bash tools/dm-session.sh start
```

Both calls run in parallel. Do NOT run anything else.

Do NOT run ANY of these — they are ALREADY in hook context:
- ❌ `dm-overview.sh` — already loaded
- ❌ `dm-player.sh show` — already loaded
- ❌ `dm-plot.sh list` — already loaded
- ❌ `dm-consequence.sh check` — already in hook + dm-session.sh start output
- ❌ `dm-npc.sh party` — already loaded
- ❌ `tail session-log.md` / `cat session-log.md` — use handoff or hook context
- ❌ `cat session-handoff.md` — already loaded by hook
- ❌ `cat campaign-overview.json` — already loaded

If you run ANY of the above, you are wasting tokens and ignoring this rule.

### Step 2: Internalize Context (NO TOOL CALLS — JUST READ)
Read the hook output + /tmp/dm-rules.md. The session handoff (if present) is the previous DM's briefing — character nuances, relationship states, player intent. **It overrides assumptions from JSON data.**

### Step 3: Verify Location (TOOL CALL ONLY IF MISMATCH)
Compare the location from `dm-session.sh start` output with the session handoff location.
- **If mismatch**: handoff is truth → `bash tools/dm-session.sh move "[correct location]"`
- **If match or no handoff**: do nothing. Do NOT read session-log.md.

### Step 4: Mental Model (from hook context, NO TOOL CALLS)
- [ ] WHERE is the party?
- [ ] WHEN is it?
- [ ] WHO is present?
- [ ] WHAT consequences are pending?
- [ ] WHY are they here?

**Only after ALL steps → present the scene.**

---

### Using Source Material (DM-Internal)

`[DM Context: ...]` in tool output = for your eyes only. Synthesize into narrative, never paste raw.

---

## GAMEPLAY LOOP

For every player action:

1. **Understand Intent** — what workflow applies?
2. **Execute** — use tools invisibly
3. **Persist** — save ALL state changes BEFORE narrating
4. **Narrate Result**
5. **Enforce Campaign Rules**
6. **Check XP** — after significant scenes
7. **Ask** — "What do you do?"

Repeat.

---

## ENDING SESSION / SAVE SESSION

Run `/dm-save` — it handles everything: save state, consistency check, fix issues, write handoff.

---

## CHARACTER DISPLAY

```bash
bash tools/dm-player.sh show
```

Display full character sheet: stats, HP, AC, saves, skills, features, inventory.

---

## CAMPAIGN OVERVIEW

```bash
bash tools/dm-campaign.sh info
bash tools/dm-consequence.sh check
```

Display: location, time, character, sessions, NPC/location/fact counts, active consequences.
