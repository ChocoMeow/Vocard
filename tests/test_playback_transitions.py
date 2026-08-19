import unittest
from types import SimpleNamespace

from voicelink.enums import LoopType
from voicelink.exceptions import NodeException
from voicelink.playback import (
    AttemptIntent,
    AttemptState,
    EventDisposition,
    PendingEventKind,
    PlaybackAdvanceReason,
    PlaybackSession,
    QueueItem,
    TerminalSource,
    encoded_from_payload,
    exception_log_fields,
    format_playback_log_fields,
)
from voicelink.queue import FairQueue, Queue


class FakeTrack:
    def __init__(self, encoded, title="song", position=0, end_time=None, requester=None, uri=None):
        self.track_id = encoded
        self.title = title
        self.position = position
        self.end_time = end_time
        self.requester = requester
        self.uri = uri or f"https://example.test/{encoded}"
        self.author = "artist"
        self.data = {"track_id": encoded, "requester_id": getattr(requester, "id", 0)}


class FakeRequester:
    def __init__(self, bot=False, user_id=1):
        self.bot = bot
        self.id = user_id


class PlaybackTransitionTests(unittest.TestCase):
    def setUp(self):
        self.session = PlaybackSession()
        self.item_a = QueueItem(1, FakeTrack("enc-a", "A", position=60_000, end_time=180_000))
        self.item_b = QueueItem(2, FakeTrack("enc-b", "B"))
        self.item_c = QueueItem(3, FakeTrack("enc-c", "C"))

    def _start(self, item, encoded=None):
        attempt = self.session.create_attempt(item, start_pos=item.track.position or 0)
        self.session.mark_play_in_flight()
        self.assertTrue(self.session.validate_play_completion(attempt.play_seq, item.item_id, attempt.attempt_id))
        self.session.arm_after_play_success()
        self.session.apply_track_start(encoded or item.track.track_id)
        return attempt

    def test_encoded_payload_snapshot(self):
        self.assertEqual(encoded_from_payload({"track": {"encoded": "abc"}}), "abc")
        self.assertEqual(encoded_from_payload({"encodedTrack": "xyz"}), "xyz")

    def test_early_track_start_is_pending_then_applied(self):
        attempt = self.session.create_attempt(self.item_a)
        self.session.mark_play_in_flight()
        disposition = self.session.enqueue_or_apply(PendingEventKind.TRACK_START, encoded="enc-a")
        self.assertEqual(disposition, EventDisposition.PENDING)
        self.assertEqual(attempt.state, AttemptState.STARTING)
        pending = self.session.arm_after_play_success()
        self.assertEqual(len(pending), 1)
        self.assertTrue(self.session.apply_track_start(pending[0].encoded))
        self.assertEqual(attempt.state, AttemptState.STARTED)
        self.assertEqual(self.session.on_watchdog(), "IGNORE")

    def test_early_load_failed_processed_once_after_arm(self):
        self.session.create_attempt(self.item_a)
        self.session.mark_play_in_flight()
        self.session.enqueue_or_apply(PendingEventKind.TRACK_END, encoded="enc-a", reason="loadFailed")
        pending = self.session.arm_after_play_success()
        self.assertEqual(pending[0].reason, "loadFailed")
        decision = self.session.on_load_failed()
        self.assertEqual(decision, "RETRY")
        self.assertEqual(self.session.on_load_failed(), "IGNORE")
        retry = self.session.commit_retry()
        self.assertIsNotNone(retry)
        self.assertEqual(self.item_a.retry_count, 1)

    def test_patch_failure_discards_pending_start(self):
        attempt = self.session.create_attempt(self.item_a)
        self.session.mark_play_in_flight()
        self.session.enqueue_or_apply(PendingEventKind.TRACK_START, encoded="enc-a")
        discarded = self.session.fail_play_patch()
        self.assertEqual(len(discarded), 1)
        self.assertFalse(attempt.armed)
        self.assertEqual(attempt.state, AttemptState.STARTING)

    def test_stuck_versus_finished_one_terminal(self):
        self._start(self.item_a)
        self.assertEqual(self.session.on_stuck(), "RETRY")
        self.assertEqual(self.session.on_finished(), "IGNORE")
        self.assertEqual(self.item_a.retry_count, 0)
        self.session.commit_retry()
        self.assertEqual(self.item_a.retry_count, 1)

    def test_finished_then_stuck_no_retry(self):
        self._start(self.item_a)
        self.assertEqual(self.session.on_finished(), "ADVANCE")
        self.assertEqual(self.session.on_stuck(), "IGNORE")

    def test_skip_cancels_reservation_before_retry_attempt(self):
        self._start(self.item_a)
        self.assertEqual(self.session.on_load_failed(), "RETRY")
        self.assertIsNotNone(self.session.reservation)
        self.assertEqual(self.session.user_skip(), "ADVANCE")
        self.assertTrue(self.session.reservation.cancelled)
        self.assertIsNone(self.session.commit_retry())
        commit = self.session.commit_advance(PlaybackAdvanceReason.MANUAL_SKIP, self.item_b)
        self.assertEqual(commit.to_item.item_id, 2)
        self.assertEqual(len(self.session.queue_advance_logs), 1)

    def test_skip_after_retry_attempt_created(self):
        self._start(self.item_a)
        self.session.on_load_failed()
        retry = self.session.commit_retry()
        self.assertIsNotNone(retry)
        self.assertEqual(self.session.user_skip(), "ADVANCE")
        commit = self.session.commit_advance(PlaybackAdvanceReason.MANUAL_SKIP, self.item_b)
        self.assertEqual(commit.from_item.item_id, 1)
        self.assertEqual(len(self.session.queue_advance_logs), 1)

    def test_skip_while_retry_patch_in_flight(self):
        self._start(self.item_a)
        self.session.on_load_failed()
        retry = self.session.commit_retry()
        self.session.mark_play_in_flight()
        self.assertEqual(self.session.user_skip(), "ADVANCE")
        play_seq = retry.play_seq
        self.assertFalse(self.session.validate_play_completion(play_seq, retry.item_id, retry.attempt_id))
        commit = self.session.commit_advance(PlaybackAdvanceReason.MANUAL_SKIP, self.item_b)
        self.assertEqual(commit.to_item.item_id, 2)

    def test_skip_after_retry_track_start(self):
        self._start(self.item_a)
        self.session.on_load_failed()
        retry = self.session.commit_retry()
        self.session.mark_play_in_flight()
        self.session.arm_after_play_success()
        self.session.apply_track_start("enc-a")
        self.assertEqual(self.session.user_skip(), "STOP_THEN_ADVANCE")
        retry.intent = AttemptIntent.SKIP
        self.assertEqual(self.session.on_stopped(), "ADVANCE")

    def test_leave_during_recovery_no_advance(self):
        self._start(self.item_a)
        self.session.on_load_failed()
        self.session.commit_retry()
        self.session.mark_play_in_flight()
        self.session.user_leave()
        self.assertFalse(self.session.desired_connected)
        self.assertTrue(self.session.tearing_down)
        self.assertIsNone(self.session.commit_retry())
        self.assertEqual(len(self.session.queue_advance_logs), 0)

    def test_same_encoded_retry_late_events_do_not_double_advance(self):
        self._start(self.item_a)
        self.session.on_load_failed()
        retry = self.session.commit_retry()
        self.session.mark_play_in_flight()
        self.session.arm_after_play_success()
        self.assertEqual(self.session.on_finished(), "IGNORE")
        self.session.apply_track_start("enc-a")
        late = self.session.enqueue_or_apply(PendingEventKind.TRACK_END, encoded="enc-a", reason="replaced")
        self.assertIn(late, (EventDisposition.APPLY, EventDisposition.AMBIGUOUS, EventDisposition.IGNORE))
        self.assertEqual(self.session.on_replaced(), "IGNORE")
        self.assertEqual(len(self.session.queue_advance_logs), 0)
        self.assertEqual(retry.item_id, 1)

    def test_stale_play_completion_does_not_mutate(self):
        self._start(self.item_a)
        self.session.on_load_failed()
        retry = self.session.commit_retry()
        old_seq = retry.play_seq
        self.session.user_skip()
        self.session.commit_advance(PlaybackAdvanceReason.MANUAL_SKIP, self.item_b)
        b_attempt = self.session.attempt
        self.session.mark_play_in_flight()
        self.session.arm_after_play_success()
        self.assertFalse(self.session.validate_play_completion(old_seq, 1, retry.attempt_id))
        self.assertEqual(self.session.current_item.item_id, 2)
        self.assertEqual(self.session.attempt.attempt_id, b_attempt.attempt_id)

    def test_forceplay_replaced_predicate(self):
        self._start(self.item_a)
        self.session.begin_forceplay(self.item_b.item_id)
        self.assertEqual(self.session.on_replaced(), "FORCEPLAY_ADVANCE")
        self.session.commit_advance(PlaybackAdvanceReason.FORCEPLAY, self.item_b)
        self.assertEqual(self.session.current_item.item_id, 2)
        self.assertEqual(len(self.session.queue_advance_logs), 1)

    def test_generic_replaced_does_not_consume(self):
        self._start(self.item_a)
        self.assertEqual(self.session.on_replaced(), "IGNORE")
        self.assertEqual(len(self.session.queue_advance_logs), 0)
        self.assertEqual(self.session.current_item.item_id, 1)

    def test_retry_preserves_start_and_end(self):
        self._start(self.item_a)
        self.session.on_load_failed()
        self.session.commit_retry()
        self.assertEqual(self.session.retry_start_position(recovery_after_started=False), 60_000)
        self.assertEqual(self.session.intended_end_time(), 180_000)
        self.assertEqual(
            self.session.retry_start_position(recovery_after_started=True, last_position=12_345),
            12_345,
        )

    def test_history_once_per_logical_item(self):
        self.session.create_attempt(self.item_a)
        self.session.mark_play_in_flight()
        self.assertTrue(self.session.record_history_if_needed())
        self.assertFalse(self.session.record_history_if_needed())
        self.session.on_load_failed()
        self.session.commit_retry()
        self.assertFalse(self.session.record_history_if_needed())
        self.assertEqual(self.session.history_writes, [1])

    def test_separate_occurrences_have_independent_history(self):
        copy = QueueItem(9, FakeTrack("enc-a", "A"))
        self.session.create_attempt(self.item_a)
        self.session.record_history_if_needed()
        self.session.commit_advance(PlaybackAdvanceReason.FINISHED, copy)
        self.session.record_history_if_needed()
        self.assertEqual(self.session.history_writes, [1, 9])

    def test_queue_advance_side_effects_not_on_retry(self):
        self._start(self.item_a)
        self.session.on_load_failed()
        self.session.commit_retry()
        self.assertEqual(self.session.side_effects[-1], "RETRY")
        self.session.current_item.mark_exhausted()
        self.session.commit_advance(PlaybackAdvanceReason.LOAD_FAILED, self.item_b)
        self.assertEqual(self.session.side_effects[-1], "QUEUE_ADVANCE")
        self.assertEqual(len(self.session.queue_advance_logs), 1)

    def test_watchdog_suspended_during_disconnect(self):
        self.session.create_attempt(self.item_a)
        self.session.mark_play_in_flight()
        self.session.arm_after_play_success()
        self.session.watchdog_suspended = True
        self.assertEqual(self.session.on_watchdog(), "IGNORE")

    def test_node_unavailable_preserves_item_without_retry_or_advance(self):
        attempt = self.session.create_attempt(self.item_a)
        self.session.mark_play_in_flight()
        decision = self.session.on_node_unavailable()
        self.assertEqual(decision, "IGNORE")
        self.assertEqual(self.session.current_item.item_id, 1)
        self.assertEqual(self.item_a.retry_count, 0)
        self.assertFalse(self.item_a.fail_exhausted)
        self.assertEqual(attempt.state, AttemptState.RECOVERING)
        self.assertFalse(attempt.play_in_flight)
        self.assertEqual(self.session.side_effects, [])

    def test_play_rest_exhaustion_still_advances(self):
        self.session.create_attempt(self.item_a)
        first = self.session.decide_after_failure(TerminalSource.PLAY_REST)
        self.assertEqual(first, "RETRY")
        self.session.commit_retry()
        second = self.session.decide_after_failure(TerminalSource.PLAY_REST)
        self.assertEqual(second, "ADVANCE")
        self.assertTrue(self.item_a.fail_exhausted)

    def test_resume_starting_does_not_increment_retry(self):
        attempt = self.session.create_attempt(self.item_a)
        self.session.mark_play_in_flight()
        self.session.arm_after_play_success()
        self.assertEqual(attempt.state, AttemptState.STARTING)
        self.assertEqual(self.item_a.retry_count, 0)
        self.session.apply_track_start("enc-a")
        self.assertEqual(self.item_a.retry_count, 0)
        self.assertEqual(len(self.session.queue_advance_logs), 0)

    def test_adversarial_sequence(self):
        queue = [self.item_a, self.item_b, self.item_c]
        self._start(queue[0])
        self.session.apply_track_exception({"message": "boom"})
        self.session.watchdog_suspended = True
        self.assertEqual(self.session.on_watchdog(), "IGNORE")
        self.session.watchdog_suspended = False
        self.assertEqual(self.session.on_load_failed(), "RETRY")
        self.assertEqual(self.session.user_skip(), "ADVANCE")
        commit = self.session.commit_advance(PlaybackAdvanceReason.MANUAL_SKIP, queue[1])
        self.session.mark_play_in_flight()
        self.session.enqueue_or_apply(PendingEventKind.TRACK_START, encoded="enc-a")
        self.session.arm_after_play_success()
        self.session.apply_track_start("enc-b")
        self.assertEqual(self.session.on_replaced(), "IGNORE")
        self.assertFalse(self.session.validate_play_completion(1, 1, 1))
        self.assertEqual(commit.from_item.item_id, 1)
        self.assertEqual(self.session.current_item.item_id, 2)
        self.assertEqual(queue[2].item_id, 3)
        self.assertEqual(len(self.session.queue_advance_logs), 1)
        self.assertEqual(self.session.queue_advance_logs[0]["from_item"], 1)
        self.assertEqual(self.session.queue_advance_logs[0]["to_item"], 2)

    def test_retry_keeps_current_item_occupied(self):
        self._start(self.item_a)
        self.session.on_load_failed()
        self.session.commit_retry()
        self.assertIs(self.session.current_item, self.item_a)
        self.assertIsNotNone(self.session.attempt)
        self.assertEqual(self.session.attempt.state, AttemptState.STARTING)

    def test_ambiguous_terminal_does_not_consume_retry_item(self):
        self._start(self.item_a)
        self.session.on_load_failed()
        self.session.commit_retry()
        self.session.mark_play_in_flight()
        self.session.arm_after_play_success()
        disposition = self.session.enqueue_or_apply(
            PendingEventKind.TRACK_END, encoded="enc-a", reason="loadFailed"
        )
        self.assertEqual(disposition, EventDisposition.AMBIGUOUS)
        self.assertEqual(len(self.session.queue_advance_logs), 0)
        self.assertEqual(self.session.current_item.item_id, 1)

    def test_abandoned_map_is_capped(self):
        for i in range(40):
            item = QueueItem(i + 1, FakeTrack(f"e{i}"))
            self.session.create_attempt(item)
            self.session.remember_stale(item.item_id, i + 1)
        self.assertLessEqual(len(self.session.stale_ops), 32)

    def test_prune_stale_play_seq_none_and_empty(self):
        self.session.prune_stale(play_seq=5)
        self.assertEqual(self.session.stale_ops, {})
        self.session.remember_stale(10, 1)
        self.session.remember_stale(20, 2)
        self.session.prune_stale(play_seq=None)
        self.assertEqual(self.session.stale_ops, {10: 1, 20: 2})
        self.session.prune_stale(item_id=10)
        self.assertEqual(self.session.stale_ops, {20: 2})

    def test_prune_stale_removes_older_ops_without_mutating_while_iterating(self):
        self.session.remember_stale(1, 1)
        self.session.remember_stale(2, 3)
        self.session.remember_stale(3, 5)
        self.session.remember_stale(4, 8)
        self.session.prune_stale(play_seq=5)
        self.assertNotIn(1, self.session.stale_ops)
        self.assertNotIn(2, self.session.stale_ops)
        self.assertEqual(self.session.stale_ops[3], 5)
        self.assertEqual(self.session.stale_ops[4], 8)

    def test_loadfailed_retry_exhaustion_advances_once_and_prunes(self):
        self._start(self.item_a)
        self.assertEqual(self.session.on_load_failed(), "RETRY")
        retry = self.session.commit_retry()
        self.assertIsNotNone(retry)
        self.session.mark_play_in_flight()
        self.session.arm_after_play_success()
        self.session.apply_track_start("enc-a")
        self.assertEqual(self.session.on_load_failed(), "ADVANCE")
        self.assertTrue(self.item_a.fail_exhausted)
        self.assertEqual(self.item_a.retry_count, 1)

        self.session.remember_stale(99, 1)
        commit = self.session.commit_advance(PlaybackAdvanceReason.LOAD_FAILED, self.item_b)
        self.assertEqual(commit.from_item.item_id, 1)
        self.assertEqual(commit.to_item.item_id, 2)
        self.assertEqual(len(self.session.queue_advance_logs), 1)
        self.assertEqual(self.session.current_item.item_id, 2)

        empty = PlaybackSession()
        lone = QueueItem(1, FakeTrack("enc-a", "A"))
        empty.create_attempt(lone)
        empty.mark_play_in_flight()
        empty.arm_after_play_success()
        empty.apply_track_start("enc-a")
        self.assertEqual(empty.on_load_failed(), "RETRY")
        empty.commit_retry()
        empty.mark_play_in_flight()
        empty.arm_after_play_success()
        empty.apply_track_start("enc-a")
        self.assertEqual(empty.on_load_failed(), "ADVANCE")
        empty.remember_stale(50, 1)
        empty.remember_stale(51, 2)
        from_seq = empty.attempt.play_seq
        commit_empty = empty.commit_advance(PlaybackAdvanceReason.LOAD_FAILED, None)
        self.assertIsNone(commit_empty.to_item)
        self.assertEqual(len(empty.queue_advance_logs), 1)
        self.assertNotIn(50, empty.stale_ops)
        self.assertEqual(empty.stale_ops.get(51), 2)
        self.assertEqual(empty.stale_ops.get(1), from_seq)

    def test_node_exception_play_kind(self):
        play_err = NodeException("x", kind="PLAYER_PLAY")
        load_err = NodeException("y", kind="LOADTRACKS")
        self.assertTrue(play_err.is_play_patch)
        self.assertFalse(load_err.is_play_patch)

    def test_track_exception_log_fields_include_lavalink_details(self):
        self._start(self.item_a)
        self.session.apply_track_exception({
            "message": "Something went wrong",
            "severity": "common",
            "cause": "java.lang.RuntimeException: boom",
            "causeStackTrace": "line1\n" * 400,
        })
        record = [row for row in self.session.logs if row.get("event") == "TRACK_EXCEPTION"][-1]
        self.assertEqual(record["item_id"], 1)
        self.assertEqual(record["attempt_id"], 1)
        self.assertEqual(record["message"], "Something went wrong")
        self.assertEqual(record["severity"], "common")
        self.assertEqual(record["cause"], "java.lang.RuntimeException: boom")
        self.assertNotIn("causeStackTrace", record)


class ExceptionLogTests(unittest.TestCase):
    def test_missing_exception_fields_are_omitted(self):
        self.assertEqual(exception_log_fields(None), {})
        self.assertEqual(exception_log_fields({}), {})
        self.assertEqual(exception_log_fields({"message": None, "severity": "", "cause": "  "}), {})

    def test_nested_exception_and_truncation(self):
        fields = exception_log_fields({
            "exception": {
                "message": "x" * 300,
                "severity": "fault",
                "cause": "y" * 50,
            }
        })
        self.assertEqual(fields["severity"], "fault")
        self.assertEqual(fields["cause"], "y" * 50)
        self.assertTrue(fields["message"].endswith("..."))
        self.assertLessEqual(len(fields["message"]), 240)

    def test_example_track_exception_log_format(self):
        line = format_playback_log_fields({
            "item_id": 3,
            "attempt_id": 5,
            "node": "DEFAULT",
            "source": "youtube",
            "track": "Bi Bi Bi Bizamet",
            "message": "This content isn’t available.",
            "severity": "common",
            "cause": "com.sedmelluq.discord.lavaplayer.tools.FriendlyException",
        })
        self.assertTrue(line.startswith("item_id=3 attempt_id=5 node=DEFAULT source=youtube"))
        self.assertIn('track="Bi Bi Bi Bizamet"', line)
        self.assertIn('message="This content isn’t available."', line)
        self.assertIn('severity="common"', line)
        self.assertIn("cause=", line)


class QueueWrapperTests(unittest.TestCase):
    def setUp(self):
        self.queue = Queue(100, True, lambda *a: "full")
        self.a = FakeTrack("enc-a", "A")
        self.b = FakeTrack("enc-b", "B")
        self.x1 = FakeTrack("enc-x", "X", uri="https://x/1")
        self.x2 = FakeTrack("enc-x", "X", uri="https://x/1")

    def test_public_helpers_return_track_not_queueitem(self):
        self.queue.put(self.a)
        self.queue.put(self.b)
        current = self.queue.get()
        self.assertIsInstance(current, FakeTrack)
        self.assertTrue(all(isinstance(t, FakeTrack) for t in self.queue.tracks()))
        self.assertTrue(all(isinstance(t, FakeTrack) for t in self.queue.history(incTrack=True)))
        self.assertTrue(all(isinstance(row, dict) for row in self.queue.session_track_data()))
        self.assertIn("trackId", self.queue.ipc_track_payloads()[0])

    def test_duplicate_identical_songs_have_independent_retry(self):
        self.queue.put(self.x1)
        self.queue.put(self.x2)
        first = self.queue.get_item()
        second = self.queue.get_item()
        first.mark_retry()
        first.mark_exhausted()
        self.assertNotEqual(first.item_id, second.item_id)
        self.assertTrue(second.can_retry())
        self.assertFalse(first.can_retry())

    def test_track_loop_success_mints_new_item_id(self):
        self.queue.put(self.a)
        first = self.queue.get_item()
        old_id = first.item_id
        self.queue._repeat.set_mode(LoopType.TRACK)
        again = self.queue.get_item()
        self.assertIs(again.track, first.track)
        self.assertNotEqual(again.item_id, old_id)
        self.assertEqual(again.retry_count, 0)

    def test_fail_exhausted_track_loop_escapes(self):
        self.queue.put(self.a)
        self.queue.put(self.b)
        current = self.queue.get_item()
        current.mark_exhausted()
        self.queue._repeat.set_mode(LoopType.TRACK)
        nxt = self.queue.get_item(force_next=True, skip_exhausted=True)
        self.assertEqual(nxt.track.title, "B")

    def test_successful_queue_wrap_unchanged(self):
        self.queue.put(self.a)
        self.queue.put(self.b)
        self.queue.get()
        self.queue.get()
        self.queue._repeat.set_mode(LoopType.QUEUE)
        wrapped = self.queue.get()
        self.assertEqual(wrapped.title, "A")

    def test_fairqueue_uses_track_requester(self):
        fq = FairQueue(100, True, lambda *a: "full")
        r1 = FakeRequester(user_id=1)
        r2 = FakeRequester(user_id=2)
        fq.put(FakeTrack("a", requester=r1))
        fq.put(FakeTrack("b", requester=r2))
        fq.put(FakeTrack("c", requester=r1))
        for track in fq.tracks(incTrack=True):
            self.assertIsInstance(track, FakeTrack)
        self.assertTrue(len(fq._queue) >= 1)

    def test_caller_loop_modes_are_independent(self):
        skip_queue = Queue(10, True, lambda *a: "full")
        skip_queue.put(self.a)
        skip_queue.put(self.b)
        skip_queue._repeat.set_mode(LoopType.TRACK)
        skip_queue._repeat.set_mode(LoopType.OFF)
        self.assertEqual(skip_queue._repeat.mode, LoopType.OFF)

        dropdown = Queue(10, True, lambda *a: "full")
        dropdown.put(self.a)
        dropdown.put(self.b)
        dropdown.get()
        dropdown._repeat.set_mode(LoopType.TRACK)
        dropdown.skipto(1)
        self.assertEqual(dropdown._repeat.mode, LoopType.TRACK)

    def test_caller_track_loop_order_in_sources(self):
        from pathlib import Path

        root = Path(__file__).resolve().parents[1]
        basic = (root / "cogs" / "basic.py").read_text(encoding="utf-8")
        controller = (root / "voicelink" / "views" / "controller.py").read_text(encoding="utf-8")
        ipc = (root / "voicelink" / "ipc" / "methods.py").read_text(encoding="utf-8")

        skip_src = basic[basic.find("async def skip"): basic.find("async def back")]
        self.assertLess(skip_src.find("set_repeat"), skip_src.find("await player.stop()"))

        back_src = basic[basic.find("async def back"): basic.find("async def seek")]
        self.assertGreater(back_src.rfind("set_repeat"), back_src.find("await player.stop()"))

        force_src = basic[basic.find("async def forceplay"): basic.find("async def pause")]
        self.assertLess(force_src.find("set_repeat"), force_src.find("AttemptIntent.FORCEPLAY"))

        tracks_src = controller[controller.find("class Tracks"): controller.find("class Effects")]
        self.assertIn("prepare_user_reselect", tracks_src)
        self.assertIn("await self.player.stop()", tracks_src)
        self.assertNotIn("set_repeat", tracks_src)

        skip_ipc = ipc[ipc.find("async def skipTo"): ipc.find("async def backTo")]
        self.assertLess(skip_ipc.find("set_repeat"), skip_ipc.find("await player.stop()"))
        back_ipc = ipc[ipc.find("async def backTo"): ipc.find("async def moveTrack")]
        self.assertNotIn("set_repeat", back_ipc)


class EventSnapshotTests(unittest.IsolatedAsyncioTestCase):
    async def test_event_objects_snapshot_track(self):
        from voicelink.events import TrackEndEvent, TrackStartEvent, TrackExceptionEvent

        track = FakeTrack("enc-a", "A")
        player = SimpleNamespace(_current=track, _ending_track=track)
        start = TrackStartEvent({"type": "TrackStartEvent", "track": {"encoded": "enc-a"}}, player)
        self.assertIs(start.track, track)
        player._current = FakeTrack("enc-b", "B")
        self.assertEqual(start.track.title, "A")

        player._current = track
        end = TrackEndEvent({"reason": "finished", "track": {"encoded": "enc-a"}}, player)
        player._current = None
        self.assertEqual(end.track.title, "A")
        self.assertEqual(end.reason, "finished")

        from voicelink.events import YT_CONTENT_UNAVAILABLE, is_youtube_content_unavailable

        exc = TrackExceptionEvent(
            {"exception": {"message": YT_CONTENT_UNAVAILABLE, "severity": "common", "cause": ""}},
            player,
        )
        self.assertEqual(exc.exception["message"], YT_CONTENT_UNAVAILABLE)
        self.assertTrue(is_youtube_content_unavailable({
            "exception": {"message": YT_CONTENT_UNAVAILABLE}
        }))
        self.assertFalse(is_youtube_content_unavailable({
            "exception": {"message": "other"}
        }))

        flagged = []

        class FakeRatelimit:
            async def flag_active_token(self):
                flagged.append(True)

        from voicelink.player import Player

        fake = SimpleNamespace(
            _node=SimpleNamespace(yt_ratelimit=FakeRatelimit()),
            _current=track,
            _ending_track=track,
            _bot=SimpleNamespace(dispatch=lambda *a, **k: None),
            guild=SimpleNamespace(name="g", id=1),
            _logger=SimpleNamespace(debug=lambda *a, **k: None),
            handle_track_start=None,
        )

        async def _noop_start(*args, **kwargs):
            return None

        fake.handle_track_start = _noop_start
        await Player._dispatch_event(fake, {
            "type": "TrackExceptionEvent",
            "exception": {"message": YT_CONTENT_UNAVAILABLE, "severity": "common", "cause": ""},
        })
        self.assertEqual(flagged, [True])


if __name__ == "__main__":
    unittest.main()
