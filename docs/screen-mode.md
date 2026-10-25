# HTML play screen

Play any campaign in a themed web page instead of terminal text: key art per act, live story and stats, option buttons, a text field, a microphone, a picture view with captions, and a feed of the Master's visible work (thinking, dice, saves). The terminal only carries a one-line reply.

It is optional and per campaign. Everything is local: a small server on `127.0.0.1` and a Chromium app window.

## Quick start

```bash
bash tools/dm-screen.sh doctor     # what is missing (browser, ffmpeg, Pillow, microphone key)
bash tools/dm-screen.sh enable     # applies the `html-screen` rule to the active campaign
```

Then play as usual (`/dm`). The Master (the AI) follows the rule in `campaign-rules.md`:

1. For every act it generates key art and runs `dm-screen.sh act ...` (the colors come from the art).
2. It starts `dm-screen.sh start` once and attaches a listener (`dm-screen.sh listen`) so your clicks and voice reach it.
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
| `dm-screen.sh act --image art.png --title "..." [--kicker --place --date --style classic\|severe\|soft --lang en\|ru --captions captions.json --labels labels.json]` | Start a new act: copies the art, derives the theme from it. |
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
Zones: `tl` (top-left row), `tr` (top-right column), `bottom` (bottom row). They never overlap. `dot` is a point on the picture in image pixels; a leader line is drawn from it.

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

Economy: every audio file is cached by its content (`screen/audio/`), so the same text with the same voice is never paid twice. The tooltip of 🔊 shows the price of the turn in credits, the footer shows what is left, and a turn that does not fit the remaining credits is refused before anything is spent. Credits per character: 0.5 on `eleven_flash_v2_5`, 1 on `eleven_v4`, `eleven_v3` and `eleven_multilingual_v2`. The Free plan has 10,000 credits a month and 3 custom voice slots; premade voices are unlimited. The key stays on the server and is never sent to the page.

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
