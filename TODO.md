# TODO — DM System

## Screen audio (`audio.py`) & speech highlight (`template.html`): stuck tavern rain ambience on missing replacement cue, low library recall without explicit tags, and `.speaking` highlight jumping ahead (found 2026-11-06)
- **Where:** `lib/screen/audio.py::Director.resolve` (lines 287–299), `lib/screen/audio.py::Library.find` (lines 109–121), `lib/screen/server.py` (line 226), and `lib/screen/template.html` (`speak`, `swapAct`, `renderFeed`).
- **What broke & triggering case:**
  1. In `pratchett-dungeon` on `https://dnd-play.seedon.ru/`, turn 9 started looping `b7596f8bfd08fa5aaa1e0b38.mp3` (`"steady heavy rain drumming on a wooden tavern roof"`). When later turns moved to the midday swamp, dungeon, and university courtyard (`"swamp frogs and dripping mist at midday"`, `"quiet evening courtyard crickets"`), those cues failed to resolve (`DM_SCREEN_SOUND_GENERATION=0` and only 4 ambience entries in `world-state/audio-library`), and `Director.resolve` left `out["ambience"] = "keep"`, keeping the tavern rain loop playing forever across acts and outdoor scenes.
  2. `Library.find` weighted `tags` by `3x` and `cue` words by `1x` (`best_score >= 3`), so cues where the master omitted `tags` (or wrote words in `cue` that matched library tags) scored `< 3` and returned `None`.
  3. In `template.html::speak()`, `highlight(seg.blocks)` ran before `a.play()` started (while the MP3 was still loading) and highlighted all merged `<p>` blocks of a multi-paragraph narration segment at `t=0`, making the `.speaking` outline jump ahead of the voice.
  4. `server.py` hid `#autoBtn` whenever `DM_SCREEN_DAILY_CREDITS` or `DM_SCREEN_TURN_CREDITS` was set, hiding the Auto-TTS toggle on `https://dnd-play.seedon.ru/`.
- **Fix direction:** Stop stale `ambience` (`out["ambience"] = None`) when a replacement `ambience` cue is missing (and on act swap), match `cue` words against library tags (`tags | wanted`) in `Library.find`, seed `world-state/audio-library` with core fantasy ambience/SFX tracks and enable `DM_SCREEN_SOUND_GENERATION=1` on `play`, step `.speaking` block highlights on `a.onplay` / `a.ontimeupdate` proportional to block character length, and keep `#autoBtn` visible unless `DM_SCREEN_AUTO_SPEECH=0`.

## Screen live feed (`hook.py`): `💾` save events lack concrete details (`Состояние героя изменилось`) (found 2026-11-06)
- **Where:** `lib/screen/hook.py::describe` (lines 73–103).
- **What broke & triggering case:** During `pratchett-dungeon` on `https://dnd-play.seedon.ru/`, `dm-player.sh condition 'Стив Хуйс' add Poisoned` and `remove Poisoned` both emitted generic `💾 Состояние героя изменилось` in `activity.jsonl` without naming what condition was applied or removed, and HP/gold/XP/inventory changes emitted generic strings without deltas or item names.
- **Fix direction:** Include concrete player-facing details in `save` (`💾`) feed events (condition added/removed with Russian labels for standard conditions, HP/max-HP delta, companion HP transition, XP delta, gold/currency delta, inventory items/gold/XP/HP changes) while keeping `world` events for new NPCs and hidden machinery (`dm-consequence`, `dm-note`, `dm-world`, `dm-npc locate`) spoiler-free, and skipping read-only `condition list`/`check` or failed `Usage:` invocations.

## Screen speech: Russian closing punctuation after `»` drops character voice and merges line into narrator (found 2026-11-06)
- **Where:** `lib/screen/speech.py::script_from_blocks` (`_QUOTED`, line 46) and `lib/screen/content.py::check_verbatim`.
- **What broke & triggering case:** In turn 9 of `pratchett-dungeon`, the master wrote standard Russian punctuation with the period outside the closing guillemet: `<p><b>Трактирщик:</b> «Комнаты наверху стоят денег. Деньги у вас закончились. Но на лавке у печки бесплатно, если не храпеть».</p>`. Because `_QUOTED = re.compile(r"^[«\"“](?P<line>.+)[»\"”]$", re.S)` requires the closing quote to be the very last character, `_QUOTED.match(rest)` returned `None`, causing `script_from_blocks` to treat the dialogue paragraph as narration (`speaker: "narrator"`) and read `"Трактирщик: «...»."` in the narrator's voice (`Sergey`) instead of the male NPC voice (`Nikolay`).
- **Fix direction:** Allow trailing sentence punctuation (`[.!?…]*`) after the closing quote in `_QUOTED` (preserving that punctuation at the end of the extracted line) so `<p><b>Name:</b> «...».</p>` is extracted as a character segment for `Name`.
- **Resolved (2026-11-06):** Updated `_QUOTED` and `script_from_blocks` in `lib/screen/speech.py` and added regression coverage in `tests/test_screen_speech.py` (`126 passed` in `test_screen_speech.py` + `test_screen_content.py`). Deployed to VPS and restarted `play`/`demo` screen servers.

## AI-table V87 cleanup: final Git status exits 128 (found 2026-11-04)
After all three clean, merged temporary worktrees were removed by `git worktree remove`
and RC build dependencies were moved to main/node_modules, the cleanup runner's final
`git -C /home/kesha/projects/ai-table-mvp status --porcelain` exited 128. Inspect the
actual Git stderr and node_modules metadata before changing anything else. Production
V87 and all 12 public authenticated socket checks already passed; runtime is unaffected.
Resolved: the preparation runner's root `git status` refreshed `.git/index` as root:root
0600 (mtime 2026-11-04 18:32:56 VPS time). Changed ownership of that one file back to
kesha:kesha; main status is clean and HEAD/origin/main remain b590f4e4. Updated the release
runner to execute every Git operation as kesha, including archive/show/status. No source
content or production state changed. All three worktrees were already successfully removed.

## AI-table socket closes between projection ACK and GM snapshot (found 2026-11-04)
`server/ai_table/adapters/ws.py::ProjectionBroker.handle`, line 315 on V85: a client
disconnecting immediately after its initial projection ACK can cause the subsequent
`socket.send_json(self.gm.snapshot(surface))` to raise `RuntimeError: Cannot call "send"
once a close message has been sent`. Triggered by the short-lived authenticated release
probe on the public mirror; gameplay counters were unchanged. Fix direction: treat close
during the initial side snapshots as normal disconnect, preserving final cleanup. The
probe should also wait for the initial side snapshot/heartbeat before disconnecting.
Fixed on `v86-ws-close`, commit `c26efe667d624d052fa5f87e3d61ad751c23cfc6`:
the close-after-ACK regression goes from 1 failed / 2 passed to 3 passed; combined real
HTTP/WS admission/reveal/gift regressions total 8 passed in 16.40 s. Unrelated RuntimeError
still propagates, cleanup is checked. Fresh provenance gate ADMITTED. Branch pushed for
CEO acceptance; production remains accepted V85. Evidence: `build/ai-table-live-gm/v85-release/V86.md`.

## AI-table V85 external socket probe timed out (found 2026-11-04; independently cleared)
After a successful local production swap (four authenticated sockets, 94 assets, unchanged
game counters), the first public-name WebSocket probe timed out at the handshake. HTTP
login had succeeded. Identify the host and compare the direct path with websocket-client
proxy auto-discovery before changing nginx; production stays healthy locally. The public
GM login page independently loads from the hub browser with its art/fonts and no errors.
Resolution: primary mirror and sslip twin passed all four authenticated sockets; an
independent stdlib TLS/RFC6455 client passed all four DuckDNS sockets with projection ACK,
revision 63 and graceful close. No nginx change was needed. The original sync-client
timeout remains a recorded verifier limitation, not a demonstrated production failure.

## AI-table V85 rollout: human GM admission is not configured (found 2026-11-04)
`server/ai_table/adapters/gm_console.py::register_gm_console` deliberately serves `/gm` as 404
without `I1_GM_PASSWORD_FILE`. The live V51 unit has no such setting and `/etc/ai-table-i1/`
has only the player passphrase, speech key and AI bearer. V85 is accepted and fast-forwarded
to `main`/`origin/main` (`509d0049`); production is still `a91e940` until rollout rehearsal.
Resolved with CEO's explicit provisioning decision on 2026-11-04: independent prod and
staging GM passphrases configured, and a protected owner copy provided by SSH. Production
now serves `509d0049`; all four surfaces on all three public names passed authenticated
socket checks. No secret value is stored here. Evidence: `build/ai-table-live-gm/v85-release/`.

## AI-table V85 release runner: staging backup sidecars block SQLite open (found 2026-11-04)
The first old-build rehearsal stopped before any production swap: staging startup failed
at `SqliteRoomRunRepository._connect`, `PRAGMA journal_mode=WAL`, with `unable to open
database file`. Inspect the freshly copied DB and WAL/SHM ownership plus parent permissions;
normalize the staging copy for `aitable-stg` before resuming. Root cause: sqlite3 connection
context managers commit/rollback but do not close the connection; the root read-only guard
held WAL/SHM files open until process exit. Fixed runner with `contextlib.closing` for every
connection, preserving the same staging DB and resuming at the old-build start. The runner's
exit cleanup stopped both staging units. Production remained V51 and was unaffected.

## AI-table hub master: residual risks before and after its deploy (found 2026-11-02, AI-table V-51)
`ops/ai-table/` (Severin's T3 thread): the first spoken line's delay is not measured (estimate 10–25 s, the VPS CLI
master did about 2 s): measure `first_caption_s` on staging, N≥10, before prod. The webhook URL stays in the VPS GM's
memory (Yama `ptrace_scope=1` blocks non-descendants; no AppArmor profile for the GM: the owner's call). If the hub's
Claude account hits limits (as the dnd-play threads did on 2026-10-31), Severin is silent until the thread moves to
another model; whether that move may be automatic is the owner's call. The staging key line (`hub-gate staging`) must
be removed from `authorized_keys` after the rehearsal.

## The VPS Claude subscription stopped working: SDK masters and the web game master fail (found 2026-10-31)
From 2026-10-31 13:31 UTC every `/usr/bin/claude` session on the VPS answers «Claude Code can't use your Claude
subscription, usually because a payment is past due». The demo table's SDK master (`backend/screen_driver.py`
`sdk_turn`) failed all 11 batches (#8-18) in about a second each, and its follow-up failed too, so the feed filled with
«Мастер споткнулся». Everything else on the VPS that thinks through that CLI is affected as well: the web game master
(`backend/providers/claude_sdk.py`) and, outside this repository, Orchestra and the AI-table. Done here: both online
tables moved to hub masters on Sonnet 5.5 with `DM_PLAY_HUB_FALLBACK=none` (owner decision 2026-10-31). Open: the
subscription itself is the owner's; the web game master stays down until it works again or gets another runtime.

## The play screen has no phone layout (found 2026-10-28, master console screenshots)
`lib/screen/template.html`: at 390x844 the page keeps its desktop grid (`main` two columns, the footer's option and input
rows in one line), so the side panel, the second option, the send button and the header's place and date are cut off
past the right edge (`.playtest/console-phone-closed.png`). The master console itself opens as a full-screen drawer and
its button is fixed top right, so it is usable. Fix direction: a `@media (max-width:760px),(orientation:portrait)` layout:
one column (story, then a collapsible side panel), options wrapping under the question, the input row wrapping.

## Hub master webhook URL is readable inside the play unit (found 2026-10-28, hub master build)
`backend/hub_master.py`: the driver popped `DM_PLAY_HUB_WEBHOOK` from `os.environ` at start, but systemd passed it in the
exec environment, so `/proc/<driver pid>/environ` still held it; the SDK master runs as the same user in the same unit,
and the demo table's master shared the AppArmor label (ptrace read allowed between the two tables). A master talked out
of its contract (at demo: by a guest) could read the URL and post forged events to the hub master's T3 thread (prompt
injection into an agent with the hub's access; the gate still refuses calls without the current ticket). Fixed
2026-10-28 in part: `scrub_exec_environ` overwrites the value in the exec environment block, and each table has its own
AppArmor profile (`dnd-play-master-%i`). Left: the URL stays in the driver's memory (ptrace attach, refused by Yama
ptrace_scope 1 for a non-descendant; check the VPS setting), and repository tools the SDK masters can edit produce the
output the hub master reads. Fix direction: a root-owned relay that adds the URL, or a pull model where the hub asks the
gate for the next event, or a T3 webhook signature; `ops/play/hub-master.md` must treat every event and tool output as
player data.

## Secret guard flags the e2e test password constants (found 2026-10-28)
`tests/test_secret_guard.py::test_common_secret_patterns_are_not_tracked` fails on `tests/e2e/e2e_support.py:11`
(the fixture's password constant and its literal value) and `tests/e2e/test_screen_browser.py:58` (the f-string that
passes that constant): the ASSIGNMENT pattern takes them for literals. Fixed 2026-10-28: the fixture value starts with
`test-` (PLACEHOLDER) and the login body is built by concatenation.

## `dm-campaign-custom-rules.sh` calls `uv` directly (found 2026-10-27, War and Peace moved online)
`.claude/additional/infrastructure/dm-campaign-custom-rules.sh` (line ~106 and ~176) runs `uv run python` itself instead
of `tools/common.sh`'s `$PYTHON_CMD`. In a plain ssh shell on the VPS `uv` is not on PATH: `remove html-screen` printed
success and `apply` failed with "uv: command not found", leaving the campaign without its html-screen rule until rerun
with `~/.local/bin` on PATH; and that `uv run` (no UV_FROZEN) rewrote the tracked `uv.lock` (restored with git checkout).
Fix direction: source `tools/common.sh` and use `$PYTHON_CMD`; make `remove`+`apply` fail together.

## Online master skips the act change on a move (found 2026-10-27, demo table playtest)
Two moves of the party to new lasting places (the University library, then a swamp camp) got `dm-scene.sh` and a turn
but no new act and no picture: the screen kept the tavern header and art while the story moved on. The contract made
it a judgement call. Fixed 2026-10-27: the contract says a move to a new lasting place is a new act, and the screen's
PostToolUse hook (`lib/screen/hook.py` `act_nudge`) tells the master, right after `dm-scene.sh` or `dm-session.sh move`,
which place the act still shows and how to start a new one with art. Verify on the next playtest.

## Online master escapes its sandbox through /proc/<pid>/root (found 2026-10-27, art service review)
`dnd-play` runs the master as `kesha` with `~/.ssh` hidden (TemporaryFileSystem) and the home read-only, but any other
`kesha` process (Orchestra, the hub tunnel, the Kesha bot) is visible in `/proc`, and `/proc/<pid>/root` of a process
outside the unit is the host's filesystem: from inside the unit's mount namespace as uid 1001,
`/proc/<orchestra pid>/root/home/kesha/.ssh/` lists all 20 files and `.../orchestra/data/secrets/` its 6 entries
(verified 2026-10-27). Yama `ptrace_scope=1` only limits attach; `ProtectProc=invisible` hides other users, not the same
uid; `PrivatePIDs` needs systemd 257 (the VPS has 255). So a guest who talks the master into it reaches kesha's keys
(GitHub, the laptop tunnel, the MultiCode hub) and every secret kesha can read. Fix in progress 2026-10-27: an AppArmor
profile for the unit with no ptrace or signal rights over other profiles (blocks `/proc/<pid>/root`, environ, kill),
plus a home allowlist (TemporaryFileSystem over `/home/kesha`, bind only what the master needs) and InaccessiblePaths
for `/opt/kesha-bot` and `/opt/cog-second-brain`. Done in the code 2026-10-27 (`ops/play/apparmor-dnd-play-master`,
`dnd-play@.service`: `ProtectHome=tmpfs` with an allowlist, `InaccessiblePaths=-/opt`, the master's own cache dir);
probed on the VPS in a transient unit: `/proc/<orchestra pid>/root`, `environ` and `kill` are denied, claude, git push,
uv and the venv work. Left: `~/.claude` (other agents' transcripts) stays readable, because the CLI needs it; the shared
`~/.cache/uv` was writable by the master from 2026-10-26 to the move to `dnd-play@` (checked 2026-10-27: no entry that
existed before the master started was modified; `uv cache clean` would remove any doubt, the owner's call because
Orchestra shares that cache).

## Live keys leaked in a tracked `.env.bak` (found 2026-10-27 by GitGuardian)
The Codex DM hooks commit (now `fb997a4`, pushed to public `main` 2026-10-25) carried `.env.bak` with
`DEEPGRAM_API_KEY` (the live key, same value as the laptop and VPS `.env`) and an older `ELEVENLABS_API_KEY` (not the
current one). `.gitignore` covered `.env` and `.env.*.local`, not `.env.bak`; the secret guard that would have failed
on it was already crashing (last paragraph), and the 7 known failures hid it. Done 2026-10-27: on the owner's order
(«срочно историю ита перезатри чтобы ключи не были в паблике») `main` was rewritten from that commit on without
`.env.bak` and force-pushed; the old commit's SHA is kept out of the repository text because GitHub serves an orphaned
commit by SHA until GitHub Support purges it. `.env.*` is ignored except `.env.example`; the guard skips symlinks and
runs again; code expressions such as `password = parse_qs(...)` no longer count as literals. Still open: the keys were
public for two days, so the owner revokes the Deepgram key and that ElevenLabs key and issues new ones (then laptop
`.env` → VPS `.env`), and asks GitHub Support to purge the orphaned commit and cached views.
This repository is a fork of `Sstobo/Claude-Code-Game-Master` (a network of 33): checked after the force push, the old
commits still serve `.env.bak` by SHA through this repository and through the upstream's URLs alike (the public push
events list the SHA). Forks share one object store, so deleting and recreating this fork would not remove them; only
the GitHub Support "remove sensitive data" request does (all eight pre-rewrite SHAs from the Codex DM hooks commit up
to the untrack commit).
The guard crash itself (found 2026-10-25, fixed 2026-10-27): `value_findings` and `pattern_findings` read every tracked
path, and `.agents/skills/*` are tracked symlinks to directories, so both tests died with `IsADirectoryError`.

## Wizard MCP tests fail on the laptop's `mcp` 2.x (found 2026-10-25)
Five `tests/test_wizard.py::TestWizardMCPTools` tests fail on the owner's laptop checkout: the installed `mcp` package is
2.x (`ModuleNotFoundError: No module named 'mcp.server.fastmcp'`, `'Server' object has no attribute 'request_handlers'`).
The wizard code targets the 1.x API. Fix direction: pin `mcp<2` in `pyproject.toml` (and refresh `uv.lock`), or port the
wizard tools to `mcp.server.mcpserver.MCPServer` per the mcp v2 migration guide.
**2026-10-26: now live on the VPS.** `uv.lock` pins `mcp` 2.3.0 since `fb997a4` (the Codex DM hooks commit); the VPS `uv sync --frozen` installed it and
`dnd-game-master` was restarted, so the Codex wizard (`backend/server.py` → `python -m backend.wizard_mcp_stdio`, which imports
`mcp.server.fastmcp`) fails on the server. The Claude wizard (in-process SDK MCP) and play are unaffected.

## `dm-time.sh --elapsed` on a campaign without `precise_time` jumps to morning (found 2026-10-25)
pratchett-dungeon had `time_of_day: "Вечер"` and no `precise_time`. `dm-time.sh "_" "<date>" --elapsed 0.25` started the
clock at 08:00 and wrote `08:15` into both fields, so an evening tavern scene became morning. Fix direction: when
`precise_time` is missing, derive the start from a named `time_of_day` (Morning/Вечер/Night → a default hour) or refuse
with "set the time first with --to HH:MM"; never overwrite a named time of day with the 08:00 default.

## Generated files tracked in git break `git pull --ff-only` on the VPS (found 2026-08-03)
Deploy on the VPS is `git pull --ff-only`, and it aborts on a dirty tree. Two tracked files are
rewritten by simply RUNNING the project, so the tree is never clean for long:
- `uv.lock` — every `uv run` (including the service's own `ExecStart`, so every `systemctl restart`)
  rewrites it: VPS uv 0.11.28 logs `Resolving despite existing lockfile due to removal of global
  exclude newer` and drops the `[options] exclude-newer` block plus all `sys_platform` markers.
- `modules/registry.json` — even the read-only `dm-module.sh list` reorders and rewrites it.

Fix direction: stop tracking `modules/registry.json` (regenerate it on demand), and pin/align the
uv version — or accept the lock churn and commit it once from the VPS. Until then a deploy can die
mid-way with "Your local changes would be overwritten".

## Unified Inventory Storage (Refactor)
Move inventory data INTO entity files instead of separate module-data JSONs:
- Player inventory → `character.json` (instead of `module-data/inventory-system.json`)
- NPC party inventory → `npcs.json` per-NPC (instead of `module-data/inventory-party.json`)
- Pros: everything in one place, `dm-npc.sh status` shows inventory inline
- Cons: breaks module isolation, but upstream is dead so lib/ is ours

## Graph System — long-term
Evolve wiki.json into a full entity graph replacing npcs.json + locations.json + facts.json + wiki.json. All entities as nodes with typed edges (sells, knows, located_at, component_of, etc). Do AFTER wiki.json is battle-tested in multiple campaigns.

## Auto-DC-Mod from Inventory (deferred)
- `--skill "alchemy"` should check if items granting dc_mod are in inventory (via wiki)
- If item not in inventory → dc_mod doesn't apply
- Currently dc_mod is hardcoded in character.json skills — should be dynamic
- Do when we actually lose an item with a bonus

## CORE Encounter System on Move
Configurable encounter engine triggered by `dm-session.sh move --elapsed N`. Settings per campaign in `campaign-overview.json`:
- `encounter_chance`: base % per hour of travel (e.g. 15 = 15% per hour)
- `encounter_types`: weighted table of categories (bandits: 30, beasts: 25, undead: 20, merchants: 15, patrol: 10)
- `encounter_frequency`: min hours between encounters (e.g. 2 = max 1 encounter per 2 hours)
- `encounters_enabled`: true/false toggle
- On trigger: roll category from weighted table, create creature from wiki (if exists) or print type for DM to narrate
- Auto-lookup creature stats from wiki for instant combat setup
- Works with any campaign/setting — zombie hordes, monster hunters, road bandits

## Import without RAG is broken end to end (found 2026-10-25, War and Peace import)
Importing a book needs `sentence-transformers` + `chromadb` (several GB with torch) even though extractor agents only read chunk files:
- `tools/dm-extract.sh prepare` aborts without RAG; `lib/agent_extractor.py` `prepare_for_agents` exits too. Chunking could be a plain paragraph split.
- `.claude/agents/extractor-*.md` tell agents to use `dm-search.sh --rag-only` and carry `model: opus` (expensive). Worked around with custom Haiku prompts, one agent per ~145k-char package writing `extracted/agent-NN.json`.
- `lib/rag/__init__.py` does not export `QuoteExtractor`, so the quote step of `save` fails with `cannot import name 'QuoteExtractor'`.
- `lib/rag/embedder.py` defaults to `all-MiniLM-L6-v2`, English only: useless for Russian books. Use a multilingual model (multilingual-e5-small needs `query: `/`passage: ` prefixes).

## Import drops factions (found 2026-10-25)
`AgentExtractor.validate_and_save` saves only npcs, locations, items, plots; `factions`, `monsters`, `traps` from `merge_agent_results` are silently dropped. War and Peace factions were kept in `world-state/campaigns/war-and-peace/merged-clean.json`.

## No dedupe of the same entity across extraction packages (found 2026-10-25)
Per-package extraction produced 419 NPC keys for ~139 real characters («Пьер Безухов» x19, «Фёдор/Федор Долохов», «Бенигсен/Беннигсен»). Needed a hand-made alias map; the importer has no normalisation step.

## Two-player (couple) play is not supported natively (found 2026-10-25)
One `player:active` node plus DM-controlled party NPCs (`dm-npc.sh promote`). Second human player has to be played as a party NPC with a campaign rule that the DM never decides for them.

## Campaign rules template can never apply to a freshly created campaign (found 2026-10-25)
`dm-campaign-rules.sh apply <id>` prints `[SKIP] campaign-rules.md already exists` and only writes the metadata to `campaign-overview.json`, but `CampaignManager.init_campaign_files` (also used by import `prepare`) already creates a placeholder `campaign-rules.md`. Result: "Template set to: political-intrigue" while the file holds no template rules. Same for `dm-campaign-custom-rules.sh apply`: "already applied" is tracked in the overview, so re-applying after the file was recreated is skipped. Fix: skip only when the file contains template content, and derive "applied" from the markers in the file, not from the overview.

## Calendar has no leap years (found 2026-10-25)
`lib/calendar.py` `days_in_year` sums fixed month lengths and `_absolute_day` multiplies `year * days_in_year`, so February is always 28 days. War and Peace runs 1805-1813 on the Julian calendar (1808 and 1812 are leap years), so dates and weekdays drift by one day after each 29 February. Fix direction: optional `leap_rule` in the calendar config (every N years, which month gets the extra day).

## Imported quests crash `dm-plot.sh list` and spam the active list (found 2026-10-25)
`AgentExtractor.validate_and_save` stores extracted `plot_hooks` as `quest:*` nodes with `objectives` as plain strings and no `status`. `world_graph.py` `quest-list` (line ~2751, `o.get("done")`) assumes objective dicts `{text, done}` and raises `AttributeError: 'str' object has no attribute 'get'`. Also 201 book beats became 201 active quests, drowning the real ones. Fix direction: importer must write objectives as `{"text","done"}`, set `status`, and put non-quest scene/theme beats into `chapter`/`fact` nodes instead of quests; make `quest-list` tolerate legacy string objectives.

## Image MCP (`mcp__websearch__generate_image`) fails on every prompt (found 2026-10-25)
Workaround that works: Codex imagegen, see ~/.claude/docs/image-generation-codex.md. Three calls in a row (two cinematic prompts and a trivial "red apple" 1:1) returned `Provider returned error` for `google/gemini-nano-banana-2.1` (OpenRouter shows the model and its single provider, Google AI Studio, as listed and up). `~/.claude/mcp-servers/websearch/index.js` sends `modalities: ['image']` plus `image_config.aspect_ratio`; Gemini image models normally require `['image','text']`. Hypothesis, not yet verified. Fix direction: change the modalities array in `index.js` (global file, owner approval needed) and reconnect the MCP; otherwise retry later. The campaign needs this for cinematic scene art (`cinematic_visuals` is enabled).

## HTML play screen follow-ups (found 2026-10-25)
- [ ] **Declare Pillow** — `lib/screen/theme.py` imports PIL, which is only present transitively; add it to `pyproject.toml` dependencies together with a deliberate `uv.lock` update (see the lockfile churn note above).
- [ ] **Web-app integration** — the screen runs next to Claude Code (actions reach the Master through `dm-screen.sh listen`). A standalone mode for the FastAPI game master (`backend/game_session.py`) should read the same `inbox.jsonl` and write `turn.json`; not done.
- [ ] **Mic tuning** — VoiceType self-tunes the system microphone volume (clipping/too quiet); the screen only cleans audio with ffmpeg and relies on VoiceType's tuning of the shared source.
- [ ] **Window on top** — the app window opens through Chrome `--app`; whether KDE raises it above other windows was not verified from the sandbox.

## Full test suite has 7 failures unrelated to the screen (found 2026-10-25)
- `tests/test_wizard.py::TestWizardMCPTools` (5 tests): `mcp` is 2.x in `.venv`, where `mcp.server.fastmcp` no longer exists (`FastMCP` became `MCPServer`). Fix direction: pin `mcp<2` or migrate `backend/wizard_mcp*.py`. Fails on a clean `HEAD` checkout as well.
- `tests/test_secret_guard.py` (2 tests): fixed 2026-10-27, see the `.env.bak` leak entry at the top.

## `dm-inventory.sh update "<name>"` can match a fact node instead of the hero (found 2026-10-25)
The fuzzy name lookup resolved `Максим Астраханцев` to `fact:npc-001` (a `dm-note` fact whose text starts with the heroes' names): `--gold 9500` was written into that fact's `data.money` and the player's purse stayed unchanged. Fix direction: resolve only `player:*` and `npc:*` nodes in `lib/inventory_manager.py` and fail loudly on any other type; until then use `dm-player.sh gold` for the player. Triggered case: War and Peace, payment for the first order.

## `/dm-save` skill calls actions that do not exist (found 2026-10-25)
`.claude/commands/dm-save.md` (and its Codex copy) runs `bash tools/dm-plot.sh threads`, which fails with `Unknown action 'threads'`. Also the orphan check compares the player's location name with location node ids, so it can report false issues. Fix direction: replace with `dm-plot.sh list --status active` and compare names or ids consistently.

## Screen voices: follow-ups (found 2026-10-25)
- [ ] **Ambient sound** — per-act looping background (wind, fire, salon murmur) through the ElevenLabs sound-effects API (`/v1/sound-generation`, `loop: true`), cached per act and cross-faded when the act changes. Credit cost per generation was not measured yet; the TTS audio effects catalog only has modern noises (cafe, city, keyboard, call center).
- [ ] **Voice slots** — the Free plan has 3 custom voice slots (all used by Nikolay, Victoria and "Slavic Man"); only two native Russian voices exist there. More distinct characters need Starter or higher, or premade voices that speak Russian with an accent. Compare samples before choosing.
- [ ] **Word highlight** — Forced Alignment would allow karaoke-style highlighting; paragraphs are highlighted now.
- [ ] **Eleven v4** — the Russian-verified list of the professional voices does not name v4; try it on a short sample before using it for the narrator.

## Screen and web GM defects found while planning online play (found 2026-10-26)
- [ ] **`wait` skips actions posted mid-turn** — `lib/screen/cli.py::wait_for_action` starts from `max(cursor, turn.answered)`, while `set_turn` stamps `answered` with the newest inbox id at publish time (`cli.py:79`), so an action sent while the Master is writing the turn is never delivered. Fix: `wait` follows only its own cursor; `set_turn` takes the delivered id explicitly.
- [ ] **HTML denylist can be bypassed** — `lib/screen/content.py` `_DANGEROUS` lets `<img/src=x/onerror=...>`, `<svg/onload=...>` and entity-encoded `jav&#x61;script:` through; caption `dot` is interpolated into an attribute unescaped (`template.html:156`). Fix: an allowlist sanitizer (no attributes) and numeric validation of `dot`.
- [ ] **Speech render is not single-flight** — two pages (or two clicks) rendering the same turn at once both pay ElevenLabs (`lib/screen/server.py::_render`, `speech.py` cache checked before synthesis). Fix: a lock around render so the second waits and hits the cache.
- [ ] **Negative or non-numeric `Content-Length` blocks the request thread** — `lib/screen/server.py::_post` reads `int(Content-Length)` unchecked. Fix: 400.
- [ ] **SDK resume sends an empty system prompt** — `backend/providers/claude_sdk.py` passes `system_prompt=""` on resume, which the SDK turns into `--system-prompt ""`; after the 5-minute hibernation the web GM continues without the DM rules. Fix: always pass the prompt (as a file when large).
- [ ] **Narrator style without a file falls back to epic-heroic** — `backend/claude_dm.py` (`narrator_style: pratchett` has no `narrator-styles/pratchett.md`); use the campaign rules' narrator text before the default.
- [ ] **Prompt hooks ignore `DM_ACTIVE_CAMPAIGN`** — `.claude/additional/infrastructure/dm-hook-common.sh` reads only `world-state/active-campaign.txt`, so a session playing another campaign gets the wrong context on a shared machine.
- [ ] **Online master can read other projects' secrets** — `ops/play/dnd-play.service` keeps `ProtectHome=read-only`, so `/home/kesha/projects/*/.env` and `~/.config/gh` stay readable to the full-access master; only its contract forbids it. Fix direction: `TemporaryFileSystem=/home/kesha/projects:ro` + `BindPaths=` of this checkout, `InaccessiblePaths=-/home/kesha/.config/gh`; test uv, `.venv` and git inside the namespace first.
- [ ] **Live Pratchett turns fail the verbatim check** — `world-state/campaigns/pratchett-dungeon/screen/turn.json`, `media/act-01/turn-02.json`, `turn-audio.json`: speech line 0 does not read block 1 word for word, so a republish is refused and a render voices different words. Fix: republish with a matching `audio.speech` (the online master's opening turn replaces it).
- [ ] **Web rate-limit wait ignores units** — `backend/providers/claude_sdk.py::_rate_limit_info` reads "try again in 5 hours" as 5 seconds. Fix: parse s/m/h like `backend/screen_driver.usage_limit`.
- [ ] **Web stale resume is not recognised** — `backend/providers/claude_sdk.py::_is_stale_resume_error` misses CLI 2.1.3xx "No conversation found with session ID", so the web game retries a dead id 3 times and fails the turn. Fix: add the phrase (the online provider already does).
- [ ] **Web connect failure leaves the CLI running** — `ClaudeSDKProvider._connect` never disconnects a client whose `connect()` failed or timed out. Fix: disconnect in an `except` (the online provider already does).
- [x] **`/favicon.ico` logs a 403 on every page load** — fixed 2026-10-27: the page declares an empty icon (`<link rel="icon" href="data:,">`), so browsers no longer ask.
- [ ] **Failed online turns are redelivered after a restart** — `backend/screen_driver.py` puts the range `(turn.answered, cursor]` back under the RESTARTED notice, including actions whose turn failed and that players were asked to repeat. Fix if unwanted: record `failed_through` in the status file.
- [ ] **The master console log is writable by the SDK master** — `<screen>/master-log.jsonl` (`lib/screen/masterlog.py`) sits in the campaign tree the sandboxed master can write as the same uid, so a prompt-injected master could append forged or unredacted entries (forged huge ids are already ignored, ticket-refused notes are throttled, 2026-10-28). Fix direction: keep the log in a driver-owned directory not bound into `dnd-play@.service`, served by the screen server from there.
