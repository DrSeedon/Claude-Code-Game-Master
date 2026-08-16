<!-- codex-review-metadata: {"reviewer_model": "gpt-5.6-sol"} -->

## Summary

The research is strong and appropriately cautious about synthetic evidence, provider latency, cost policy, retention entitlement, and provenance. I reproduced the specified command: all 10 tests passed (`OK`, 0.004s locally), and generated output matched `probe-results.json` byte-for-byte. This remains an author-created fake oracle, not independent evidence about browsers, providers, physical sound, or costs.

I inspected every R6 artifact, the canonical specification/research/plan, merged R4/R8 inputs, and the assigned read-only R7 evidence. Provider facts checked against current official documentation were materially supported, including voice-bound multi-context sockets, `close_context`, five-context limit, single-use tokens, response cost headers, and ZRM restrictions.

Inspection evidence from an artifact not quoted in the prompt: “A provider's technical availability is not provenance.”

## Findings (blocking/suggestion/question)

blocking: [playback-event-contract.md:272](</home/kesha/orchestra/worktrees/home-kesha-projects-dnd-game-master/research-audio-output/docs/tasks/377/phase3/r6/playback-event-contract.md:272>) — SFX and music bypass the lease/fence contract, so the design does not actually guarantee one audible client for all audible output.

The contract correctly says:

> “Only that consumer may receive a playable `media_ref`/chunk.”

But the normative messages are:

> “`music.set_state` is `{event_id, presentation_id, music_state, track_id, manifest_version, crossfade_ms}`.”

> “`sfx.play` is `{event_id, presentation_id, sfx_key, asset_id, manifest_version, priority_class, gain}`.”

Neither carries `lease_id`, `lease_generation`, `consumer_id`, nor `audio_fence`. The research’s R7 delta likewise adds fences only to `audio.play`/chunks/`audio.stop`. A former leader can therefore accept reordered or late music/SFX after lease loss or pause/end unless implementation invents semantics outside the “exact” contract. The fake covers stale speech playback only and cannot detect this.

Concrete correction: define exact leased envelopes for `music.set_state` and `sfx.play`, carrying at least lease ID/generation, audio fence, stable event ID, manifest identity, and leader-scoped media reference. Specify identical fail-silent acceptance rules and room-wide stop behavior for every audible lane. Extend G3 and the fake tests to re-elect during music/SFX delivery and prove the stale client produces no sound.

blocking: [playback-event-contract.md:304](</home/kesha/orchestra/worktrees/home-kesha-projects-dnd-game-master/research-audio-output/docs/tasks/377/phase3/r6/playback-event-contract.md:304>) — the normative telemetry schema includes the exact unkeyed hash that the privacy contract forbids.

The telemetry row includes:

> “`input_character_count, text_sha256,`”

and later also includes `text_hmac_sha256`. Yet the same artifact states:

> “an unkeyed short-line hash is forbidden because it permits dictionary recovery.”

This contradicts the privacy boundary and makes the claimed “exact” contract unsafe: short narrator/combat lines have a small enough domain for offline recovery.

Concrete correction: remove `text_sha256` entirely from the normative telemetry schema, retain only the keyed HMAC plus `telemetry_key_id`, and add a schema-level/probe assertion rejecting any `text_sha256`, plaintext, or unapproved content-derived field. Also remove the duplicated `input_character_count`.

suggestion: [playback-event-contract.md:288](</home/kesha/orchestra/worktrees/home-kesha-projects-dnd-game-master/research-audio-output/docs/tasks/377/phase3/r6/playback-event-contract.md:288>) — require completed cancel fan-out and an unambiguous current lease before explicit retry starts provider I/O. Presently retry requires only a terminal line state and valid text/manifest routes. It could begin a new provider context while the old close/stop tasks remain pending or while no playable leader exists, contradicting the stated one-generating-context rule and the provenance document’s “lease unambiguous” admission gate. Persist retry as requested, but delay external I/O until provider-close/browser-stop disposition and lease admission are known.

suggestion: [playback-event-contract.md:35](</home/kesha/orchestra/worktrees/home-kesha-projects-dnd-game-master/research-audio-output/docs/tasks/377/phase3/r6/playback-event-contract.md:35>) — connect durable `SpeechLine.text`, generated media, and attempt records to explicit retention/deletion classes. The documents correctly defer retention policy to its authority, but the exact durable record contains full text without specifying deletion linkage, while provenance says the existing caption is authoritative. Add retention-class and expiry/disposition references and require deletion/withdrawal inventory coverage for line text, media, caches, and telemetry.

question: [playback-event-contract.md:293](</home/kesha/orchestra/worktrees/home-kesha-projects-dnd-game-master/research-audio-output/docs/tasks/377/phase3/r6/playback-event-contract.md:293>) — should a successor leader resume the current preauthored music state? “Future media only” is correct for speech, but music represents persistent scene state rather than historical utterance replay. The contract should explicitly choose either silence until the next canonical state transition or a freshly leased/idempotent rendering of the current music state. This becomes especially important once music receives proper lease/fence identity.

## Verdict

**NEEDS WORK — 2 blocking findings.**

The server-owned hybrid decision is otherwise decision-grade, and the synthetic claims are mostly calibrated honestly. The exact protocol is not ready for planning/implementation until all audible lanes share lease/fence ownership and the forbidden unkeyed text hash is removed.

Blocking-finding count: **2**.

## Round (2026-08-16T18:55:04Z)

<!-- codex-review-metadata: {"reviewer_model": "gpt-5.6-sol"} -->

## Summary

All five prior findings are closed in the current artifacts. The required command passes 14 tests (`OK`, 0.003s in this run), and generated probe output matches `probe-results.json` byte-for-byte. The fake remains correctly scoped as synthetic evidence.

Inspection evidence from the updated contract: “Missing/expired policy values block provider I/O and persistence.”

One new cancellation/re-election ordering hole remains.

## Findings (blocking/suggestion/question)

- **FIXED — prior all-lanes blocker.** Speech, music, and SFX now carry lease/generation/consumer/fence identities; `all_audio` clears every lane; G3 and the fake cover stale music/SFX and music reconstruction.

- **FIXED — prior telemetry blocker.** `text_sha256` and the duplicate count field are removed. The contract retains keyed HMAC metadata, and the fake rejects unknown or forbidden content fields.

- **FIXED — retry suggestion.** Provider I/O now waits for durable cancellation dispositions and one unambiguous unlocked lease.

- **FIXED — retention suggestion.** `SpeechLine` uses `text_ref` and defines retention, deletion, and withdrawal-inventory links.

- **ANSWERED — music reconstruction question.** A successor receives a fresh leased rendering of persistent music from loop zero; speech and SFX are not replayed.

- **blocking:** [playback-event-contract.md:306](</home/kesha/orchestra/worktrees/home-kesha-projects-dnd-game-master/research-audio-output/docs/tasks/377/phase3/r6/playback-event-contract.md:306>) — a higher-fence media event can arrive before its stop/control event and be accepted without clearing older audio. The contract says acceptance permits:

  > “`audio_fence >= current fence`”

  But only `audio.stop` records the higher fence and clears invalidated lanes. If fresh music/SFX—or similarly a new speech play—at fence 14 is reordered ahead of `all_audio` stop at fence 14, a client at fence 13 can start it while old fence-13 media remains audible. The fake always calls `stop_all` synchronously before granting/delivering and therefore cannot expose this race.

  Concrete correction: either require media fence equality with an already-applied local control fence, buffering/rejecting future-fence media, or define receipt of higher-fence media as an atomic fence advance that first performs the required scoped clear. Add a test delivering new music/SFX/speech before the reordered stop and prove no old/new overlap or cancelled audio survives.

- **suggestion:** The fake telemetry validator rejects unknown fields but accepts rows missing required fields because it checks only `set(row) <= METRIC_FIELDS`. Add an exact required-field schema/check so missing retention or deletion identities cannot pass the synthetic oracle.

## Verdict

**NEEDS WORK — 1 blocking finding.**

Prior blocking-finding count: 2, both fixed.  
Current blocking-finding count: **1**.
