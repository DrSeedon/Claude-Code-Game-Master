---
name: cinematic-scene
description: >
  Generate wide cinematic campaign images like game loading screens or chapter
  key art during DM gameplay. Use for major location reveals, first appearance of
  important characters/factions, confrontations, turning points, aftermath, or
  explicit requests for a scene image, poster frame, loading screen, or widescreen
  campaign art. Prefer when cinematic_visuals is enabled on the active campaign.
when-to-use: >
  cinematic scene, loading screen art, campaign illustration, chapter key art,
  major visual beat during /dm play
---

# Cinematic Scene (Grok Build)

Create a single raster image with Grok `image_gen` (or `image_edit` when
preserving an established look). Treat it as a visual story beat, not an ad or
asset sheet.

Full composition doctrine lives in `codex-skills/cinematic-scene/SKILL.md` —
follow that file for beats, framing, prompt order, spoilers, and frequency.
This skill only remaps tools for Grok.

## Grok tool mapping

| Shared skill wording | Grok |
|---|---|
| available image-generation tool | `image_gen` |
| edit / preserve likeness | `image_edit` with prior image path |
| landscape 16:9 | `aspect_ratio: "16:9"` |
| show result | Tell the user the short path (`images/N.jpg`) so it renders |

## Rules that still apply (summary)

1. Use already prepared DM context; do not reread the whole campaign for a picture.
2. Depict only player-known facts. No spoilers, hidden complications, or unrevealed identities.
3. Continuity: location, time, weather, appearance, gear, wounds, companions, factions.
4. Auto-generate only on major beats when `cinematic_visuals` is enabled; skip routine travel/combat turns.
5. Environment-first, asymmetrical staging, no text/logo/UI/character lineup.
6. If narration is needed, write it **before** the image call. Image tool is the last action of the turn.
7. If image tools fail or privacy blocks media, continue gameplay without treating art as a blocker.
