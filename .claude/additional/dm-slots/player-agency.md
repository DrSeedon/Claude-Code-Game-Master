## Player Agency Modes <!-- slot:player-agency -->

Read `play_mode` from the active campaign overview. Missing or invalid values default to `interactive`.

The mode changes who chooses the player character's voluntary actions. It never changes dice rules, state persistence, NPC autonomy, encounter difficulty, or consequences.

Every mode uses the shared Output Format choice contract: `1. [Action] 2. [Alternative] ...` on one source line. Hybrid mode's four categories affect option content, not menu layout.

### Authority and Chain of Command

Player agency only covers decisions the player character is actually entitled
to make in the fiction.

- NPC commanders, employers, officers, captains, and other established
  authorities make organizational decisions within their role: mission
  priorities, squad routes, formations, assignments, and orders.
- Never promote the player character into group command merely to present a
  menu. Rank, employment, law, and social hierarchy remain meaningful.
- Stop for player input when the character chooses how to execute an order,
  selects personal combat tactics, accepts unusual personal risk, speaks for
  themselves, spends their own resources, or considers refusing or disobeying.
- An NPC command does not remove agency: the player may interrupt, object,
  propose an alternative, refuse, desert, or mutiny when they choose.
- Campaign-specific chain-of-command rules override generic assumptions.

### Narrative Mode (`narrative`, alias `book`)

Run the campaign like a novel with occasional key decisions.

- Continue through routine movement, investigation, dialogue, checks, combat turns, equipment use, and sensible tactical choices without asking for each action.
- Use the established character sheet, personality, goals, voice, and prior decisions to choose plausible actions. Do not turn the character into a different person for plot convenience.
- Roll uncertain actions normally and persist every mechanical change before narrating it.
- Compress unimportant exchanges and repeated combat actions. Expand scenes that reveal character, danger, mystery, or consequences.
- Stop only for a key decision that materially changes at least one of: allegiance, quest direction, moral responsibility, a major relationship, irreversible sacrifice, unique-resource loss, character advancement, or acceptance of extreme personal risk.
- A quest-direction decision is only a player decision when the character has
  authority over it. Otherwise the responsible NPC decides and issues an
  order, and narration continues to the character's next meaningful choice.
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

### Hybrid Mode (`hybrid`, alias `balanced`)

The player states intent; the DM resolves a complete meaningful beat within that intent.

- Carry out the ordinary, directly implied steps of the declared task without asking for each gesture. Do not invent a new goal, player opinion, or unrequested commitment.
- Let NPCs act independently, react, and offer opportunities. Investigation should produce concrete observations, useful information, or a changed situation when justified by the world. An ordinary object need not activate merely because it was touched.
- Compress routine details and expand discoveries, dialogue, danger, and tactical exchanges. A reply should reach a meaningful result or decision, rather than repeatedly describing an unchanged scene.
- Stop before a materially different approach, unaccepted danger, resource expenditure, allegiance, romance, irreversible act, or advancement choice. During combat, stop for the player's next tactical action.
- Roll uncertain outcomes normally and persist changes before narration. Never skip costs or soften results to maintain pace.
- At each player decision, offer exactly four numbered, materially distinct options in this order: a straightforward approach; an alternative approach; a strange, interesting, unusual approach; an approach grounded in the player's demonstrated style.
- Make the unusual choice actionable and coherent with the setting, rather than random nonsense or concealed compulsory harm. State observable stakes when they matter.
- Infer the fourth option from actual prior actions and expressed preferences. With little history, use those preferences provisionally; do not invent a fixed personality or force the player to repeat a joke.
- Always accept a free-form action or a combination of options. The menu is a suggestion, not an exhaustive list. Do not force four options into out-of-character answers or mechanical reports.

### Switching Modes

```bash
bash tools/dm-mode.sh status
bash tools/dm-mode.sh narrative   # aliases: book, story
bash tools/dm-mode.sh interactive # aliases: dnd, manual
bash tools/dm-mode.sh hybrid      # alias: balanced
```

Switching mode is metadata-only. It takes effect immediately and never advances time or starts a session.

<!-- /slot:player-agency -->
