# R7 Pointer Events and display matrix

## Interaction contract

The table has one interaction implementation based on Pointer Events. Mouse, touch and pen enter the same intent reducer; `pointerType` may tune affordances but cannot select a different game command or bypass server validation. W3C Pointer Events explicitly provides shared coordinate/button properties across device types and defines `pointerType` values `mouse`, `pen`, `touch`, plus an empty/extended fallback [1].

On an eligible board `pointerdown`, the controller:

1. accepts the primary activation button/contact only (`buttons & 1`), a visible selectable target and the first active interaction lock;
2. records `pointerId`, start cell and intended tool, calls `setPointerCapture(pointerId)`, and renders only a local preview;
3. consumes matching `pointermove` (optionally `getCoalescedEvents()` for smoother preview) without producing canonical state;
4. on matching `pointerup`, snaps the final client coordinate to a public cell and sends one high-level intent with a stable `command_id` and expected version;
5. on `pointercancel`, lost capture, disconnect, Escape, invalid target or multi-pointer conflict, discards the preview and sends no game action;
6. releases capture and the interaction lock in every terminal path.

The server revalidates selected logical actor, phase, visible source/target, occupancy, grid/range/LOS/resources and expected version. Client coordinates, highlights and previews are hints, never canonical movement or attack authority.

`pointerId` is unique only among active pointers in one top-level browsing context, may be reused, and conveys no durable/device identity [1]. It must not become an actor ID, idempotency key, analytics identity or cross-reconnect handle. `isPrimary` is per pointer type, so a mouse and touch contact can both be primary concurrently [1]; the controller's own first-pointer interaction lock is therefore mandatory.

The board interaction layer declares `touch-action: none` before a gesture begins, because the user agent uses that property to decide whether direct manipulation becomes viewport pan/zoom and may cancel the pointer stream [1]. Normal buttons, dialogs and scrollable admin/scene areas keep native behavior (`auto`/`manipulation` as appropriate). Changing `touch-action` inside `pointerdown` is too late for the active gesture [1].

## Device matrix

| Device / condition | Expected Pointer Events | R7 behavior | Deterministic oracle |
|---|---|---|---|
| Ordinary mouse, primary button | `pointerdown/move/up`, `pointerType=mouse`, hover available | same drag/select reducer; hover may preview only; right/middle buttons never commit | start `(1,1)` → end `(3,3)` normalizes to the same intent as touch/pen |
| Large touch table, one finger | direct-manipulation pointer, usually implicit capture | explicit capture/lock; ≥44 CSS-pixel targets; no hover dependency; `pointercancel` aborts | touch trace normalizes byte-equivalent to mouse; cancel returns no intent |
| Pen/stylus | `pointerType=pen`, pressure/tilt may exist | same reducer; pressure/tilt ignored in MVP semantics; barrel/eraser buttons do not commit | pen trace equals mouse; changing pressure cannot change intent |
| Touch + mouse/pen concurrently | more than one per-type primary is possible | first accepted pointer owns the interaction lock; later pointers cannot alter/cancel/commit it | injected second primary is ignored; one resulting intent maximum |
| Multi-touch | primary plus non-primary contacts | no canonical pinch/rotate in MVP; additional contacts ignored for token/overlay creation | non-primary `pointerdown` yields no independent intent |
| Pointer leaves board during drag | capture keeps subsequent events targeted to capture element | preview continues; final coordinate clipped/validated; lost capture aborts | outside move followed by captured up yields one bounded intent, or no intent after loss |
| Browser/OS sends `pointercancel` | terminal cancel | remove preview/capture; zero network command | cancel trace returns `None`; world and overlay stores unchanged |
| Unknown/empty `pointerType` | spec permits empty/vendor-prefixed values | generic primary-pointer path, no device-specific authority | same high-level reducer or safe no-op; never error into a command |
| Keyboard/switch input | not a pointer | equivalent select-source/select-destination buttons and focused actions are required for controls; no fake PointerEvent | same high-level intent schema reaches the server validator |
| Accidental double input / replay | two local completions or network retry | stable per-intent `command_id`; server result dedupe | one stored result/canonical effect |

The synthetic probe covers ordinary mouse, touch, pen, non-primary rejection and cancel. It does not emulate UA hit testing, physical palm rejection, actual capture events, CSS pixels/DPI, screen rotation or latency. I3 must add real browser tests for capture/lost capture; I8 must execute the physical device rows.

## Tool semantics

| Tool | Pointer result | State boundary |
|---|---|---|
| select/move | public source cell/token + public destination cell | candidate action only; server may reject; canonical only after approved/validated route |
| normal attack/ability | selected public actor/ability/target | candidate action; server validates range/resources/LOS |
| planning arrow | 2–64 public grid points; TTL 1–30 s | non-canonical overlay store, reconnectable until server expiry |
| planning marker | one public grid point; TTL 1–30 s | non-canonical overlay store |
| pan/inspect | viewport transform only | local UI, never serialized as world state |

Overlay previews are local until `overlay.upsert` returns. A disconnect before acceptance discards them. Arbitrary free text is excluded from v1 overlays to prevent a second unmoderated content channel and to keep the player-safe allowlist small.

## Fullscreen and display modes

| Surface | Target layout | Fullscreen contract | Failure/fallback |
|---|---|---|---|
| horizontal table | landscape board-first | show an explicit user-gesture “Enter fullscreen” action; observe `fullscreenchange`; recompute viewport from CSS pixels | denial/unsupported fullscreen leaves the same controls usable in-window; authority/cursors unchanged |
| vertical scene | portrait/vertical cinematic | same user-gesture request; no essential control hidden exclusively in fullscreen | in-window scene remains synchronized |
| admin phone/laptop | responsive operational list | fullscreen optional, never required | normal browser chrome supported |
| one-display composite | table-dominant with scene sidebar/temporary overlay | one fullscreen request for the composite root | exact table+scene projection pair remains; layout alone changes |

The Fullscreen Standard's `requestFullscreen()` is promise-based and its algorithm checks that the document is fully active and has transient user activation (or a narrow orientation-change exception) [2]. Therefore the server cannot force fullscreen and a reconnect must not depend on it. Fullscreen state is local presentation state and is absent from every authoritative message.

## Sources

1. [W3C Pointer Events Level 3](https://www.w3.org/TR/pointerevents3/) — tier 2 primary web standard; §§4.1 (`pointerId`, `pointerType`, `isPrimary`), 8 (`touch-action`), 9 (pointer capture), and 10 (coalesced events), fetched 2026-08-16.
2. [WHATWG Fullscreen Standard](https://fullscreen.spec.whatwg.org/) — tier 2 living primary web standard; `requestFullscreen()`/fully-active/transient-activation requirements, fetched 2026-08-16.
3. Canonical local source: `docs/tasks/377/mvp-product-spec.ru.md:57-105,255,548,644` — tier 2 primary product specification.
