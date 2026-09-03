# R6 voice, recording, and asset provenance boundary

Status: mandatory input gate for future I6/I8 work. This document does not assert that any current voice or asset is licensed. R8 classifies the present voice/audio inputs as `AVOID_LITERAL`; the R6 runtime therefore starts with an empty approved roster and fails silent/text-only until evidence is accepted [L1].

## Boundary and authorities

The rights/production authority, not the game model, provider, browser, or audio router, may move an entry to `approved`. It owns performer consent, contracts, territory/term, withdrawal, source files, synthetic-voice authorization, and attribution. The audio router consumes only immutable approved manifest versions. It cannot accept a raw ElevenLabs `voice_id`, upload a sample, clone a voice, invent a fallback, or play an unmanifested path.

The boundary separates four subjects:

1. **Voice identity** — the performer/voice model and the right to generate, cache, edit, distribute, and publicly perform outputs.
2. **Spoken content** — the disclosed text and, for cached lines, the authored script/version/localization approval.
3. **Audio master** — the exact recorded/generated file, transformations, checksum, and permitted runtime uses.
4. **Music/SFX work and recording** — composition/work, master recording, stems/loops/edits, attribution, and public-performance or distribution constraints.

A provider's technical availability is not provenance. ElevenLabs documents that public Voice Library voices may be removed or become unavailable, and may have credit multipliers [P1]. ElevenLabs also says Professional Voice Cloning is only for the account holder's own voice; another performer must create, verify, and share their own clone [P2]. These provider controls do not replace a production contract or R8 legal approval.

## Required manifests

### `voice_manifest`

Every route, including a generic archetype, must resolve by `voice_key` into an immutable versioned entry:

```json
{
  "schema_version": 1,
  "manifest_version": "voice-2026-08-16.1",
  "voice_key": "narrator.severin",
  "character_scope": ["narrator:severin"],
  "archetype_scope": [],
  "provider": "elevenlabs",
  "provider_voice_id_secret_ref": "secret://voices/severin",
  "model_id": "eleven_flash_v2_5",
  "locale": "en",
  "provenance_record_id": "rights:voice:severin:v1",
  "consent_scope": [
    "source_recording",
    "voice_model_creation",
    "synthetic_generation",
    "editing",
    "cache",
    "application_distribution",
    "public_performance"
  ],
  "territories": ["owner-approved-value-required"],
  "term_start": "owner-approved-value-required",
  "term_end": "owner-approved-value-required",
  "withdrawal_process_id": "withdrawal:voice:severin",
  "retention_class": "owner-approved-value-required",
  "attribution": "owner-approved-value-required",
  "status": "blocked_pending_rights"
}
```

`status` is `blocked_pending_rights | approved | withdrawn | expired`. Only `approved` is routable. The owner must supply every placeholder; engineering must not infer contract terms. `provider_voice_id_secret_ref` resolves only server-side and never appears in a browser manifest or model prompt.

Severin Crow is a distinct brand voice and has `fallback=text_only`. Each authored important NPC has a distinct cleared entry and may name one cleared generic archetype fallback in its own manifest. Generic archetypes are finite authored entries such as `npc.guard` or `npc.scholar`; there is no `random_voice`, provider-library search, voice similarity selection, or silent provider substitution.

### `audio_asset_manifest`

Every cached combat line, music loop/stem, and SFX master is immutable and content-addressed:

```json
{
  "schema_version": 1,
  "manifest_version": "audio-2026-08-16.1",
  "asset_id": "combat.hit.001",
  "kind": "cached_speech",
  "event_key": "combat.hit",
  "speaker_voice_key": "npc.guard",
  "locale": "en",
  "script_version": "combat-lines-en-v1",
  "source_master_id": "master:combat-hit-001",
  "derivation": "edited-recording-or-approved-generated-output",
  "generator_provider": null,
  "generator_voice_key": null,
  "model_id": null,
  "generated_at": null,
  "encoding": "opus-or-owner-approved-value-required",
  "duration_ms": 520,
  "sha256": "64-lowercase-hex-required",
  "provenance_record_id": "rights:asset:combat-hit-001:v1",
  "allowed_uses": ["runtime_playback", "application_distribution"],
  "territories": ["owner-approved-value-required"],
  "term_end": "owner-approved-value-required",
  "attribution": "owner-approved-value-required",
  "status": "blocked_pending_rights"
}
```

For `music`, the provenance record separately identifies the composition/work, master recording, all contributors, edit/loop/stem permission, attribution, and public-performance/distribution scope. For `sfx`, it identifies the source library/recording and edit/distribution scope. For pre-generated speech, the record joins both the approved voice identity and the exact output master. A right to use a voice does not automatically clear a particular script or audio master, and a cleared master does not authorize future synthesis.

The build/publish gate rejects an asset when its manifest is missing, status is not `approved`, checksum differs, term is expired, locale/script version is absent, or any required voice/work/master relationship is unresolved. Runtime failure is silent for music/SFX and text-only for speech; it never searches the filesystem or provider library for a substitute.

## Offline generation versus live generation

Normal combat uses only approved `audio_asset_manifest` entries. If any cached line was generated through ElevenLabs during production, its input text, voice manifest version, model/settings, provider request evidence, output checksum, editorial approval, and provider-retention disposition belong in the production provenance record. Runtime never regenerates a missing combat asset.

Live story generation is allowed only after all of these are true:

- the selected voice entry is `approved` at the stored manifest version;
- the line text is already disclosed by the R4 safe presentation gate;
- the privacy/retention authority has accepted the provider mode for that data class;
- the provider secret, voice ID, model, and logging mode resolve server-side;
- the current R7 playback lease is unambiguous, otherwise generation is not started;
- an attempt record exists before external I/O.

The attempt record links `line_id`, `text_event_id`, voice/model/manifest versions, input character count and a keyed content HMAC, but observability stores no plaintext. The HMAC key is server-only and rotated/versioned; an unkeyed short-line hash is forbidden because it is dictionary-recoverable. The already-disclosed caption remains the authoritative readable record.

## Withdrawal and expiry

Withdrawal/expiry is a new manifest version and an operational stop condition:

1. Mark the voice or asset non-routable and invalidate future cache/manifests.
2. Cancel any in-flight provider context for that voice and fence browser playback through the R6 contract.
3. Prevent new generation/playback immediately; use declared approved fallback or text-only/silence.
4. Inventory generated/cached masters linked to the provenance record and apply the rights authority's disposition. Do not assume the right to retain old output.
5. Keep minimal audit evidence required by the approved retention schedule; do not keep source samples or line audio "for debugging" without an explicit basis.

Provider deletion is not equivalent to application deletion. ElevenLabs documents that TTS input/output retention is enabled by default; its Zero Retention Mode is available only to select Enterprise customers, API-only, and voice-cloning samples are not eligible. Default deletion can leave backups for up to 30 days and limited logs may remain [P3]. Future deployment must record the actual entitlement/configuration and cannot advertise zero retention from an application flag alone.

## Falsification gates

The following conditions stop I6/I8; fallback is text-only/silence:

| Gate | Required evidence | Falsifier / stop condition |
|---|---|---|
| V1 Severin identity | approved performer/voice-model record covering every consent scope above | public-library-only identity, inferred consent, missing synthetic/cache/distribution right, expired/withdrawn entry |
| V2 important NPC | approved exact voice plus declared approved archetype fallback or text-only | runtime provider search, raw voice ID supplied by AI/admin/browser, uncleared fallback |
| V3 generic archetype | finite approved roster, locale and intended character scope | generic label with no performer/model provenance or similarity/random selection |
| A1 cached combat | exact script + voice + master + checksum + runtime use approval | live TTS occurs on `cache_only`, asset missing/unapproved/modified, retry selects a different line |
| A2 music/SFX | work/master/contributor/edit-loop/distribution evidence | filesystem/provider fallback or generated music/SFX in MVP |
| P1 disclosure/retention | safe `text_event_id`; approved provider retention mode and deletion procedure | hidden prompt/world field transmitted; retention described as zero without entitlement and observed configuration |
| W1 withdrawal rehearsal | inventory query reaches every linked voice/output/asset and new routing fails closed | any in-flight/new playback survives withdrawal, or linked output cannot be enumerated |

No synthetic test can approve V1–A2: it can only prove that unapproved inputs fail closed. The owner/legal/audio-production authorities must provide the evidence.

## Interfaces

- **R4/unified core → R6:** only committed `presentation_id`, disclosed `text_event_id`, canonical event/speaker identifiers, and `audio_policy`; never raw voice IDs or asset paths.
- **R8 → R6:** accepted provenance record IDs, rights state, attribution/term/territory/withdrawal constraints, and retention approval. Until then, all current voice/asset inputs remain `AVOID_LITERAL` [L1].
- **R6 → R7:** opaque cleared `media_ref` plus stable line/context/playback/fence identity. R7 never receives provider credentials or a rights decision.
- **R6 → I8 content production:** required roster/asset schemas, missing evidence, offline-generation receipt fields, and target acoustic test candidates. I8 returns immutable approved manifest versions, never ad-hoc paths.

## Sources

- **[L1] Tier 2, local accepted architecture/legal research:** `docs/tasks/377/phase3/r8/ip-route.md` and `transfer-manifest.tsv` on `main`; current voice/audio inputs are fail-closed and the required voice/asset evidence is enumerated there.
- **[P1] Tier 2, provider primary documentation:** ElevenLabs, [Voice Library](https://elevenlabs.io/docs/eleven-creative/voices/voice-library), opened 2026-08-16.
- **[P2] Tier 2, provider primary documentation:** ElevenLabs, [voice-cloning overview](https://elevenlabs.io/docs/eleven-creative/voices/voice-cloning), opened 2026-08-16.
- **[P3] Tier 2, provider primary documentation:** ElevenLabs, [Zero Retention Mode](https://elevenlabs.io/docs/eleven-api/resources/zero-retention-mode), opened 2026-08-16.
