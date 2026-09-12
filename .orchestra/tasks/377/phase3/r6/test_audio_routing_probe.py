from dataclasses import replace
import unittest

from audio_routing_probe import MAX_BUFFER_MS, fixture, request, run_probe


class AudioRoutingProbeTest(unittest.TestCase):
    def test_normal_combat_is_cached_deterministic_and_provider_offline(self):
        router, provider, _, server = fixture()
        first = server.submit(request("combat-a", event_key="combat.hit", normal_combat=True), 0)
        duplicate = server.submit(request("combat-a", event_key="combat.hit", normal_combat=True), 1)
        second = server.submit(request("combat-b", event_key="combat.hit", normal_combat=True), 2)
        self.assertEqual("cache", first.source)
        self.assertEqual(first.asset_id, duplicate.asset_id)
        self.assertNotEqual(first.asset_id, second.asset_id)
        self.assertEqual([], provider.started)
        snapshot = router.cache.snapshot()
        self.assertEqual(first.asset_id, snapshot["assignments"]["line:combat-a:1"])

    def test_voice_routes_are_explicit_and_uncleared_voice_falls_back(self):
        _, provider, _, server = fixture()
        server.grant_lease("table-a", 0)
        severin = server.submit(request("story"), 0)
        blocked = server.submit(request("npc", speaker_role="npc", entity_id="npc:blocked", archetype="guard"), 1)
        missing = server.submit(request("unknown", speaker_role="npc", entity_id="npc:unknown"), 2)
        self.assertEqual("narrator.severin", severin.voice_key)
        self.assertEqual("npc.guard", blocked.voice_key)
        self.assertEqual("text_only", missing.source)
        self.assertEqual(2, len(provider.started))

    def test_tts_without_audible_lease_does_not_start_provider(self):
        _, provider, _, server = fixture()
        line = server.submit(request("no-leader"), 0)
        self.assertEqual("pending", line.status)
        self.assertEqual([], provider.started)

    def test_undisclosed_text_never_reaches_provider(self):
        _, provider, _, server = fixture()
        with self.assertRaisesRegex(ValueError, "undisclosed_text"):
            server.submit(request("secret", disclosed=False, text="GM_ONLY_CANARY_377_R6"), 0)
        self.assertEqual([], provider.started)

    def test_missing_text_event_identity_never_reaches_provider(self):
        _, provider, _, server = fixture()
        invalid = replace(request("missing-id"), text_event_id="")
        with self.assertRaisesRegex(ValueError, "undisclosed_text"):
            server.submit(invalid, 0)
        self.assertEqual([], provider.started)

    def test_cancel_closes_provider_stops_buffers_and_drops_late_chunks(self):
        _, provider, players, server = fixture()
        lease = server.grant_lease("table-a", 0)
        line = server.submit(request("story"), 10)
        old_context = line.context_id
        server.provider_chunk(line.line_id, old_context, 1, 120, 80)
        self.assertLessEqual(players[0].buffers[(line.line_id, old_context)], MAX_BUFFER_MS)
        server.cancel(line.line_id, old_context, 90)
        server.provider_chunk(line.line_id, old_context, 2, 80, 95)
        self.assertIn(old_context, provider.closed_contexts)
        self.assertNotIn((line.line_id, old_context), players[0].buffers)
        self.assertEqual(1, server.provider_late_drops)
        self.assertEqual(0, server.kernel_calls)
        self.assertEqual(1, lease.generation)
        stale = replace(
            line,
            line_id="line:stale",
            context_id="ctx:stale",
            status="ready",
            audio_fence=0,
        )
        self.assertFalse(players[0].play("stale-fence", stale, lease.generation))
        self.assertEqual(1, players[0].dropped_stale_fence)

    def test_provider_failure_after_audio_interrupts_and_clears_browser(self):
        _, _, players, server = fixture()
        server.grant_lease("table-a", 0)
        line = server.submit(request("partial"), 0)
        server.provider_chunk(line.line_id, line.context_id, 1, 90, 50)
        self.assertEqual(90, players[0].buffers[(line.line_id, line.context_id)])
        server.provider_failure(line.line_id, "provider_busy", 60)
        self.assertEqual("interrupted", line.status)
        self.assertNotIn((line.line_id, line.context_id), players[0].buffers)
        self.assertEqual(0, server.kernel_calls)

    def test_one_leader_fences_stale_generation_and_dedupes_play(self):
        _, _, players, server = fixture()
        lease1 = server.grant_lease("table-a", 0)
        stale_line = server.submit(request("combat", event_key="combat.hit", normal_combat=True), 0)
        lease2 = server.grant_lease("scene-b", 100)
        self.assertFalse(players[0].play("stale", stale_line, lease1.generation))
        line = server.submit(request("fresh", event_key="combat.miss", normal_combat=True), 101)
        event_id = f"audio.play:{line.playback_attempt_id}"
        self.assertTrue(players[1].play(event_id, line, lease2.generation))
        self.assertFalse(players[1].play(event_id, line, lease2.generation))
        self.assertEqual(1, players[1].play_count)

    def test_player_allows_only_one_active_speech_line(self):
        _, _, players, server = fixture()
        lease = server.grant_lease("table-a", 0)
        first = server.submit(request("first", event_key="combat.hit", normal_combat=True), 0)
        second = server.submit(request("second", event_key="combat.miss", normal_combat=True), 1)
        self.assertTrue(players[0].play("play:first", first, lease.generation))
        self.assertFalse(players[0].play("play:second", second, lease.generation))
        self.assertEqual(1, players[0].dropped_busy_speech)
        players[0].stop(first.line_id, first.context_id)
        self.assertTrue(players[0].play("play:second", second, lease.generation))

    def test_lease_re_election_fences_music_and_sfx_and_restores_only_music_state(self):
        _, _, players, server = fixture()
        lease1 = server.grant_lease("table-a", 0)
        self.assertTrue(server.set_music_state("danger"))
        self.assertTrue(server.deliver_sfx("sfx:old"))
        old_fence = server.audio_fence
        lease2 = server.grant_lease("scene-b", 100)
        self.assertEqual("silence", players[0].music_state)
        self.assertEqual(set(), players[0].sfx_events)
        self.assertEqual("danger", players[1].music_state)
        self.assertEqual(set(), players[1].sfx_events)
        self.assertFalse(players[0].set_music("music:late", "boss", lease1.generation, old_fence))
        self.assertFalse(players[0].play_sfx("sfx:late", lease1.generation, old_fence))
        self.assertTrue(server.deliver_sfx("sfx:new"))
        self.assertEqual({"sfx:new"}, players[1].sfx_events)
        self.assertEqual(2, lease2.generation)

    def test_future_fence_media_waits_for_all_audio_control_without_overlap(self):
        _, _, players, server = fixture()
        lease = server.grant_lease("table-a", 0)
        player = players[0]
        old_speech = server.submit(request("old-speech", event_key="combat.hit", normal_combat=True), 0)
        self.assertTrue(player.play("speech:old", old_speech, lease.generation))
        self.assertTrue(server.set_music_state("danger"))
        self.assertTrue(server.deliver_sfx("sfx:old"))

        future_fence = player.audio_fence + 1
        new_speech = replace(
            server.submit(request("new-speech", event_key="combat.miss", normal_combat=True), 1),
            audio_fence=future_fence,
        )
        self.assertFalse(player.play("speech:new", new_speech, lease.generation))
        self.assertFalse(player.set_music("music:new", "boss", lease.generation, future_fence))
        self.assertFalse(player.play_sfx("sfx:new", lease.generation, future_fence))

        self.assertEqual((old_speech.line_id, old_speech.context_id), player.active_speech)
        self.assertEqual("danger", player.music_state)
        self.assertEqual({"sfx:old"}, player.sfx_events)
        self.assertNotIn("speech:new", player.applied_events)
        self.assertNotIn("music:new", player.applied_events)
        self.assertNotIn("sfx:new", player.applied_events)
        self.assertEqual(3, len(player.pending_media))

        self.assertTrue(player.apply_control(future_fence, "all_audio"))
        self.assertTrue(player.control_barrier_observations[-1]["old_cleared_before_drain"])
        self.assertEqual((new_speech.line_id, new_speech.context_id), player.active_speech)
        self.assertNotIn((old_speech.line_id, old_speech.context_id), player.buffers)
        self.assertEqual("boss", player.music_state)
        self.assertEqual({"sfx:new"}, player.sfx_events)
        self.assertEqual(0, len(player.pending_media))
        self.assertEqual(future_fence, player.audio_fence)

    def test_future_fence_buffer_is_bounded_and_overflow_requests_control_gap(self):
        _, _, players, server = fixture()
        lease = server.grant_lease("table-a", 0)
        player = players[0]
        self.assertTrue(server.set_music_state("danger"))
        future_fence = player.audio_fence + 1
        for index in range(16):
            self.assertFalse(player.play_sfx(f"sfx:future:{index}", lease.generation, future_fence))
        self.assertEqual(16, len(player.pending_media))
        self.assertFalse(player.play_sfx("sfx:overflow", lease.generation, future_fence))
        self.assertEqual(0, len(player.pending_media))
        self.assertEqual(1, player.control_gap_requests)
        self.assertEqual("danger", player.music_state)
        self.assertEqual(0, player.audio_fence)

    def test_metric_schema_rejects_plaintext_and_unkeyed_or_unknown_content_fields(self):
        _, _, _, server = fixture()
        server.grant_lease("table-a", 0)
        server.submit(request("metric-schema"), 0)
        for field in ("text", "text_sha256", "content_fingerprint"):
            with self.subTest(field=field):
                with self.assertRaisesRegex(ValueError, "telemetry_schema_rejected"):
                    server.record_metric({field: "forbidden"})
        missing_retention = dict(server.metrics[0])
        missing_retention.pop("retention_policy_id")
        with self.assertRaisesRegex(ValueError, "telemetry_required_missing"):
            server.record_metric(missing_retention)
        self.assertTrue(server.metrics_schema_valid())

    def test_audio_retry_and_provider_failure_never_replay_world(self):
        _, _, _, server = fixture()
        server.grant_lease("table-a", 0)
        line = server.submit(request("story"), 0)
        old_context = line.context_id
        server.cancel(line.line_id, old_context, 10)
        retried = server.retry_audio(line.line_id, 20)
        server.provider_failure(retried.line_id, "concurrent_limit_exceeded", 30)
        self.assertEqual(2, retried.attempt)
        self.assertIsNot(line, retried)
        self.assertEqual(old_context, line.context_id)
        self.assertNotEqual(old_context, retried.context_id)
        self.assertEqual("failed_text_only", retried.status)
        self.assertEqual(0, server.kernel_calls)

    def test_retry_waits_for_cancel_disposition_and_current_lease(self):
        _, provider, players, server = fixture()
        server.grant_lease("table-a", 0)
        line = server.submit(request("retry-gate"), 0)
        old_context = line.context_id
        server.cancel(line.line_id, old_context, 10)
        started_before = len(provider.started)
        server.cancel_fanout_complete.remove((line.line_id, old_context))
        with self.assertRaisesRegex(RuntimeError, "retry_waiting_for_audio_admission"):
            server.retry_audio(line.line_id, 20)
        self.assertEqual(started_before, len(provider.started))
        server.cancel_fanout_complete.add((line.line_id, old_context))
        server.current_lease = None
        players[0].lease = None
        with self.assertRaisesRegex(RuntimeError, "retry_waiting_for_audio_admission"):
            server.retry_audio(line.line_id, 30)
        self.assertEqual(started_before, len(provider.started))

    def test_complete_probe(self):
        result = run_probe()
        self.assertEqual("PASS", result["oracle"])
        self.assertTrue(result["cancel"]["provider_context_closed"])
        self.assertEqual(0, result["cancel"]["buffered_after_ms"])
        self.assertEqual(0, result["retry_failure"]["kernel_calls"])
        self.assertFalse(result["leader_replay"]["duplicate_play_accepted"])
        self.assertTrue(result["privacy_observability"]["text_absent"])
        self.assertTrue(result["privacy_observability"]["undisclosed_rejected"])
        self.assertTrue(result["privacy_observability"]["metrics_schema_valid"])
        self.assertEqual("interrupted", result["provider_failure_after_audio"]["status"])
        self.assertEqual(0, result["provider_failure_after_audio"]["buffered_after_ms"])
        self.assertEqual("silence", result["all_audible_lanes"]["old_leader_music_after_loss"])
        self.assertEqual("danger", result["all_audible_lanes"]["new_leader_music_snapshot"])
        self.assertFalse(result["all_audible_lanes"]["stale_music_accepted"])
        self.assertFalse(result["all_audible_lanes"]["stale_sfx_accepted"])
        self.assertEqual(3, result["control_barrier"]["future_media_buffered_before_control"])
        self.assertTrue(result["control_barrier"]["old_media_preserved_before_control"])
        self.assertFalse(result["control_barrier"]["new_media_started_before_control"])
        self.assertTrue(result["control_barrier"]["old_cleared_before_drain"])
        self.assertTrue(result["control_barrier"]["old_media_absent_after_control"])
        self.assertTrue(result["control_barrier"]["new_media_admitted_after_control"])


if __name__ == "__main__":
    unittest.main()
