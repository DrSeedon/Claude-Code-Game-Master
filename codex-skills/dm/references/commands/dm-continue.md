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
| mode [status\|narrative\|interactive] | Run the matching `dm-mode.sh` command without starting a session |
| end | Run `/dm-save` skill |

---

## 🔒 MANDATORY STARTUP CHECKLIST

### Codex context architecture

Codex does not rely on Claude's `UserPromptSubmit` hooks. Run the adapter once:

```bash
bash codex-skills/dm/scripts/prepare_session.sh
```

It compiles `/tmp/dm-rules.md`, registers the session, and prints campaign state, module status, consequences, active quests, recent log context, and the session handoff. Then read `/tmp/dm-rules.md` completely.

Do NOT run any of these again after the adapter has printed them:
- ❌ `dm-overview.sh` — already loaded
- ❌ `dm-player.sh show` — already loaded
- ❌ `dm-plot.sh list` — already loaded
- ❌ `dm-consequence.sh check` — already in adapter output
- ❌ `dm-npc.sh party` — already loaded
- ❌ `tail session-log.md` / `cat session-log.md` — use handoff or hook context
- ❌ `cat session-handoff.md` — already loaded by the adapter
- ❌ `cat campaign-overview.json` — already loaded

If you run ANY of the above, you are wasting tokens and ignoring this rule.

### Step 2: Internalize Context (NO TOOL CALLS — JUST READ)
Read the adapter output plus `/tmp/dm-rules.md`. The session handoff (if present) is the previous DM's briefing — character nuances, relationship states, player intent. **It overrides assumptions from JSON data.**

### Step 3: Verify Location (TOOL CALL ONLY IF MISMATCH)
Compare the location from `dm-session.sh start` output with the session handoff location.
- **If mismatch**: handoff is truth → `bash tools/dm-session.sh move "[correct location]"`
- **If match or no handoff**: do nothing. Do NOT read session-log.md.

### Step 4: Mental Model (from adapter context, NO TOOL CALLS)
- [ ] WHERE is the party?
- [ ] WHEN is it?
- [ ] WHO is present?
- [ ] WHAT consequences are pending?
- [ ] WHY are they here?
- [ ] WHICH player-agency mode is active?

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
