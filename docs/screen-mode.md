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

## Voice

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
