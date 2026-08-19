import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from voicelink.exceptions import NodeNotAvailable
from voicelink.playback import AttemptState, PlaybackSession, QueueItem
from voicelink.player import Player, cancel_owned_tasks


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


def _bare_player() -> Player:
    player = Player.__new__(Player)
    player._playback = PlaybackSession()
    player._attempt_lock = asyncio.Lock()
    player._queue_lock = asyncio.Lock()
    player._watchdog_task = None
    player._exception_fallback_task = None
    player._recovery_task = None
    player._notify_tasks = set()
    player._desired_connected = True
    player._tearing_down = False
    player._had_started = False
    player._current = None
    player._current_item = None
    player._last_position = 0
    player._guild = SimpleNamespace(id=1, name="g", me=SimpleNamespace(voice=True))
    player._logger = SimpleNamespace(debug=lambda *a, **k: None, error=lambda *a, **k: None)
    player._playback_log = SimpleNamespace(log=lambda *a, **k: None, warning=lambda *a, **k: None)
    loop = asyncio.get_running_loop()
    player.client = SimpleNamespace(loop=loop)
    player._bot = player.client
    player._sync_current = lambda: None
    player._run_decision = AsyncMock()
    return player


class CancelOwnedTasksTests(unittest.IsolatedAsyncioTestCase):
    async def test_cleanup_from_watchdog_does_not_cancel_self(self):
        started = asyncio.Event()
        finished = asyncio.Event()
        host = SimpleNamespace(_watchdog_task=None, _exception_fallback_task=None)

        async def watchdog():
            started.set()
            await asyncio.sleep(0)
            owned = {
                "_watchdog_task": host._watchdog_task,
                "_exception_fallback_task": host._exception_fallback_task,
            }
            cleared, pending = cancel_owned_tasks(owned)
            self.assertEqual(pending, [])
            self.assertIs(host._watchdog_task, asyncio.current_task())
            for name in cleared:
                setattr(host, name, None)
            await asyncio.sleep(0)
            finished.set()

        host._watchdog_task = asyncio.create_task(watchdog())
        task = host._watchdog_task
        await asyncio.wait_for(started.wait(), timeout=1)
        await asyncio.wait_for(task, timeout=1)
        self.assertTrue(finished.is_set())
        self.assertTrue(task.done())
        self.assertIsNone(task.exception())

    async def test_cleanup_from_exception_fallback_cancels_watchdog_only(self):
        watchdog_cancelled = asyncio.Event()

        async def watchdog():
            try:
                await asyncio.sleep(60)
            except asyncio.CancelledError:
                watchdog_cancelled.set()
                raise

        async def fallback():
            await asyncio.sleep(0)
            owned = {
                "_watchdog_task": host._watchdog_task,
                "_exception_fallback_task": host._exception_fallback_task,
            }
            cleared, pending = cancel_owned_tasks(owned)
            for name in cleared:
                setattr(host, name, None)
            self.assertEqual(pending, [watchdog_task])
            await asyncio.gather(*pending, return_exceptions=True)

        host = SimpleNamespace(_watchdog_task=None, _exception_fallback_task=None)
        watchdog_task = asyncio.create_task(watchdog())
        host._watchdog_task = watchdog_task
        fallback_task = asyncio.create_task(fallback())
        host._exception_fallback_task = fallback_task
        await asyncio.wait_for(fallback_task, timeout=1)
        self.assertTrue(watchdog_cancelled.is_set())
        self.assertTrue(watchdog_task.done())
        self.assertTrue(watchdog_task.cancelled())
        self.assertFalse(fallback_task.cancelled())

    async def test_retry_supersedes_old_attempt_tasks(self):
        async def linger():
            try:
                await asyncio.sleep(60)
            except asyncio.CancelledError:
                raise

        watchdog = asyncio.create_task(linger())
        fallback = asyncio.create_task(linger())
        _, pending = cancel_owned_tasks(
            {"_watchdog_task": watchdog, "_exception_fallback_task": fallback}
        )
        await asyncio.gather(*pending, return_exceptions=True)
        self.assertTrue(watchdog.cancelled())
        self.assertTrue(fallback.cancelled())
        self.assertEqual(len(pending), 2)

    async def test_teardown_cancels_multiple_attempt_tasks(self):
        player = _bare_player()

        async def linger():
            try:
                await asyncio.sleep(60)
            except asyncio.CancelledError:
                raise

        player._watchdog_task = asyncio.create_task(linger())
        player._exception_fallback_task = asyncio.create_task(linger())
        player._recovery_task = asyncio.create_task(linger())
        cancelled = player._cancel_attempt_tasks_locked()
        await player._absorb_cancelled(cancelled)
        recovery = player._recovery_task
        player._recovery_task = None
        _, pending = cancel_owned_tasks({"_recovery_task": recovery})
        await player._absorb_cancelled(pending)
        self.assertIsNone(player._watchdog_task)
        self.assertIsNone(player._exception_fallback_task)
        self.assertTrue(cancelled[0].cancelled())
        self.assertTrue(cancelled[1].cancelled())
        self.assertTrue(recovery.cancelled())

    async def test_no_surviving_obsolete_tasks_after_skip_cleanup(self):
        player = _bare_player()

        async def linger():
            try:
                await asyncio.sleep(60)
            except asyncio.CancelledError:
                raise

        player._watchdog_task = asyncio.create_task(linger())
        player._exception_fallback_task = asyncio.create_task(linger())
        cancelled = player._cancel_attempt_tasks_locked()
        await player._absorb_cancelled(cancelled)
        self.assertIsNone(player._watchdog_task)
        self.assertIsNone(player._exception_fallback_task)
        self.assertTrue(all(task.done() for task in cancelled))
        self.assertTrue(all(task.cancelled() for task in cancelled))


class PlaybackWorkerCleanupTests(unittest.IsolatedAsyncioTestCase):
    async def test_watchdog_worker_cleanup_from_self(self):
        player = _bare_player()
        item = QueueItem(1, FakeTrack("enc-a"))
        attempt = player._playback.create_attempt(item)
        player._playback.mark_play_in_flight()
        player._playback.arm_after_play_success()
        with patch("voicelink.player.TRACK_START_TIMEOUT", 0):
            task = asyncio.create_task(
                player._watchdog_worker(attempt.attempt_id, item.item_id, attempt.play_seq)
            )
            player._watchdog_task = task
            await asyncio.wait_for(task, timeout=1)
        self.assertIsNone(player._watchdog_task)
        self.assertFalse(task.cancelled())
        player._run_decision.assert_awaited()

    async def test_exception_fallback_worker_cleanup_from_self(self):
        player = _bare_player()
        item = QueueItem(1, FakeTrack("enc-a"))
        attempt = player._playback.create_attempt(item)
        with patch("voicelink.player.EXCEPTION_END_FALLBACK", 0):
            task = asyncio.create_task(
                player._exception_fallback_worker(attempt.attempt_id, item.item_id)
            )
            player._exception_fallback_task = task
            await asyncio.wait_for(task, timeout=1)
        self.assertIsNone(player._exception_fallback_task)
        self.assertFalse(task.cancelled())
        player._run_decision.assert_awaited()

    async def test_watchdog_self_cleanup_does_not_recurse(self):
        player = _bare_player()
        item = QueueItem(1, FakeTrack("enc-a"))
        attempt = player._playback.create_attempt(item)
        player._playback.mark_play_in_flight()
        player._playback.arm_after_play_success()
        with patch("voicelink.player.TRACK_START_TIMEOUT", 0):
            task = asyncio.create_task(
                player._watchdog_worker(attempt.attempt_id, item.item_id, attempt.play_seq)
            )
            player._watchdog_task = task
            await asyncio.wait_for(task, timeout=1)
        self.assertIsNone(task.exception())

    async def test_issue_play_node_unavailable_does_not_queue_advance(self):
        player = _bare_player()
        item = QueueItem(1, FakeTrack("enc-a"))
        player._playback.create_attempt(item)

        async def boom(*args, **kwargs):
            raise NodeNotAvailable("The node 'test' is unavailable.")

        player.play = boom
        await player._issue_play()
        self.assertEqual(player._playback.current_item.item_id, 1)
        self.assertEqual(player._playback.attempt.state, AttemptState.RECOVERING)
        self.assertEqual(player._playback.side_effects, [])
        self.assertEqual(item.retry_count, 0)
        player._run_decision.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
