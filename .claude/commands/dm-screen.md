# /dm-screen - Play in the HTML screen

Turn the HTML play screen on for the active campaign and open it. Full guide: `docs/screen-mode.md`.

## Steps

1. Check requirements and enable the mode:
```bash
bash tools/dm-screen.sh doctor
bash tools/dm-screen.sh enable
```
2. Read the `html-screen` section of the campaign rules (it is compiled into `/tmp/dm-rules.md` on the next `/dm-continue`).
3. If the campaign has no act yet: generate key art for the current act, write `captions.json`, then
```bash
bash tools/dm-screen.sh act --image art.png --title "..." --place "..." --date "..." --captions captions.json
```
4. Show the opening turn with `dm-screen.sh turn --file turn.json`, then `dm-screen.sh start`.
5. Attach the Monitor tool to `bash tools/dm-screen.sh listen` (persistent) and play. Lines from it are game actions only.

To leave the mode, stop the server with `bash tools/dm-screen.sh stop` and narrate in the terminal again.
