import asyncio
import logging
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from discord.errors import Forbidden, HTTPException

from voicelink.playback import NotifySnapshot, PlaybackAdvanceReason, PlaybackSession, QueueItem
from voicelink.player import Player


class FakeTrack:
    def __init__(self, encoded, title="song"):
        self.track_id = encoded
        self.title = title
        self.position = 0
        self.end_time = None
        self.requester = None
        self.uri = f"https://example.test/{encoded}"
        self.author = "artist"


class FakeQueue:
    def __init__(self, nxt=None):
        self._next = nxt
        self._repeat = SimpleNamespace(mode=None)
        self.is_empty = nxt is None
        self._position = 0

    def get_item(self, force_next=False, skip_exhausted=False):
        item = self._next
        self._next = None
        self.is_empty = True
        return item


class DummyResponse:
    def __init__(self, status=403, reason="Forbidden"):
        self.status = status
        self.reason = reason
        self.headers = {}


def _notify_player(channel=None, channel_id=99):
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
    player._paused = False
    player._updating = False
    player._current = None
    player._current_item = None
    player._last_position = 0
    player._guild = SimpleNamespace(id=1, name="g", me=SimpleNamespace(voice=True))
    player._logger = SimpleNamespace(debug=lambda *a, **k: None, error=lambda *a, **k: None)
    player._playback_log = SimpleNamespace(log=lambda *a, **k: None, warning=lambda *a, **k: None)
    player.settings = {}
    player.channel = SimpleNamespace(id=1)
    player.context = SimpleNamespace(channel=SimpleNamespace(id=channel_id, send=AsyncMock()))
    player.logs = []

    def _log(event, *, level=logging.INFO, **fields):
        player.logs.append((event, level, fields))
        player._playback.log(event, **fields)

    player._log_playback = _log
    player.get_msg = lambda key: (
        "Couldn't play **{0}**. Skipping to the next track."
        if key == "player.playback.loadFailedSkip"
        else "Couldn't play **{0}**."
    )

    def _sync():
        player._playback.desired_connected = player._desired_connected
        player._playback.tearing_down = player._tearing_down
        player._current_item = player._playback.current_item
        player._current = player._current_item.track if player._current_item else None

    player._sync_current = _sync
    player._after_new_item = AsyncMock()
    player._issue_play = AsyncMock()
    player.queue = FakeQueue()

    text_channel = channel or SimpleNamespace(id=channel_id, send=AsyncMock())
    loop = asyncio.get_running_loop()
    player.client = SimpleNamespace(loop=loop, get_channel=lambda cid: text_channel if cid == text_channel.id else None)
    player._bot = player.client
    player._text_channel = text_channel
    return player


def _snapshot(item, has_next=False, channel_id=99):
    return NotifySnapshot(
        item_id=item.item_id,
        title=item.track.title,
        reason=str(PlaybackAdvanceReason.LOAD_FAILED),
        retry_count=item.retry_count,
        has_next=has_next,
        channel_id=channel_id,
        guild_id=1,
    )


def _prepare_exhausted(player, item, next_item=None):
    player._playback.create_attempt(item)
    player._playback.mark_play_in_flight()
    player._playback.arm_after_play_success()
    player._playback.apply_track_start(item.track.track_id)
    player._playback.on_load_failed()
    player._playback.commit_retry()
    player._playback.mark_play_in_flight()
    player._playback.arm_after_play_success()
    player._playback.apply_track_start(item.track.track_id)
    player._playback.on_load_failed()
    player.queue = FakeQueue(next_item)
    player._sync_current()


class PlaybackNotificationDeliveryTests(unittest.IsolatedAsyncioTestCase):
    async def test_retryable_failure_does_not_send(self):
        player = _notify_player()
        item = QueueItem(1, FakeTrack("enc-a", "Stateside"))
        player._playback.create_attempt(item)
        player._playback.mark_play_in_flight()
        player._playback.arm_after_play_success()
        player._playback.apply_track_start("enc-a")
        self.assertEqual(player._playback.on_load_failed(), "RETRY")
        player._schedule_playback_failure_notification(player._playback.snapshot_notify(PlaybackAdvanceReason.LOAD_FAILED))
        await asyncio.sleep(0)
        player._text_channel.send.assert_not_awaited()
        self.assertEqual(player.logs, [])

    async def test_exhausted_failure_sends_once(self):
        player = _notify_player()
        item = QueueItem(1, FakeTrack("enc-a", "Stateside"))
        _prepare_exhausted(player, item, QueueItem(2, FakeTrack("enc-b", "Next")))
        await player._commit_and_play(PlaybackAdvanceReason.LOAD_FAILED, skip_exhausted=True)
        await asyncio.sleep(0)
        self.assertEqual(player._text_channel.send.await_count, 1)
        content = player._text_channel.send.await_args.args[0]
        self.assertEqual(content, "Couldn't play **Stateside**. Skipping to the next track.")
        self.assertEqual(player._text_channel.send.await_args.kwargs.get("delete_after"), 10)
        self.assertTrue(any(event == "PLAYBACK_NOTIFICATION_SENT" for event, _, _ in player.logs))

    async def test_exhausted_failure_with_next_item_starts_once(self):
        player = _notify_player()
        item = QueueItem(1, FakeTrack("enc-a", "A"))
        nxt = QueueItem(2, FakeTrack("enc-b", "B"))
        _prepare_exhausted(player, item, nxt)
        await player._commit_and_play(PlaybackAdvanceReason.LOAD_FAILED, skip_exhausted=True)
        await asyncio.sleep(0)
        self.assertEqual(player._text_channel.send.await_count, 1)
        player._issue_play.assert_awaited_once()
        self.assertEqual(player._current_item.item_id, 2)
        self.assertEqual(player._playback.side_effects.count("QUEUE_ADVANCE"), 1)

    async def test_exhausted_failure_empty_queue_does_not_issue_play(self):
        player = _notify_player()
        item = QueueItem(1, FakeTrack("enc-a", "A"))
        _prepare_exhausted(player, item, None)
        await player._commit_and_play(PlaybackAdvanceReason.LOAD_FAILED, skip_exhausted=True)
        await asyncio.sleep(0)
        self.assertEqual(player._text_channel.send.await_count, 1)
        content = player._text_channel.send.await_args.args[0]
        self.assertEqual(content, "Couldn't play **A**.")
        player._issue_play.assert_not_awaited()
        self.assertIsNone(player._current_item)
        self.assertEqual(player._playback.side_effects.count("QUEUE_ADVANCE"), 1)

    async def test_stale_duplicate_does_not_send_second_notification(self):
        player = _notify_player()
        item = QueueItem(1, FakeTrack("enc-a", "A"))
        nxt = QueueItem(2, FakeTrack("enc-b", "B"))
        _prepare_exhausted(player, item, nxt)
        await player._commit_and_play(PlaybackAdvanceReason.LOAD_FAILED, skip_exhausted=True)
        await asyncio.sleep(0)
        player._schedule_playback_failure_notification(
            player._playback.snapshot_notify(PlaybackAdvanceReason.LOAD_FAILED, has_next=True)
        )
        await asyncio.sleep(0)
        self.assertEqual(player._text_channel.send.await_count, 1)

    async def test_manual_skip_does_not_send(self):
        player = _notify_player()
        item = QueueItem(1, FakeTrack("enc-a", "A"))
        nxt = QueueItem(2, FakeTrack("enc-b", "B"))
        player._playback.create_attempt(item)
        player.queue = FakeQueue(nxt)
        await player._commit_and_play(PlaybackAdvanceReason.MANUAL_SKIP)
        await asyncio.sleep(0)
        player._text_channel.send.assert_not_awaited()
        player._issue_play.assert_awaited_once()

    async def test_forceplay_does_not_send(self):
        player = _notify_player()
        item = QueueItem(1, FakeTrack("enc-a", "A"))
        nxt = QueueItem(2, FakeTrack("enc-b", "B"))
        player._playback.create_attempt(item)
        player.queue = FakeQueue(nxt)
        await player._commit_and_play(PlaybackAdvanceReason.FORCEPLAY)
        await asyncio.sleep(0)
        player._text_channel.send.assert_not_awaited()
        player._issue_play.assert_awaited_once()

    async def test_node_unavailable_does_not_send(self):
        player = _notify_player()
        item = QueueItem(1, FakeTrack("enc-a", "A"))
        player._playback.create_attempt(item)
        self.assertEqual(player._playback.on_node_unavailable(), "IGNORE")
        player._schedule_playback_failure_notification(
            player._playback.snapshot_notify(PlaybackAdvanceReason.LOAD_FAILED)
        )
        await asyncio.sleep(0)
        player._text_channel.send.assert_not_awaited()
        player._issue_play.assert_not_awaited()

    async def test_forbidden_send_does_not_block_next_item(self):
        player = _notify_player()
        player._text_channel.send = AsyncMock(
            side_effect=Forbidden(DummyResponse(), {"message": "Missing Permissions"})
        )
        item = QueueItem(1, FakeTrack("enc-a", "A"))
        nxt = QueueItem(2, FakeTrack("enc-b", "B"))
        _prepare_exhausted(player, item, nxt)
        await player._commit_and_play(PlaybackAdvanceReason.LOAD_FAILED, skip_exhausted=True)
        await asyncio.sleep(0)
        player._issue_play.assert_awaited_once()
        self.assertEqual(player._current_item.item_id, 2)
        failed = [fields for event, _, fields in player.logs if event == "PLAYBACK_NOTIFICATION_FAILED"]
        self.assertEqual(len(failed), 1)
        self.assertEqual(failed[0]["item_id"], 1)
        self.assertEqual(failed[0]["channel_id"], 99)
        self.assertIn("Forbidden", failed[0]["error"])

    async def test_http_exception_does_not_block_next_item(self):
        player = _notify_player()
        player._text_channel.send = AsyncMock(
            side_effect=HTTPException(DummyResponse(status=500, reason="Internal Server Error"), "boom")
        )
        item = QueueItem(1, FakeTrack("enc-a", "A"))
        nxt = QueueItem(2, FakeTrack("enc-b", "B"))
        _prepare_exhausted(player, item, nxt)
        await player._commit_and_play(PlaybackAdvanceReason.LOAD_FAILED, skip_exhausted=True)
        await asyncio.sleep(0)
        player._issue_play.assert_awaited_once()
        failed = [fields for event, _, fields in player.logs if event == "PLAYBACK_NOTIFICATION_FAILED"]
        self.assertEqual(len(failed), 1)
        self.assertIn("HTTPException", failed[0]["error"])

    async def test_missing_channel_logs_useful_warning(self):
        player = _notify_player()
        player.client.get_channel = lambda cid: None
        player._bot = player.client
        item = QueueItem(1, FakeTrack("enc-a", "A"))
        await player._notify_playback_failure(_snapshot(item, channel_id=123))
        failed = [fields for event, _, fields in player.logs if event == "PLAYBACK_NOTIFICATION_FAILED"]
        self.assertEqual(len(failed), 1)
        self.assertEqual(failed[0]["channel_id"], 123)
        self.assertEqual(failed[0]["error"], "destination channel unavailable")
        player._issue_play.assert_not_awaited()

    async def test_missing_channel_id_logs_useful_warning(self):
        player = _notify_player()
        item = QueueItem(1, FakeTrack("enc-a", "A"))
        await player._notify_playback_failure(_snapshot(item, channel_id=None))
        failed = [fields for event, _, fields in player.logs if event == "PLAYBACK_NOTIFICATION_FAILED"]
        self.assertEqual(failed[0]["error"], "destination channel unavailable")

    async def test_does_not_use_context_send(self):
        player = _notify_player()
        player.context.send = AsyncMock()
        item = QueueItem(1, FakeTrack("enc-a", "A"))
        nxt = QueueItem(2, FakeTrack("enc-b", "B"))
        _prepare_exhausted(player, item, nxt)
        await player._commit_and_play(PlaybackAdvanceReason.LOAD_FAILED, skip_exhausted=True)
        await asyncio.sleep(0)
        player.context.send.assert_not_awaited()
        player._text_channel.send.assert_awaited()

    async def test_teardown_cancels_pending_notification(self):
        started = asyncio.Event()
        release = asyncio.Event()

        async def slow_send(*args, **kwargs):
            started.set()
            await release.wait()

        player = _notify_player()
        player._text_channel.send = slow_send
        item = QueueItem(1, FakeTrack("enc-a", "A"))
        task = asyncio.create_task(player._notify_playback_failure(_snapshot(item)))
        player._notify_tasks.add(task)
        await asyncio.wait_for(started.wait(), timeout=1)
        await player._cancel_pending_notifications()
        self.assertTrue(task.done())
        self.assertEqual(player._notify_tasks, set())
        player._issue_play.assert_not_awaited()
        self.assertFalse(player._tearing_down)
        release.set()

    async def test_controller_send_uses_text_channel_not_context(self):
        player = _notify_player()
        player.context.send = AsyncMock(side_effect=AssertionError("expired interaction must not be used"))
        message = SimpleNamespace(id=55)
        player._text_channel.send = AsyncMock(return_value=message)
        embed = SimpleNamespace()
        view = SimpleNamespace()
        result = await player._send_controller_message(embed, view)
        self.assertIs(result, message)
        player.context.send.assert_not_awaited()
        player._text_channel.send.assert_awaited_once_with(embed=embed, view=view)

    async def test_new_controller_does_not_use_context_send(self):
        player = _notify_player()
        player.settings = {"controller": True}
        player.controller = None
        player.context.send = AsyncMock(side_effect=AssertionError("expired interaction must not be used"))
        player.build_embed = lambda current: SimpleNamespace()
        player._text_channel.send = AsyncMock(return_value=SimpleNamespace(id=7))
        with patch("voicelink.player.InteractiveController", return_value=SimpleNamespace()):
            await player.invoke_controller()
        player.context.send.assert_not_awaited()
        player._text_channel.send.assert_awaited()
        self.assertEqual(player.controller.id, 7)

    async def test_controller_missing_channel_does_not_crash(self):
        player = _notify_player()
        player.client.get_channel = lambda cid: None
        player._bot = player.client
        player.context.send = AsyncMock()
        result = await player._send_controller_message(SimpleNamespace(), SimpleNamespace())
        self.assertIsNone(result)
        player.context.send.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
