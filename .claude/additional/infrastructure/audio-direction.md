# Audio Direction for the HTML Screen

Read this before writing the `audio` field of a screen turn or creating a voice. The screen plays everything from one turn file: the shown `blocks` are for the eyes, `audio` is for the ears.

## The `audio` field

```json
"audio": {
  "scene":    {"environment_id": "big_room", "background_noise_id": "cafe"},
  "speech":   [{"who": "narrator", "text": "...", "blocks": [0, 1]},
               {"who": "Zoya", "text": "[whispers] ...", "blocks": [3]},
               {"who": "Hostess", "text": "...", "cast": "female", "blocks": [4]}],
  "music":    {"cue": "cheerful medieval tavern lute jig", "tags": ["tavern", "medieval", "cheerful"]},
  "ambience": {"cue": "busy tavern crowd, rain on the roof", "tags": ["tavern", "crowd", "rain"]},
  "sfx":      [{"cue": "heavy tin mug slammed on a wooden table", "tags": ["mug", "table"], "block": 3, "seconds": 2}]
}
```

Every part is optional. A turn without `speech` is read from its blocks as before.

## Voice script (`speech`)

- **The voice reads exactly what is shown.** Every readable paragraph (`<p>` blocks except dice lines) is voiced word for word, the narrator's text and the characters' lines alike. Never shorten, paraphrase, reorder or add words in the voice script: if something is too long to be heard, shorten the shown block itself. The screen refuses a turn whose script differs from the blocks or skips one.
- What may be added: performance tags in square brackets, and punctuation that shapes delivery (`…` trails off, `—` cuts in, `!` raises energy).
- One entry per speaker turn. `who` is `narrator` or the character's name as written in their card (first name works). `blocks` (required) lists the shown blocks the line reads; they are highlighted while it plays. Consecutive narration blocks may share one entry.
- A character line reads only the quoted words of `<p><b>Name:</b> «line»</p>`, never the name.
- Performance tags (Eleven v4) are written in English inside `text` and are removed from what the page shows: emotions and delivery (`[whispers]`, `[laughs]`, `[sighs]`, `[angry]`, `[sarcastic]`, `[nervous]`, `[shouting]`), sounds a voice makes (`[clears throat]`, `[gulps]`, `[snorts]`), and pacing (`[pause]`). Use one or two per line where they change the delivery; never tag every sentence.
- Nothing hidden from the players goes into blocks, so nothing hidden is ever spoken.
- The narrator stays outside the scene: scene acoustics never apply to the narrator.

## Who speaks with which voice

- The campaign narrator: `dm-screen.sh voice narrator --voice ...`.
- Important characters get a voice of their own, made with Voice Design (below): the player characters, the core party, and recurring key characters (a main villain, a patron, a companion who keeps coming back). Give the voice when the character first matters, ask the players before spending, and store it in the card with `voice keep` (or `dm-screen.sh voice set "Name" --voice ...` for an existing voice).
- Every other character uses the campaign cast: add `"cast": "female"` or `"cast": "male"` to their line. Never give a minor or one-scene character a voice of their own.
- **At most 10 own voices on the account** (the Starter plan's `voice_limit`; library voices such as the narrator and the cast do not count). Before designing, check the slots: `dm-screen.sh voice show` prints `own voice slots: N of 10 used`. When all 10 are used, ask the players which voice to retire: a character who left the story gives the slot back with `dm-screen.sh voice delete "Name"` (it refuses while any campaign still uses the voice) and returns to the cast.
- `dm-screen.sh voice show` lists the current setup.

## Acoustics (`scene` and line `effects`, free)

Effects never change the price. `scene` applies to every character line of the turn; a line's own `effects` override it.

| Field | Values | Use |
|---|---|---|
| `environment_id` | `small_room`, `big_room`, `hall`, `tunnel`, `street`, `valley`, `forest` | Where the characters stand: a tavern is `big_room`, a cell `small_room`, a temple `hall`, a dungeon corridor `tunnel` |
| `send_level` | 0..1 | How much reverb (0 turns it off) |
| `distance` | 0..1 | A voice behind a door or across a hall: 0.6..0.9 |
| `pan` | -1..1 | Two speakers sharing a voice: put them left and right |
| `background_noise_id` | `cafe`, `city`, `call_center`, `keyboard` | A bed under the voice: `cafe` for a busy tavern, `city` for a street |
| `filter_preset_id` | `old_radio`, `robot`, `cheap_microphone`, `phone`, `low_quality_phone`, `bright_phone` | Magic mirrors, speaking skulls, voices through a pipe |

## Sounds: `music`, `ambience`, `sfx`

- `cue` is an English description of the sound, concrete and physical ("heavy oak door creaks open slowly", not "a scary sound"). `tags` are 2..5 English keywords (place, mood, object).
- The screen looks in the shared library first (free), then Freesound CC0 (free), and generates with ElevenLabs only when nothing fits and the players press 🔊. Generated sounds join the library, so a good cue is reused by every later turn and campaign.
- Reuse the same cue words for the same thing ("tavern", "dungeon", "battle") so the library finds it again.
- Prefer music that does not sound like stock video background: medieval and folk pieces (lute, fiddle, flute, choir) over cartoon-comedy tracks, even in a comedy campaign. The humour comes from the narration, not from the music.
- `music` and `ambience` loop and keep playing across turns: leave them out to keep the current one, give a new cue only when the place or mood really changes, set `null` to stop. One music bed per scene, not per turn.
- `sfx`: 0..3 per turn, only for moments that matter (a door, a blow, a spell, a crash). `block` ties the sound to the shown block where it happens. `seconds` 1..4 for one-shots.
- `"generate": false` on a cue means "only if it costs nothing".
- Prices when generated (measured on the Starter plan): sound effects and ambience about 10 credits a second, music about 15 credits a second, Eleven v4 speech about 0.45 credits a character. The 🔊 tooltip shows the whole turn's price; what the library already has costs nothing.
- Fill the library cheaply with `dm-screen.sh audio seed` (free tracks) and check what is there with `dm-screen.sh audio list` / `audio find "cue" --kind sfx`.

## Creating a voice (Voice Design)

Only for the important characters above, only with the players' consent, and only while a slot of the 10 is free: each design costs credits for its sample text (≈ one credit a character) and returns three previews.

1. Describe the voice in English, one or two sentences, in this order: gender and age, timbre and pitch, pace and energy, accent, manner and attitude, one "sounds like" image. Example: "A gruff man in his fifties with a deep gravelly voice, slow and deliberate, a heavy Slavic accent, speaks like a retired executioner who is tired of people and secretly kind."
2. Write a sample of 100..1000 characters in the campaign language in the character's own voice (a real line they would say), with one or two performance tags.
3. `dm-screen.sh voice design "Name" --describe "..." --text "..."`, let the players listen to the three previews, then `dm-screen.sh voice keep "Name" --preview <id> --describe "..."`.
4. A kept voice takes one of the 10 slots until it is deleted; previews that were not kept take none.
