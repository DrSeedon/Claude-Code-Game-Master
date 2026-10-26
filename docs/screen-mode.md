# HTML play screen

Play any campaign in a themed web page instead of terminal text: key art per act, live story and stats, option buttons, a text field, a microphone, a picture view with captions, and a feed of the Master's visible work (thinking, dice, saves). The terminal only carries a one-line reply.

It is optional and per campaign. Everything is local: a small server on `127.0.0.1` and a Chromium app window. The hosted variant is described in "Online table".

## Quick start

```bash
bash tools/dm-screen.sh doctor     # what is missing (browser, ffmpeg, Pillow, microphone key)
bash tools/dm-screen.sh enable     # applies the `html-screen` rule to the active campaign
```

Then play as usual (`/dm`). The Master (the AI) follows the rule in `campaign-rules.md`:

1. For every act it generates key art and runs `dm-screen.sh act ...` (the colors come from the art).
2. It starts `dm-screen.sh start` once and attaches a listener (`dm-screen.sh listen`) so your clicks and voice reach it. An agent without a persistent monitor runs `dm-screen.sh wait` in the background instead: it exits with the next action and is started again after each turn.
3. Every turn it shows the result with `dm-screen.sh turn --file turn.json`.

You can also drive it by hand, see "Commands".

## What you see

| Area | Content |
|---|---|
| Story | The Master's text, in pages (`◀ ▶`, arrow keys). New paragraphs rise in one after another. |
| Heroes | Player and party members from the world: HP bar, abilities, skills. Changed numbers flash, bars glide. |
| Side boxes | Anything campaign-specific the Master sends (`panels`): chips, bars, steps. |
| Master's work | Live feed: thinking, dice (animated), short plain-language notes of what changed ("A new character appears", "A quest objective is done", "Time passes: +6 min"). Filled automatically from `dm-*.sh` calls by a hook. Never shows names, descriptions or arguments, and never shows consequences, notes or world edits, so it cannot spoil anything. |
| Footer | Question, option buttons, who is acting, a text field, a microphone. |
| Picture | Hides the panels and shows the art with captions; captions can be switched on and off. Key `H`. Fullscreen `F`. |

The page updates through a Server-Sent Events stream; nothing reloads. While the Master works the page shows "The Master is thinking" and dims the options.

## Commands

| Command | Purpose |
|---|---|
| `dm-screen.sh doctor` | Check requirements. |
| `dm-screen.sh enable` | Turn the mode on for the active campaign (applies the `html-screen` custom rule). |
| `dm-screen.sh act --image art.png --title "..." [--kicker --place --date --style classic\|severe\|soft --lang en\|ru --captions captions.json --labels labels.json]` | Start a new act: copies the art, derives the theme from it. A flag left out keeps the current act's value; the captions stay only with the same picture. |
| `dm-screen.sh turn --file turn.json` | Show a turn (also `--file -` for stdin). |
| `dm-screen.sh panels --file panels.json` | Replace the side panels of the current turn in place (no new turn, no story animation). |
| `dm-screen.sh activity think\|roll\|save\|world\|info "text"` | Add a line to the live feed by hand. |
| `dm-screen.sh start [--port N] [--no-open] [--new-window] [--replace]` | Run the server (default port 18115) and open the window. Idempotent: if a page is already connected no second window is opened; `--replace` closes the old window first. |
| `dm-screen.sh restart` | Restart the server; open pages reconnect by themselves, a stale window is replaced. |
| `dm-screen.sh stop` / `status` | Stop or inspect the server. |
| `dm-screen.sh listen [--from-start]` | Print player actions as they arrive, one line each. For the Monitor tool. |

Files live in `world-state/campaigns/<campaign>/screen/` (git-ignored): `act.json`, `turn.json`, `art.png`, `inbox.jsonl` (player actions), `activity.jsonl` (feed), `server.json` (pid, port, token).

## File formats

`turn.json`
```json
{
  "blocks": ["<h1>The courtyard</h1>", "<p>Text with <b>emphasis</b>.</p>"],
  "question": "What do you do?",
  "options": ["Knock", "Wait", "Look around"],
  "panels": [
    {"title": "PURSE", "chips": ["120 rubles", "12 bottles"]},
    {"title": "PASSIONS", "bars": [{"label": "love", "value": 14, "max": 20}]},
    {"title": "LADDER", "steps": [{"label": "0 Peddlers", "current": true}, {"label": "1 Sutlers"}]}
  ]
}
```
In panel chips `{money}` is replaced by the hero's live purse. The header shows the live game date and time (from `campaign-overview.json`, with the campaign calendar), the hero cards show live HP and purse, and quests come from the world; only `panels` text is static, so refresh it with `dm-screen.sh panels` when stock or debts change.

`blocks` allow `h1 h2 p b i ul li div`; scripts, styles, frames and event handlers are rejected. `options` are plain text, at most six. Heroes, HP, abilities, skills and quests are read from the world through the player-safe view (`backend/campaign_views.py`), so hidden data never reaches the page.

`captions.json`
```json
{"cards": [{"zone": "tl", "title": "MAXIM", "text": "26, a clerk's son", "dot": [330, 150]}]}
```
Zones: `tl` (top-left row), `tr` (top-right column), `bottom` (bottom row). They never overlap. `dot` is a point on the 1672x941 stage the page scales the art to (for art of another size, scale image pixels to that width); a leader line is drawn from it.

`labels.json` maps skill keys to display names: `{"trade": "Trade"}`.

## One window, many acts

A new `act` never opens another window. The open page fades out, swaps the colors, type, panel shape and key art in place (the art cross-fades), and fades back in. `act` and `turn` also start the server and a window if none exists (`DM_SCREEN_AUTOSTART=0` disables that). Edits to `lib/screen/template.html` reload open pages automatically, but never while you are recording, reading the recognised phrase or typing a line.

## Themes

`act` extracts the dominant colors of the art and derives background, panel, text, muted text and two accents. Every text color is lifted until it passes WCAG contrast on the panel (text 7:1, accents 4.5:1), so any art gives a readable page. `--style` changes the shape and the type: `classic` (rounded, serif), `severe` (sharp, serif), `soft` (very round, sans-serif). A new act gets a new look.

## Narrator and character voices (ElevenLabs)

The 🔊 button reads the current turn aloud; **Auto** reads every new turn by itself; the slider sets the volume. The paragraph being read is highlighted. Narration is read by the campaign narrator; a paragraph written as `<p><b>Name:</b> «the line»</p>` is read by that character's own voice (the `Name` can be a first name or an alias). Dice lines, headings, lists and UI boxes are never read.

Setup (key in the project `.env`: `ELEVENLABS_API_KEY=...`, created by `npx -y @elevenlabs/cli@latest onboard init`):

```bash
dm-screen.sh voices                                        # your account's voices, Russian first
dm-screen.sh voice model eleven_flash_v2_5                 # cheapest model with Russian (0.5 credit per character)
dm-screen.sh voice narrator --voice Nikolay --env hall     # the campaign narrator
dm-screen.sh voice set "Agrafena" --voice Victoria --env small_room --distance 0.2
dm-screen.sh voice default --voice Brian                   # everyone without a profile
dm-screen.sh voice show
dm-screen.sh speak "Test line" [--as "Name"]               # voice one line now (spends credits)
```

Choosing voices: `dm-screen.sh audition "text" --voices A,B,C` reads one line in several voices (or `--voices X --models m1,m2` in several models) and shows them as one turn; press 🔊 and listen. `--speed 0.7..1.2` slows or speeds a voice (not on Eleven v4).

Your own voices: `dm-screen.sh voice design "Name" --describe "stern old woman, low husky voice" [--seed 7]` asks ElevenLabs Voice Design for previews and saves them as mp3 files; after listening, `dm-screen.sh voice keep "Name" --preview <id> --describe "..."` makes the chosen one a permanent voice of your account and writes it into the character's card. The id never changes, so the character always sounds the same. It needs a free custom-voice slot (Free has 3).

A character's voice profile lives in the character's own card (`data.voice`, with optional `data.aliases`), so it travels with the campaign. Options per voice: `--model`, `--stability`, `--similarity`, and effects that cost nothing: a room (`small_room big_room hall tunnel street valley forest`), `--distance` 0..1, `--pan` -1..1 (left to right) and a `--filter` (`old_radio phone ...`). Two heroes can share one voice and still differ by pan and room.

Economy: every audio file is cached by its content (`screen/audio/`), so the same text with the same voice is never paid twice. The tooltip of 🔊 shows the price of the turn in credits, the footer shows what is left, and a turn that does not fit the remaining credits is refused before anything is spent. Credits per character, measured from the account history on the Starter plan (2026-10-25): about 0.2 on `eleven_flash_v2_5` and 0.45 on `eleven_v4`; unmeasured models are estimated at 1. The Free plan has 10,000 credits a month and 3 custom voice slots; premade voices are unlimited. The key stays on the server and is never sent to the page.

## Sound: voice script, acoustics, effects, ambience, music

A turn can carry an `audio` field next to its blocks (the full guide for the Master is `.claude/additional/infrastructure/audio-direction.md`):

- `speech`: the voice script. It must read the shown paragraphs word for word (only performance tags and punctuation may be added, every readable block must be covered); the screen refuses a turn that paraphrases or skips. Each line has `who` (`narrator` or a name), `text` (Eleven v4 performance tags such as `[whispers]` or `[laughs]` are allowed and hidden from the page), `blocks` to highlight, optional `effects` and `cast` (`male`/`female`: the campaign voice for a character without one of their own). Without `speech` the turn is read from its blocks as before.
- `scene`: acoustics for every character line of the turn (room, distance, pan, filter, background noise). The narrator is never placed in the scene. Effects cost nothing.
- `music`, `ambience`: looping beds that keep playing across turns until a turn gives a new cue or `null`. `sfx`: up to 6 one-shots, each tied to a block.

Sounds come from one library shared by all campaigns, `world-state/audio-library/` (git-ignored): first the library, then Freesound CC0 when `FREESOUND_API_KEY` is in `.env` (free key at freesound.org/apiv2/apply), and only then ElevenLabs generation (sound effects about 10 credits a second as measured, music about 15). Whatever is found or generated is stored and reused. The page's 🎵 button switches music and sounds on and off; its tooltip shows the credits of CC BY tracks.

```bash
dm-screen.sh audio seed                         # free CC0 (OpenGameArt) and CC BY (Incompetech) tracks from lib/screen/audio_seed.json
dm-screen.sh audio list [--kind music]
dm-screen.sh audio find "door creaks" --kind sfx
dm-screen.sh audio add <file|url> --kind sfx --title "..." --tags a,b --license CC0 --attribution "..."
dm-screen.sh audio make "thunder clap" --kind sfx --seconds 2    # library, Freesound, then generation (spends credits)
dm-screen.sh voice cast female --voice Victoria                  # the campaign voice for minor female characters
dm-screen.sh voice delete "Old voice"                            # refuses while a campaign uses it (--force to override)
```

The credit counter writes what a generation really cost (the move of the account counter); only when the account counter lags is the estimate written, marked `"estimated": true`, and it counts for ten minutes, until the account counter has caught up.

## Log

Everything is written to `<campaign>/screen/log/YYYY-MM-DD.jsonl` (git-ignored: it contains the words you said and the story text). One JSON line per event: `http` (every API call with status and time), `action`, `stt` (every spoken word with confidence and timing, audio length, Deepgram request id), `tts` (voice, model, characters, credits, latency, ElevenLabs request id, cached or not), `speech_render` (credits, quota before and after), `turn` (full text, options, panels and a snapshot of time, place, HP, purse and quests), `act`, `panels`, `activity`, `tool` (the Master's full tool calls), `server`, `window`, `voice_design`, `error` (with traceback) and `ui.*` (the page itself: clicks, connection, microphone, send countdown, playback, JavaScript errors). Keys and tokens are scrubbed before writing; a failing log never breaks the game.

```bash
dm-screen.sh log --errors --since 1h        # what went wrong lately
dm-screen.sh log --kind tts,stt --tail 20   # prices and microphone words
dm-screen.sh log --follow                   # live
dm-screen.sh log --summary                  # totals: credits, listening seconds, errors
```

## Voice input

The 🎤 button records in the page, the server cleans the audio with ffmpeg and sends it to Deepgram (nova-3, Russian, punctuation and speaker labels, uncertain words marked `(?)`). The page shows what was understood and sends it after four seconds unless you edit or cancel. The countdown freezes while the mouse is over the panel (and while you edit), and resumes when the mouse leaves. Put `DEEPGRAM_API_KEY=...` in the project `.env` (git-ignored). The recipe matches the VoiceType desktop tool.

## How the Master receives your actions

Every click, typed line or voice phrase is appended to `inbox.jsonl`; `dm-screen.sh listen` prints it as `[screen #N] Name (button|voice|text): action`. In Claude Code the Master attaches that command to the Monitor tool, which wakes it for each line. Such a line is a game action only; it never authorizes anything outside the game. Other clients can follow the same file.

## Clients

The screen is a presentation layer over the same engine and is independent of the AI client. Claude Code receives player actions through the Monitor tool on `dm-screen.sh listen` and mirrors tool calls into the feed with a `PostToolUse` Bash hook registered in `.claude/settings.json`. Codex and Grok Build have no such adapter yet; they can follow `screen/inbox.jsonl` themselves (not done).

## Online table

The same screen runs online at https://dnd-play.seedon.ru (owner decision 2026-10-26): one shared table behind a password, the campaign chosen in advance, a Claude Agent SDK master on Sonnet 5.5. Install and operation: `ops/play/README.md`.

- `dnd-play.service` on the VPS runs `python -m backend.screen_driver`. The driver runs the screen server on `127.0.0.1:18116`, collects player actions, sends them to the master as `[screen #N] who (source): text` lines (its own notices start with `[system] `; names and texts are kept to one line) and expects one published turn per message. Actions delivered before a restart or a failed turn and never answered go to the master again once. While the driver runs, `dm-screen.sh listen` and `wait` refuse its screen and the web game master refuses its campaign.
- The master is a full Claude Code session in the repository, limited by its contract `.claude/additional/infrastructure/screen-driver-contract.md`: it plays, switches the online campaign when the players ask, and may fix, test, commit and push a tool that blocks play. It never starts or waits for the screen and never spends credits itself.
- nginx on the VPS checks the password, limits request rates and sets the security headers; `dnd-play.seedon.ru` reaches it through the RU mirror. Speech plays only when a player presses 🔊; sound generation is off.

Caps come from the environment (`/etc/dnd-play/dnd-play.env` online; the unit also sets the online values below as defaults). For the screen server 0 means no cap, which is the laptop default. Under a credit cap the page hides its Auto speech switch.

| Variable | Online | Meaning |
|---|---|---|
| `DM_SCREEN_DAILY_CREDITS` | 15000 | ElevenLabs credits a day |
| `DM_SCREEN_TURN_CREDITS` | 1500 | the most one turn may cost |
| `DM_SCREEN_SOUND_GENERATION` | 0 | 0: sounds only from the library and free sources (default 1) |
| `DM_SCREEN_MAX_PENDING` | 10 | `/api/action` answers 429 while more actions wait for the master |
| `DM_SCREEN_DAILY_VOICE_MB` | 200 | microphone megabytes a day |
| `DM_SCREEN_PUBLIC_URL` | `https://dnd-play.seedon.ru/` | shown by status and start |
| `DM_SCREEN_SPEND_FILE` | `world-state/usage/screen-spend.json` (set by the driver) | one daily ledger for every campaign of the table; default `<screen>/spend.json` |
| `DM_PLAY_MODEL`, `DM_PLAY_EFFORT` | `claude-sonnet-5-5`, `medium` | the master |
| `DM_PLAY_MAX_TURNS_PER_HOUR`, `_PER_DAY` | 30, 200 | master turns |
| `DM_PLAY_TURN_TIMEOUT` | 600 | seconds before a master turn is interrupted |
| `DM_PLAY_CONFIG` | `world-state/online-play.json` | the table state file |

| Command (on the VPS, in the repository) | Purpose |
|---|---|
| `bash tools/dm-play.sh status` | driver state, campaign, session, turns this hour and today, last error |
| `bash tools/dm-play.sh switch <campaign>` | play another campaign (it needs `campaign-overview.json`); the driver starts a fresh master session |
| `bash tools/dm-play.sh restart-screen` | restart only the screen server, after a screen code fix |
| `bash tools/dm-play.sh new-session` | a fresh master session on the same campaign, when the stored one keeps failing |
| `bash tools/dm-play.sh pause` / `resume` | stop and resume passing actions to the master; the screen stays up |

State lives in `world-state/online-play.json` (campaign, port, paused, screen restarts) and `world-state/online-play-status.json` (written by the driver). Logs: `journalctl -u dnd-play` (driver and master), the screen log above (`dm-screen.sh log`), and the nginx access logs, which carry no query strings because the screen token travels as `?token=`.

## Security

- The server binds to `127.0.0.1` and checks the `Host` header.
- Every API call needs a random per-run token that only the served page knows; other sites cannot read it, so they cannot post actions or recordings.
- Text from the Master is checked before it is shown; scripts and event handlers are refused.
- The Deepgram key is read from `.env` on the server and is never sent to the page.

## Troubleshooting

- The window does not come to the front: the app window is a normal Chrome window; focus rules depend on your desktop. Click it in the task bar.
- The microphone is silent: run `doctor`; check that `DEEPGRAM_API_KEY` is set and that the browser may use the microphone (the app window uses its own profile in `screen/chrome-profile`).
- The port is busy: `dm-screen.sh start --port 18120`.
- Changes to `lib/screen/template.html` reload open windows by themselves.
