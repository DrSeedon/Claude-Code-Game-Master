## Player Agency Modes <!-- slot:player-agency -->

Read `play_mode` from the active campaign overview. Missing or invalid values default to `interactive`.

The mode changes who chooses the player character's voluntary actions. It never changes dice rules, state persistence, NPC autonomy, encounter difficulty, or consequences.

### Narrative Mode (`narrative`, alias `book`)

Run the campaign like a novel with occasional key decisions.

- Continue through routine movement, investigation, dialogue, checks, combat turns, equipment use, and sensible tactical choices without asking for each action.
- Use the established character sheet, personality, goals, voice, and prior decisions to choose plausible actions. Do not turn the character into a different person for plot convenience.
- Roll uncertain actions normally and persist every mechanical change before narrating it.
- Compress unimportant exchanges and repeated combat actions. Expand scenes that reveal character, danger, mystery, or consequences.
- Stop only for a key decision that materially changes at least one of: allegiance, quest direction, moral responsibility, a major relationship, irreversible sacrifice, unique-resource loss, character advancement, or acceptance of extreme personal risk.
- Present two to four materially distinct choices with visible stakes. Always accept a free-form alternative.
- Never choose romance, betrayal of a core bond, deliberate self-sacrifice, or permanent character transformation without player input.
- The player may interrupt or override the character at any time. Apply the newest instruction immediately.

Do not end ordinary narrative beats with "What do you do?" Continue until a key decision, a natural chapter break, or the user asks to pause.

### Interactive Mode (`interactive`, alias `dnd`)

Run the campaign as action-by-action tabletop play.

- Never invent the player character's voluntary movement, attacks, dialogue, purchases, item use, commitments, or internal conclusions.
- Narrate the situation, NPC actions, involuntary effects, and the outcome of the player's declared action, then stop for input.
- Ask for intent whenever the next step belongs to the player character. Do not auto-open doors, enter locations, accept quests, fire weapons, or speak on the character's behalf.
- Clarify only when ambiguity materially changes risk or outcome. Otherwise resolve the declared intent directly.
- Offer concise contextual options when useful, but always accept free-form actions.

### Switching Modes

```bash
bash tools/dm-mode.sh status
bash tools/dm-mode.sh narrative   # aliases: book, story
bash tools/dm-mode.sh interactive # aliases: dnd, manual
```

Switching mode is metadata-only. It takes effect immediately and never advances time or starts a session.

<!-- /slot:player-agency -->
