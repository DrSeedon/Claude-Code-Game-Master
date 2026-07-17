---
name: cinematic-scene
description: Generate wide cinematic campaign images that function like game loading screens or chapter key art. Use during tabletop or DM gameplay for a major location reveal, first appearance of an important character or faction, major confrontation, turning point, aftermath, or explicit requests for a scene image, poster-like frame, loading screen, cinematic illustration, or widescreen campaign art.
---

# Cinematic Scene

Create a single raster image with the available image-generation tool. Treat it as a visual story beat, not an advertisement or a lineup of assets.

## Build Canonical Context

1. Use the already prepared DM context when available. Do not reread campaign files without a concrete missing detail.
2. Include only facts currently visible or known to the player. Never depict hidden scenario results, inactive complications, secret identities, unrevealed enemies, or future transformations.
3. Preserve continuity: current location, time, weather, character appearance, equipped armor and weapon, wounds, conditions, companions, and established faction design.
4. When a necessary visual fact is undefined, choose a restrained detail that does not create new plot canon.

## Choose Visual Beats

Generate automatically when cinematic visuals are enabled and one of these occurs:

- first reveal of a major location;
- first clear appearance of a major character, creature, or faction;
- encounter opening, boss reveal, major reversal, or chapter climax;
- visually meaningful aftermath or chapter transition.

Skip routine travel, shopping, inventory changes, repeated views, ordinary dialogue, and individual combat turns. At `occasional` frequency, target no more than one image per major scene and avoid consecutive image turns unless the user asks.

## Compose the Frame

- Request a landscape `16:9` frame, ideally `1792x1024` or the nearest supported size.
- Make the environment readable and story-bearing. Allocate roughly two thirds of the frame to location, scale, weather, architecture, activity, or threat.
- Place characters asymmetrically inside the scene. Use foreground, middle ground, and background with one clear focal hierarchy.
- Show action, tension, travel, observation, or preparation. Avoid a row of posed characters facing the camera.
- Use a cinematic camera choice: low wide angle, over-the-shoulder, elevated establishing view, deep corridor perspective, or distant compressed silhouette.
- Use motivated lighting from actual scene sources. Preserve readable silhouettes and material detail.
- Prefer game loading-screen key art, grounded concept art, or a film still. Avoid glossy product advertising, collage layouts, character sheets, floating portraits, UI frames, logos, captions, and generated text.
- Do not make every frame dark. Match exposure and palette to the location while retaining clear spatial information.

## Build the Generation Prompt

Write one coherent prompt in this order:

1. output format and presentation;
2. location, time, weather, and scale;
3. foreground subject and current action;
4. middle-ground relationships or activity;
5. background landmark or threat;
6. camera, lens feeling, lighting, palette, and material detail;
7. continuity constraints and exclusions.

Explicitly include: `widescreen 16:9`, `cinematic game loading-screen key art`, `environment-first composition`, `asymmetrical staging`, `no text`, `no logo`, `no UI`, and `not a character lineup`.

## Generate as the Final Action

If scene narration or a player decision prompt is also needed, send all text before invoking image generation. Invoke the image tool as the final action of the turn and send nothing afterward.

If no raster image-generation tool is available, continue gameplay without generating an image. Do not substitute SVG, HTML, or ASCII art.
