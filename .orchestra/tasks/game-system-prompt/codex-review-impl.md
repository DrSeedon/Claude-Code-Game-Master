The campaign-scoped prompt path breaks common campaigns created by the existing wizard/API schema, either crashing on `narrator_style` or dropping all compiled rules when `modules` is a list. The new WebSocket validation also rejects names that the creation API still allows.

Full review comments:

- [P1] Handle string narrator_style before reading fields — /mnt/data/Projects/Python/orchestra/worktrees/mnt-data-projects-python-claude-code-game-master/vanilla-frontend/backend/claude_dm.py:67-69
  When a campaign is created through the wizard/API with a narrator choice, `campaign_api.create_campaign()` stores `narrator_style` as a string ID, not the object shape assumed here. Because `/ws/game` now calls `load_system_prompt(campaign)` for the selected campaign, opening that campaign raises `AttributeError: 'str' object has no attribute 'get'` at this line after the socket is accepted, so the new “Начать играть” path cannot start the game for those campaigns.

- [P1] Support modules arrays when compiling campaign rules — /mnt/data/Projects/Python/orchestra/worktrees/mnt-data-projects-python-claude-code-game-master/vanilla-frontend/.claude/additional/infrastructure/dm-active-modules-rules.sh:31-38
  Campaigns created by `create_campaign()` always write `modules` as a list, often `[]`, but after this change the compiler now loads the selected campaign overview and the code immediately below still does `mods.items()`. For any such campaign, the subprocess exits with `AttributeError`, `load_system_prompt()` catches it as empty `dm_rules`, and the prompt regresses to narrator-only instead of including the core DnD slots.

- [P2] Accept campaign names that creation permits — /mnt/data/Projects/Python/orchestra/worktrees/mnt-data-projects-python-claude-code-game-master/vanilla-frontend/backend/server.py:76-80
  The campaign creation API only rejects `/\\:*?"<>|`, so existing/API-created campaigns can legally contain spaces, dots, Unicode, or longer names; the frontend sends those exact names from `/api/campaigns` as `?campaign=`. This stricter ASCII/64-character regex makes those campaigns connect only to an error frame and close, so they become unplayable unless creation is constrained to the same format or this accepts the same safe names.
---

## Resolution (all 3 fixed + regression-tested)

- **[P1] string narrator_style** — `claude_dm.py` now handles both: a string id loads
  `narrator-styles/<id>.md`; a dict uses the embedded object. Verified: a real API campaign
  (`narrator_style="epic-heroic"`) → 74452-char prompt, no crash.
- **[P1] modules list** — the compiler normalizes `modules`: list → enabled ids, dict → truthy
  keys. Verified: `modules=["world-travel"]` → rules include the module (74452 > 66479 core-only),
  no AttributeError.
- **[P2] campaign name regex** — replaced the strict `^[A-Za-z0-9_-]{1,64}$` with the creation
  API's rule: reject only `/\:*?"<>|` + traversal (`..`, leading dot). Verified: spaces / Unicode /
  dots / long names accepted; `../evil`, `a/b`, `..`, `.hidden` blocked.

Regression tests added in `tests/test_claude_dm.py` (wizard-shape campaign, name validation).
192 backend tests pass.
