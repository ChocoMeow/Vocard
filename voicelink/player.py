"""MIT License

Copyright (c) 2023 - present Vocard Development

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

from __future__ import annotations

import time, logging, asyncio

from math import ceil
from random import shuffle, choice
from typing import Any, Dict, List, Optional, Union, Tuple, TYPE_CHECKING

from discord import (
    Client,
    Guild,
    VoiceChannel,
    VoiceProtocol,
    Member,
    Message,
    PartialMessage,
    Interaction,
    errors,
    ChannelType
)

from discord.ext import commands

from . import events
from .config import Config
from .pool import Node, NodePool
from .objects import Track, Playlist
from .filters import Filter, Filters
from .enums import SearchType, LoopType, RequestMethod
from .events import VoicelinkEvent, TrackStartEvent, is_youtube_content_unavailable
from .exceptions import VoicelinkException, FilterInvalidArgument, TrackInvalidPosition, FilterTagAlreadyInUse, DuplicateTrack, NodeException, NodeNotAvailable
from .placeholders import PlayerPlaceholder
from .queue import Queue, QUEUE_TYPES
from .mongodb import MongoDBHandler
from .language import LangHandler
from .views import InteractiveController
from .utils import format_ms, dispatch_message
from .playback import (
    AttemptIntent,
    AttemptState,
    EventDisposition,
    EXCEPTION_END_FALLBACK,
    exception_log_fields,
    format_playback_log_fields,
    PendingEventKind,
    PlaybackAdvanceReason,
    PlaybackSession,
    safe_log_text,
    TerminalSource,
    TRACK_START_TIMEOUT,
)
from .resume import fetch_player_state, remote_encoded_track
from .health import health_store

if TYPE_CHECKING:
    from .ipc import IPCClient


def cancel_owned_tasks(
    owned: Dict[str, Optional[asyncio.Task]],
    *,
    current: Optional[asyncio.Task] = None,
) -> Tuple[Dict[str, None], List[asyncio.Task]]:
    """Detach owned task refs and cancel every task except the caller.

    Returns (cleared name map, tasks to await outside any lock). Never
    cancels ``asyncio.current_task()``, so attempt workers can clean up
    without cancelling themselves.
    """
    if current is None:
        current = asyncio.current_task()
    pending: List[asyncio.Task] = []
    cleared: Dict[str, None] = {name: None for name in owned}
    for task in owned.values():
        if task is None or task.done() or task is current:
            continue
        task.cancel()
        pending.append(task)
    return cleared, pending


async def connect_channel(ctx: Union[commands.Context, Interaction], channel: VoiceChannel = None):
    texts = await LangHandler.get_lang(ctx.guild.id, "voice.connection.noChannel", "voice.connection.noPermission")
    try:
        channel = channel or ctx.author.voice.channel if isinstance(ctx, commands.Context) else ctx.user.voice.channel
    except:
        raise VoicelinkException(texts[0])

    check = channel.permissions_for(ctx.guild.me)
    if check.connect == False or check.speak == False:
        raise VoicelinkException(texts[1])

    settings = await MongoDBHandler.get_settings(channel.guild.id)
    player: Player = await channel.connect(
        cls=Player(
            ctx.bot if isinstance(ctx, commands.Context) else ctx.client,
            channel, ctx, settings
        ))

    if player.volume != 100:
        await player.set_volume(player.volume)

    if player.is_ipc_connected:
        await player.send_ws({"op": "createPlayer", "memberIds": [str(member.id) for member in channel.members]})

    return player

class Player(VoiceProtocol):
    """The base player class for Voicelink.
       In order to initiate a player, you must pass it in as a cls when you connect to a channel.
       i.e: ```py
       await ctx.author.voice.channel.connect(cls=voicelink.Player)
       ```
    """

    def __call__(self, client: Client, channel: VoiceChannel):
        self.client: Client = client
        self.channel: VoiceChannel = channel

        return self

    def __init__(
        self, 
        client: Optional[Client] = None, 
        channel: Optional[VoiceChannel] = None, 
        ctx: Union[commands.Context, Interaction] = None,
        settings: dict[str, Any] = None
    ):
        self.client: Client = client
        self._bot: Client = client
        self._ipc_client: IPCClient = self._bot.ipc_client
        self._ipc_connection: bool = False
        
        self.context = ctx
        self.dj: Member = ctx.user if isinstance(ctx, Interaction) else ctx.author
        self.channel: VoiceChannel = channel
        self._guild = channel.guild if channel else None

        self.settings: dict = settings
        self.joinTime: float = round(time.time())
        self._volume: int = self.settings.get('volume', 100)
        self.queue: Queue = QUEUE_TYPES.get(self.settings.get("queue_type", "queue").lower())(
            self.settings.get("max_queue", Config().max_queue),
            self.settings.get("duplicate_track", True), self.get_msg
        )

        self._node = NodePool.get_node()
        self._current: Optional[Track] = None
        self._current_item = None
        self._filters: Filters = Filters()
        self._paused: bool = False
        self._is_connected: bool = False
        self._ping: float = 0.0

        self._position: int = 0
        self._last_position: int = 0
        self._last_update: int = 0
        self._ending_track: Optional[Track] = None

        self._voice_state: dict = {}
        self._playback = PlaybackSession()
        self._attempt_lock = asyncio.Lock()
        self._queue_lock = asyncio.Lock()
        self._playback_log = logging.getLogger("vocard.playback")
        self._watchdog_task: Optional[asyncio.Task] = None
        self._exception_fallback_task: Optional[asyncio.Task] = None
        self._recovery_task: Optional[asyncio.Task] = None
        self._desired_connected: bool = True
        self._tearing_down: bool = False
        self._had_started: bool = False

        self.controller: Union[Message, PartialMessage] = None
        self._updating: bool = False

        self.pause_votes = set()
        self.resume_votes = set()
        self.skip_votes = set()
        self.previous_votes = set()
        self.shuffle_votes = set()
        self.stop_votes = set()

        self._ph = PlayerPlaceholder(client, self)
        self._logger: Optional[logging.Logger] = self._node._logger
        self._inactive_cleanup_task: Optional[asyncio.Task[None]] = None

    def __repr__(self):
        return (
            f"<Voicelink.player bot={self.bot} guildId={self.guild.id} "
            f"is_connected={self.is_connected} is_playing={self.is_playing}>"
        )

    @property
    def position(self) -> float:
        """Property which returns the player's position in a track in milliseconds"""
        if not self.is_playing or not self._current:
            return 0

        if self.is_paused:
            return min(self._last_position, self._current.length)

        difference = (time.time() * 1000) - self._last_update
        position = self._last_position + difference

        if position > self._current.length:
            return 0

        return min(position, self._current.length)

    @property
    def is_playing(self) -> bool:
        """Property which returns whether or not the player is actively playing a track."""
        return self._is_connected and self._current is not None

    @property
    def is_connected(self) -> bool:
        """Property which returns whether or not the player is connected"""
        return self._is_connected

    @property
    def is_paused(self) -> bool:
        """Property which returns whether or not the player has a track which is paused or not."""
        return self._is_connected and self._paused

    @property
    def current(self) -> Optional[Track]:
        """Property which returns the currently playing track"""
        return self._current

    @property
    def node(self) -> Node:
        """Property which returns the node the player is connected to"""
        return self._node

    @property
    def guild(self) -> Guild:
        """Property which returns the guild associated with the player"""
        return self._guild

    @property
    def volume(self) -> int:
        """Property which returns the players current volume"""
        return self._volume

    @property
    def filters(self) -> Filters:
        """Property which returns the helper class for interacting with filters"""
        return self._filters

    @property
    def bot(self) -> Client:
        """Property which returns the bot associated with this player instance"""
        return self._bot

    @property
    def is_dead(self) -> bool:
        """Returns a bool representing whether the player is dead or not.
           A player is considered dead if it has been destroyed and removed from stored players.
        """
        return self.guild.id not in self._node._players

    @property
    def ping(self) -> float:
        """Calculates and returns the player's current ping in seconds."""
        return round(self._ping / 1000, 2)
    
    @property
    def autoplay(self) -> bool:
        """Indicates whether the player is set to autoplay."""
        return self.settings.get("autoplay", False)
    
    @property
    def data(self) -> dict:
        """Returns a dictionary containing the player's data."""
        return {
            "guild_id": self._guild.id,
            "channel_id": self.channel.id,
            "queue": {
                "tracks": self.queue.session_track_data(),
                "position": self.queue._position,
                "repeat_mode": self.queue._repeat.current.name,
                "repeat_position": self.queue._repeat_position
            },
            "dj": self.dj.id,
            "is_paused": self.is_paused,
            "position": self.position,
            "autoplay": self.autoplay
        }
    
    @property
    def is_ipc_connected(self) -> bool:
        """Indicates whether the Inter-Process Communication (IPC) connection is active."""
        return self._ipc_client._is_connected and self._ipc_connection
        
    def get_msg(self, *keys) -> Union[list[str], str]:
        """Retrieves a localized message or list of messages based on the given keys
           for the guild associated with this player.
        """
        return LangHandler._get_lang(self.settings.get("lang"), *keys)

    def required(self, leave: bool = False):
        """
        Calculates the number of votes required for a specific action in the voice channel.

        If `leave` is True and the channel has three members, the requirement adjusts to 2 votes.
        """
        if self.settings.get('disabled_vote'):
            return 0

        required = ceil((len(self.channel.members) - 1) / 2.5)
        if leave:
            required += 1
        
        return required
    
    def is_user_join(self, user: Member):
        """Checks if a user is present in the voice channel or has 'Manage Server' permission."""
        if user not in self.channel.members:
            if not user.guild_permissions.manage_guild:
                return False        
        return True
    
    def is_privileged(self, user: Member, check_user_join: bool = True) -> bool:
        """
        Determines if a user has privileged access.

        Privileged access is granted if the user is in the bot access list, 
        has 'Manage Server' permission, or meets the DJ role criteria in the settings.
        Raises an exception if `check_user_join` is True and the user is not in the channel.
        """
        if user.id in Config().bot_access_user:
            return True
        
        manage_perm = user.guild_permissions.manage_guild
        if check_user_join and not self.is_user_join(user):
            raise VoicelinkException(self.get_msg('voice.connection.notInChannel').format(user.mention, self.channel.mention))
            
        if 'dj' in self.settings and self.settings['dj']:
            return manage_perm or (self.settings['dj'] in [role.id for role in user.roles])
        return self.dj.id == user.id or manage_perm
    
    def build_embed(self, current_track: Track = None):
        """Builds an embed based on the current track state."""
        controller = self.settings.get("default_controller", Config().controller).get("embeds", {})
        embed_form = controller.get("active" if current_track else "inactive", {})
        
        return PlayerPlaceholder.build_embed(embed_form, self._ph)

    async def send(self, method: RequestMethod, query: str = None, data: Union[Dict, str] = {}, kind: str = None) -> Dict:
        """Sends an HTTP request to the node with the given method, query, and data."""
        uri: str = f"sessions/{self._node._session_id}/players/{self._guild.id}" + (f"?{query}" if query else "")
        return await self._node.send(method, query=uri, data=data, kind=kind)
        
    async def _update_state(self, data: dict) -> None:
        """Updates the player's state based on the provided data."""
        state: dict = data.get("state")
        self._last_update = time.time() * 1000
        self._is_connected = state.get("connected")
        self._last_position = state.get("position")
        self._ping = state.get("ping")
        self._logger.debug(f"Player in {self.guild.name}({self.guild.id}) update state with data {data}")

        if self.is_ipc_connected:
            await self.send_ws({
                "op": "playerUpdate",
                "lastUpdate": self._last_update,
                "isConnected": self._is_connected,
                "lastPosition": self._last_position
            })

    async def _dispatch_voice_update(self, voice_data: Dict[str, Any] = None):
        """Dispatches a voice update to the node."""
        if {"sessionId", "event"} != self._voice_state.keys():
            self._logger.debug(f"Player in {self.guild.name}({self.guild.id}) dispatched voice update failed {voice_data}")
            return

        state = voice_data or self._voice_state

        data = {
            "token": state['event']['token'],
            "endpoint": state['event']['endpoint'],
            "sessionId": state['sessionId'],
            "channelId": str(self.channel.id),
        }
        
        await self.send(method=RequestMethod.PATCH, data={"voice": data})
        self._logger.debug(f"Player in {self.guild.name}({self.guild.id}) dispatched voice update to {state['event']['endpoint']} with data {data}")

    async def on_voice_server_update(self, data: dict):
        """Handles a voice server update event."""
        self._voice_state.update({"event": data})
        await self._dispatch_voice_update(self._voice_state)

    async def on_voice_state_update(self, data: dict):
        """Handles a voice state update event."""
        self._voice_state.update({"sessionId": data.get("session_id")})

        if not (channel_id := data.get("channel_id")):
            await self.teardown()
            self._voice_state.clear()
            return

        self.channel = self.guild.get_channel(int(channel_id))

        if not data.get("token"):
            return

        await self._dispatch_voice_update({**self._voice_state, "event": data})

    def _sync_current(self) -> None:
        self._playback.desired_connected = self._desired_connected
        self._playback.tearing_down = self._tearing_down
        self._current_item = self._playback.current_item
        self._current = self._current_item.track if self._current_item else None

    def _cancel_attempt_tasks_locked(self) -> List[asyncio.Task]:
        owned = {
            "_watchdog_task": self._watchdog_task,
            "_exception_fallback_task": self._exception_fallback_task,
        }
        cleared, pending = cancel_owned_tasks(owned)
        for name in cleared:
            setattr(self, name, None)
        return pending

    def suspend_playback_watchdog(self) -> None:
        self._playback.watchdog_suspended = True
        task = self._watchdog_task
        self._watchdog_task = None
        current = asyncio.current_task()
        if task and not task.done() and task is not current:
            task.cancel()

    def _log_playback(self, event: str, *, level: int = logging.INFO, **fields) -> None:
        self._playback.log(event, guild_id=getattr(self._guild, "id", None), **fields)
        extras = format_playback_log_fields(fields)
        self._playback_log.log(level, "%s %s", event, extras)

    async def _dispatch_event(self, data: dict):
        """Dispatches an event based on the type of event data received."""
        event_type = data.get("type")
        if not event_type:
            return
        if event_type == "TrackExceptionEvent":
            if is_youtube_content_unavailable(data) and self._node.yt_ratelimit:
                await self._node.yt_ratelimit.flag_active_token()

        event: VoicelinkEvent = getattr(events, event_type)(data, self)
        event.dispatch(self._bot)

        if isinstance(event, TrackStartEvent):
            self._ending_track = event.track or self._current
            await self.handle_track_start(event.track, encoded=event.encoded)

        self._logger.debug(f"Player in {self.guild.name}({self.guild.id}) dispatched event {event_type}.")

    async def handle_track_start(self, track, encoded: str = None) -> None:
        encoded = encoded or getattr(track, "track_id", None)
        applied = False
        tasks: List[asyncio.Task] = []
        async with self._attempt_lock:
            disposition = self._playback.enqueue_or_apply(PendingEventKind.TRACK_START, encoded=encoded)
            if disposition not in (EventDisposition.APPLY, EventDisposition.AMBIGUOUS):
                return
            applied = self._playback.apply_track_start(encoded)
            if applied:
                self._had_started = True
            self._sync_current()
            tasks = self._cancel_attempt_tasks_locked()
        await self._absorb_cancelled(tasks)
        if applied:
            self._log_playback("TRACK_START", item_id=getattr(self._current_item, "item_id", None), track=getattr(track, "title", None))
            source_recovered = health_store.record_track_start(getattr(track, "source", None))
            health_store.clear_guild_failure(getattr(self._guild, "id", None))
            if source_recovered:
                await NodePool.broadcast_playback_health()
            elif self.is_ipc_connected:
                await self._node.broadcast_playback_health(guild_id=self.guild.id)

    async def handle_track_end(self, track, reason: str, encoded: str = None) -> None:
        encoded = encoded or getattr(track, "track_id", None)
        async with self._attempt_lock:
            disposition = self._playback.enqueue_or_apply(
                PendingEventKind.TRACK_END, encoded=encoded, reason=reason
            )
            if disposition != EventDisposition.APPLY:
                return
            tasks = self._cancel_attempt_tasks_locked()
            if reason == "finished":
                decision = self._playback.on_finished()
                reason_enum = PlaybackAdvanceReason.FINISHED
            elif reason == "loadFailed":
                decision = self._playback.on_load_failed()
                reason_enum = PlaybackAdvanceReason.LOAD_FAILED
            elif reason == "replaced":
                decision = self._playback.on_replaced()
                reason_enum = PlaybackAdvanceReason.REPLACED
            elif reason == "stopped":
                decision = self._playback.on_stopped()
                reason_enum = PlaybackAdvanceReason.MANUAL_SKIP
            elif reason == "cleanup":
                decision = self._playback.on_cleanup()
                reason_enum = PlaybackAdvanceReason.CLEANUP
            else:
                self._log_playback("TRACK_END", reason=reason or "UNKNOWN")
                decision = "IGNORE"
                reason_enum = PlaybackAdvanceReason.UNKNOWN
            self._sync_current()
        await self._absorb_cancelled(tasks)
        self._log_playback("TRACK_END", reason=reason, item_id=getattr(self._current_item, "item_id", None))
        await self._run_decision(decision, reason_enum)

    async def handle_track_stuck(self, track, threshold=None, encoded: str = None) -> None:
        encoded = encoded or getattr(track, "track_id", None)
        async with self._attempt_lock:
            disposition = self._playback.enqueue_or_apply(
                PendingEventKind.TRACK_STUCK, encoded=encoded, threshold=threshold
            )
            if disposition != EventDisposition.APPLY:
                return
            tasks = self._cancel_attempt_tasks_locked()
            decision = self._playback.on_stuck()
            self._sync_current()
        await self._absorb_cancelled(tasks)
        self._log_playback("TRACK_STUCK", item_id=getattr(self._current_item, "item_id", None))
        await self._run_decision(decision, PlaybackAdvanceReason.TRACK_STUCK)

    async def handle_track_exception(self, track, error: dict, encoded: str = None) -> None:
        encoded = encoded or getattr(track, "track_id", None)
        start_fallback = False
        async with self._attempt_lock:
            disposition = self._playback.enqueue_or_apply(
                PendingEventKind.TRACK_EXCEPTION, encoded=encoded, exception=error
            )
            if disposition != EventDisposition.APPLY:
                return
            started = self._playback.apply_track_exception(error)
            start_fallback = started and self._exception_fallback_task is None
            if start_fallback:
                attempt_id = self._playback.attempt.attempt_id if self._playback.attempt else None
                item_id = self._playback.attempt.item_id if self._playback.attempt else None
                self._exception_fallback_task = self.bot.loop.create_task(
                    self._exception_fallback_worker(attempt_id, item_id)
                )
        track_obj = track or getattr(self._current_item, "track", None)
        self._log_playback(
            "TRACK_EXCEPTION",
            level=logging.ERROR,
            item_id=getattr(self._current_item, "item_id", None),
            attempt_id=getattr(self._playback.attempt, "attempt_id", None),
            node=getattr(self._node, "_identifier", None),
            source=getattr(track_obj, "source", None),
            track=getattr(track_obj, "title", None),
            uri=safe_log_text(getattr(track_obj, "uri", None), limit=180),
            **exception_log_fields(error if isinstance(error, dict) else None),
        )
        classification, changed = health_store.record_exception(
            source=getattr(track_obj, "source", None),
            exception=error if isinstance(error, dict) else None,
            item_id=getattr(self._current_item, "item_id", None),
            encoded=encoded,
            title=getattr(track_obj, "title", None),
            guild_id=getattr(self._guild, "id", None),
            node_available=bool(getattr(self._node, "_available", True)),
        )
        playback_failure = {
            "code": classification.code,
            "title": getattr(track_obj, "title", None),
            "source": getattr(track_obj, "source", None),
        }
        if changed:
            await NodePool.broadcast_playback_health()
        elif self.is_ipc_connected:
            await self._node.broadcast_playback_health(
                guild_id=self.guild.id,
                playback_failure=playback_failure,
            )

    async def _exception_fallback_worker(self, attempt_id: Optional[int], item_id: Optional[int]) -> None:
        try:
            await asyncio.sleep(EXCEPTION_END_FALLBACK)
            async with self._attempt_lock:
                if not self._playback.attempt or self._playback.attempt.attempt_id != attempt_id:
                    return
                if self._playback.attempt.item_id != item_id:
                    return
                decision = self._playback.on_exception_fallback()
                tasks = self._cancel_attempt_tasks_locked()
                self._sync_current()
            await self._absorb_cancelled(tasks)
            await self._run_decision(decision, PlaybackAdvanceReason.PLAYBACK_EXCEPTION)
        except asyncio.CancelledError:
            return

    async def _watchdog_worker(self, attempt_id: int, item_id: int, play_seq: int) -> None:
        try:
            await asyncio.sleep(TRACK_START_TIMEOUT)
            async with self._attempt_lock:
                if self._playback.watchdog_suspended:
                    return
                if not self._playback.attempt or self._playback.attempt.attempt_id != attempt_id:
                    return
                if self._playback.attempt.play_seq != play_seq or self._playback.attempt.item_id != item_id:
                    return
                decision = self._playback.on_watchdog()
                tasks = self._cancel_attempt_tasks_locked()
                self._sync_current()
            await self._absorb_cancelled(tasks)
            await self._run_decision(decision, PlaybackAdvanceReason.PLAY_REQUEST_FAILED)
        except asyncio.CancelledError:
            return

    async def _absorb_cancelled(self, tasks: List[asyncio.Task]) -> None:
        current = asyncio.current_task()
        wait = [task for task in tasks if task is not None and task is not current]
        if not wait:
            return
        await asyncio.gather(*wait, return_exceptions=True)

    async def _run_decision(self, decision: str, reason: PlaybackAdvanceReason) -> None:
        if decision in (None, "IGNORE"):
            return
        if decision == "TEARDOWN":
            return
        if decision == "RETRY":
            await self._run_retry()
            return
        if decision in ("ADVANCE", "FORCEPLAY_ADVANCE"):
            await self._commit_and_play(
                reason,
                skip_exhausted=reason in (
                    PlaybackAdvanceReason.LOAD_FAILED,
                    PlaybackAdvanceReason.TRACK_STUCK,
                    PlaybackAdvanceReason.PLAY_REQUEST_FAILED,
                    PlaybackAdvanceReason.PLAYBACK_EXCEPTION,
                ),
            )
            return
        if decision == "RECOVER":
            await self.request_playback_recovery(resume_failed=True)
            return
        if decision == "RECONCILE":
            await self._request_reconcile()

    async def _commit_and_play(self, reason: PlaybackAdvanceReason, *, skip_exhausted: bool = False) -> None:
        notify = None
        cancelled = []
        async with self._attempt_lock:
            async with self._queue_lock:
                cancelled = self._cancel_attempt_tasks_locked()
                next_item = self.queue.get_item(
                    force_next=skip_exhausted and self.queue._repeat.mode == LoopType.TRACK,
                    skip_exhausted=skip_exhausted,
                )
                commit = self._playback.commit_advance(
                    reason,
                    next_item,
                    notify=reason in (
                        PlaybackAdvanceReason.LOAD_FAILED,
                        PlaybackAdvanceReason.TRACK_STUCK,
                        PlaybackAdvanceReason.PLAY_REQUEST_FAILED,
                        PlaybackAdvanceReason.PLAYBACK_EXCEPTION,
                    ),
                )
                self._sync_current()
                self._had_started = False
                if commit.from_item is not None:
                    self._log_playback(
                        "QUEUE_ADVANCE",
                        from_item=commit.from_item.item_id,
                        to_item=commit.to_item.item_id if commit.to_item else None,
                        attempt_id=commit.from_attempt_id,
                        reason=str(reason),
                        retry_count=commit.from_item.retry_count,
                        track=getattr(commit.from_item.track, "title", None),
                    )
                notify = commit.notify
        await self._absorb_cancelled(cancelled)
        if notify and not self._tearing_down:
            self.bot.loop.create_task(self._notify_playback_failure(notify))
        await self._after_new_item()
        if self._current_item and self._desired_connected and not self._tearing_down:
            await self._issue_play()
        elif not self._current_item and self.autoplay and not self._tearing_down:
            if await self.get_recommendations():
                await self.do_next()

    async def _run_retry(self) -> None:
        cancelled = []
        async with self._attempt_lock:
            if self._playback.reservation is None or self._playback.reservation.cancelled:
                return
            cancelled = self._cancel_attempt_tasks_locked()
            attempt = self._playback.commit_retry()
            self._sync_current()
            self._had_started = False
        await self._absorb_cancelled(cancelled)
        if not attempt or not self._current_item:
            await self._commit_and_play(PlaybackAdvanceReason.LOAD_FAILED, skip_exhausted=True)
            return
        self._log_playback("RETRY", item_id=self._current_item.item_id, attempt_id=attempt.attempt_id, retry_count=self._current_item.retry_count)
        if not self.guild.me.voice:
            await self.connect(timeout=0.0, reconnect=True)
        await self._issue_play()

    async def _after_new_item(self) -> None:
        if not self.channel:
            return
        if self._paused:
            self._paused = False
        if self.guild and self.guild.me and not self.guild.me.voice:
            await self.connect(timeout=0.0, reconnect=True)

        self.pause_votes.clear()
        self.resume_votes.clear()
        self.skip_votes.clear()
        self.previous_votes.clear()
        self.shuffle_votes.clear()
        self.stop_votes.clear()

        if not self._current_item:
            if self.queue.is_empty:
                self._schedule_inactive_cleanup_timer()
        else:
            self._cancel_inactive_cleanup_timer()

        await self.invoke_controller()
        await self.update_voice_status()

        track = self._current
        if self.is_ipc_connected:
            await self.send_ws({
                "op": "trackUpdate",
                "currentQueuePosition": self.queue._position if track else self.queue._position + 1,
                "trackId": track.track_id if track else None,
                "isPaused": self._paused
            })

    async def _issue_play(self, *, recovery: bool = False) -> None:
        async with self._attempt_lock:
            item = self._playback.current_item
            attempt = self._playback.attempt
            if not item or not attempt or self._tearing_down or not self._desired_connected:
                return
            play_seq = attempt.play_seq
            attempt_id = attempt.attempt_id
            item_id = item.item_id
            start = self._playback.retry_start_position(
                recovery_after_started=recovery and self._had_started,
                last_position=int(self._last_position or 0),
            )
            end_time = self._playback.intended_end_time()
            track = item.track
            self._playback.mark_play_in_flight()
            self._playback.watchdog_suspended = False
        self._log_playback("PLAY_REQUEST", item_id=item_id, attempt_id=attempt_id, play_seq=play_seq, start=start)
        try:
            await self.play(track, start=start, end=end_time or 0)
        except asyncio.CancelledError:
            raise
        except NodeNotAvailable:
            async with self._attempt_lock:
                if self._playback.validate_play_completion(play_seq, item_id, attempt_id):
                    decision = self._playback.on_node_unavailable()
                else:
                    decision = "IGNORE"
                self._sync_current()
            self._log_playback(
                "NODE_DISCONNECT",
                item_id=item_id,
                attempt_id=attempt_id,
                play_seq=play_seq,
            )
            if decision == "TEARDOWN":
                return
            return
        except NodeException as e:
            if not e.is_play_patch:
                self._logger.error(
                    f"Non-play REST error during playback in {self.guild.name}({self.guild.id})",
                    exc_info=e,
                )
                return
            async with self._attempt_lock:
                valid = self._playback.validate_play_completion(play_seq, item_id, attempt_id)
                self._playback.fail_play_patch()
                if not valid:
                    self._playback.mark_reconcile()
                    should_retry = False
                    decision = "RECONCILE"
                elif self._playback.claim(TerminalSource.PLAY_REST):
                    decision = self._playback.decide_after_failure(TerminalSource.PLAY_REST)
                    should_retry = True
                else:
                    decision = "IGNORE"
                self._sync_current()
            if decision == "RECONCILE":
                await self._request_reconcile()
            elif should_retry:
                await self._run_decision(decision, PlaybackAdvanceReason.PLAY_REQUEST_FAILED)
            return
        except Exception as e:
            self._logger.error(f"Something went wrong while playing music in {self.guild.name}({self.guild.id})", exc_info=e)
            async with self._attempt_lock:
                if self._playback.validate_play_completion(play_seq, item_id, attempt_id) and self._playback.claim(TerminalSource.PLAY_REST):
                    decision = self._playback.decide_after_failure(TerminalSource.PLAY_REST)
                else:
                    decision = "IGNORE"
            await self._run_decision(decision, PlaybackAdvanceReason.PLAY_REQUEST_FAILED)
            return

        pending = []
        start_watchdog = False
        async with self._attempt_lock:
            if not self._playback.validate_play_completion(play_seq, item_id, attempt_id):
                self._playback.mark_reconcile()
                await_reconcile = True
            else:
                await_reconcile = False
                pending = self._playback.arm_after_play_success()
                if self._playback.record_history_if_needed() and track.requester and not track.requester.bot:
                    self._bot.loop.create_task(MongoDBHandler.update_user(track.requester.id, {
                        "$push": {"history": {"$each": [track.track_id], "$slice": -25}}
                    }))
                if self._playback.attempt and self._playback.attempt.state == AttemptState.STARTING:
                    start_watchdog = True
                    self._watchdog_task = self.bot.loop.create_task(
                        self._watchdog_worker(attempt_id, item_id, play_seq)
                    )
            self._sync_current()
        if await_reconcile:
            await self._request_reconcile()
            return
        for event in pending:
            await self._apply_pending_event(event)
        if start_watchdog and self._playback.attempt and self._playback.attempt.state != AttemptState.STARTING:
            task = self._watchdog_task
            self._watchdog_task = None
            _, pending = cancel_owned_tasks({"_watchdog_task": task})
            await self._absorb_cancelled(pending)

    async def _apply_pending_event(self, event) -> None:
        if event.kind == PendingEventKind.TRACK_START:
            await self.handle_track_start(self._current, encoded=event.encoded)
        elif event.kind == PendingEventKind.TRACK_END:
            await self.handle_track_end(self._current, event.reason or "unknown", encoded=event.encoded)
        elif event.kind == PendingEventKind.TRACK_EXCEPTION:
            await self.handle_track_exception(self._current, event.exception or {}, encoded=event.encoded)
        elif event.kind == PendingEventKind.TRACK_STUCK:
            await self.handle_track_stuck(self._current, event.threshold, encoded=event.encoded)

    async def _notify_playback_failure(self, snapshot) -> None:
        if self._tearing_down or not self._desired_connected:
            return
        try:
            if self.context:
                await self.context.send(
                    f"{snapshot.title} could not be played. Skipping to the next track.",
                    delete_after=10,
                )
        except Exception:
            self._playback_log.warning("Failed to send playback failure notification for item_id=%s", snapshot.item_id)

    async def _request_reconcile(self) -> None:
        generation = self._playback.mark_reconcile()
        if self._recovery_task and not self._recovery_task.done():
            return
        self._recovery_task = self.bot.loop.create_task(self._reconcile_worker(generation))

    async def _reconcile_worker(self, generation: int) -> None:
        try:
            async with self._attempt_lock:
                if not self._playback.take_reconcile(generation):
                    return
                expected = self._playback.current_item
            if expected is None or self._tearing_down or not self._desired_connected:
                return
            state = await fetch_player_state(self._node, self._node._session_id, self.guild.id)
            remote = remote_encoded_track(state)
            intended = getattr(expected.track, "track_id", None)
            if remote == intended:
                if self._playback.attempt and self._playback.attempt.state == AttemptState.STARTING:
                    async with self._attempt_lock:
                        self._playback.apply_track_start(intended)
                        self._had_started = True
                return
            await self._issue_play(recovery=self._had_started)
        except asyncio.CancelledError:
            return
        except Exception as e:
            self._logger.error("Playback reconcile failed", exc_info=e)

    async def on_session_resumed(self) -> None:
        self._playback.watchdog_suspended = False
        task = self._watchdog_task
        self._watchdog_task = None
        _, pending = cancel_owned_tasks({"_watchdog_task": task})
        await self._absorb_cancelled(pending)
        await self._request_reconcile()

    async def request_playback_recovery(self, *, resume_failed: bool = False) -> None:
        if self._tearing_down or not self._desired_connected:
            return
        async with self._attempt_lock:
            if not self._playback.current_item:
                return
            if self._playback.attempt and self._playback.attempt.intent in (AttemptIntent.SKIP, AttemptIntent.STOP, AttemptIntent.FORCEPLAY):
                return
            if self._playback.attempt:
                self._playback.attempt.state = AttemptState.RECOVERING
        if resume_failed:
            await self._issue_play(recovery=self._had_started)

    async def do_next(self):
        """Processes the next track in the queue."""
        if self._tearing_down or not self.channel:
            return
        if self._current or self.is_playing:
            return
        await self._commit_and_play(PlaybackAdvanceReason.FINISHED)

    async def request_skip(self) -> None:
        async with self._attempt_lock:
            decision = self._playback.user_skip()
        if decision == "STOP_THEN_ADVANCE":
            try:
                await self.send(method=RequestMethod.PATCH, data={"encodedTrack": None}, kind="PLAYER_STOP")
            except Exception:
                await self._commit_and_play(PlaybackAdvanceReason.MANUAL_SKIP)
            return
        if decision == "ADVANCE":
            try:
                await self.send(method=RequestMethod.PATCH, data={"encodedTrack": None}, kind="PLAYER_STOP")
            except Exception:
                pass
            await self._commit_and_play(PlaybackAdvanceReason.MANUAL_SKIP)

    async def invoke_controller(self):
        """Sends or updates the music controller message in the designated channel."""
        if not self.settings.get('controller', True) or self._updating or not self.channel:
            return
        
        self._updating = True

        try:            
            embed, view = self.build_embed(self.current), InteractiveController(self)
            if not self.controller:
                if request_channel_data := self.settings.get("music_request_channel"):
                    if channel := self.bot.get_channel(request_channel_data.get("text_channel_id")):
                        try:
                            self.controller = await channel.fetch_message(request_channel_data.get("controller_msg_id"))
                            await self.controller.edit(embed=embed, view=view)
                        except errors.NotFound:
                            self.controller = None
                
                # Send a new controller message if none exists
                if not self.controller:
                    self.controller = await dispatch_message(self.context, content=embed, view=view, delete_after=None, requires_fetch=True)

            elif not await self.is_position_fresh():
                try:
                    await self.controller.delete()
                except errors.NotFound:
                    self.controller = None
                    
                self.controller = await dispatch_message(self.context, content=embed, view=view, delete_after=None, requires_fetch=True)

            else:
                await self.controller.edit(embed=embed, view=view)
        
        except errors.Forbidden:
            self._logger.warning(f"Missing permission to update the music controller on {self.guild.name}({self.guild.id})")

        except Exception as e:
            self._logger.error(f"Something went wrong while sending music controller to {self.guild.name}({self.guild.id})", exc_info=e)
        
        finally:
            self._updating = False

    async def is_position_fresh(self):
        """Checks if the current controller message is among the most recent messages."""
        try:
            async for message in self.context.channel.history(limit=5):
                if message.id == self.controller.id:
                    return True
        except:
            pass

        return False
    
    async def teardown(self):
        """Cleans up the player and associated resources."""
        self._desired_connected = False
        self._tearing_down = True
        async with self._attempt_lock:
            self._playback.user_leave()
            cancelled = self._cancel_attempt_tasks_locked()
            self._sync_current()
        await self._absorb_cancelled(cancelled)
        recovery = self._recovery_task
        self._recovery_task = None
        _, pending = cancel_owned_tasks({"_recovery_task": recovery})
        await self._absorb_cancelled(pending)
        try:
            await MongoDBHandler.update_settings(self.guild.id, {"$set": {
                "last_active": (timeNow := round(time.time())), 
                "played_time": round(self.settings.get("played_time", 0) + ((timeNow - self.joinTime) / 60), 2)
            }})
            
            if self.is_ipc_connected:
                await self.send_ws({"op": "playerClose"})
        except:
            pass

        try:
            await self.update_voice_status(remove_status=True)
            self._cancel_inactive_cleanup_timer()
            if self.controller:
                if self.controller.id == self.settings.get("music_request_channel", {}).get("controller_msg_id"):
                    await self.controller.edit(embed=self.build_embed(), view=None)
                else: 
                    await self.controller.delete()
        except:
            pass

        try:
            await self.destroy()
        except:
            pass

    async def get_tracks(
        self,
        query: str,
        *,
        requester: Member,
        search_type: SearchType = None
    ) -> Union[List[Track], Playlist]:
        """Fetches tracks from the node's REST api to parse into Lavalink.

        You can also pass in a discord.py Context object to get a
        Context object on any track you search.
        """
        if not search_type:
            search_type = Config().search_platform
            
        return await self._node.get_tracks(query, requester=requester, search_type=search_type)

    async def connect(self, *, timeout: float, reconnect: bool, self_deaf: bool = True, self_mute: bool = False):
        """Connects the player to a voice channel."""
        await self.guild.change_voice_state(channel=self.channel, self_deaf=True, self_mute=self_mute)
        self._node._players[self.guild.id] = self
        self._desired_connected = True
        self._tearing_down = False
        self._is_connected = True

        if self.channel:
            self._logger.debug(f"Player in {self.guild.name}({self.guild.id}) has been connected to {self.channel.name}({self.channel.id}).")
            
    async def stop(self, *, intent: AttemptIntent = AttemptIntent.SKIP):
        """Stops the currently playing track."""
        should_advance = False
        async with self._attempt_lock:
            if intent == AttemptIntent.FORCEPLAY:
                target = self.queue.peek_next_item()
                if target:
                    self._playback.begin_forceplay(target.item_id)
            elif self._playback.attempt:
                self._playback.attempt.intent = intent
                if intent == AttemptIntent.SKIP and self._playback.attempt.state != AttemptState.STARTED:
                    decision = self._playback.user_skip()
                    should_advance = decision == "ADVANCE"
            if self._playback.attempt and self._playback.attempt.play_in_flight:
                self._playback.remember_stale(self._playback.attempt.item_id, self._playback.attempt.play_seq)
        try:
            await self.send(method=RequestMethod.PATCH, data={'encodedTrack': None}, kind="PLAYER_STOP")
        except Exception:
            if intent == AttemptIntent.SKIP:
                should_advance = True
        if should_advance:
            await self._commit_and_play(PlaybackAdvanceReason.MANUAL_SKIP)

    async def disconnect(self, *, force: bool = False):
        """Disconnects the player from voice."""
        try:
            await self.guild.change_voice_state(channel=None)
        finally:
            self.cleanup()
            self._is_connected = False
            self.channel = None
        
        self._logger.debug(f"Player in {self.guild.name}({self.guild.id}) has been disconnected from a voice channel.")

    async def destroy(self):
        """Disconnects and destroys the player, and runs internal cleanup."""
        
        try:
            await self.disconnect()
        except:
            # 'NoneType' has no attribute '_get_voice_client_key' raised by self.cleanup() ->
            # assume we're already disconnected and cleaned up
            assert self.channel is None and not self.is_connected
        
        self._node._players.pop(self.guild.id)
        await self.send(method=RequestMethod.DELETE)
    
    async def play(
        self,
        track: Track,
        *,
        start: int = 0,
        end: int = 0,
        ignore_if_playing: bool = False
    ) -> Track:
        """Plays a track."""
        if not self._node:
            return track

        data = {
            "encodedTrack": track.track_id,
            "position": str(start or 0)
        }

        if end or track.end_time:
            data["endTime"] = str(end or track.end_time)
        
        await self.send(method=RequestMethod.PATCH, query=f"noReplace={ignore_if_playing}", data=data, kind="PLAYER_PLAY")
        if self._node.yt_ratelimit:
            await self._node.yt_ratelimit.handle_request()

        if not self._current:
            self._current = track

        self._logger.debug(f"Player in {self.guild.name}({self.guild.id}) playing {track.title} from uri {track.uri} with a length of {track.length}")
        return self._current

    def _validate_time(self, track: Track, start_time: int, end_time: int) -> None:
        """Validates the start and end times for a track."""
        if start_time or end_time:
            if not end_time:
                end_time = track.length

            if start_time >= end_time:
                raise VoicelinkException(self.get_msg("time.invalidStartTime"))

            track_length = track.length
            if not 0 <= start_time <= track_length:
                raise VoicelinkException(self.get_msg("time.invalidStartTime", format_ms(track_length)))
            if not 0 <= end_time <= track_length:
                raise VoicelinkException(self.get_msg("time.invalidEndTime", format_ms(track_length)))

            track.position = start_time
            track.end_time = end_time

    def _cancel_inactive_cleanup_timer(self) -> None:
        """Cancels the per-player inactivity cleanup timer (if any)."""
        task: Optional[asyncio.Task] = getattr(self, "_inactive_cleanup_task", None)
        if task and not task.done():
            task.cancel()
        self._inactive_cleanup_task = None

    def _schedule_inactive_cleanup_timer(self) -> None:
        """Schedules per-player cleanup after inactivity."""
        self._cancel_inactive_cleanup_timer()
        seconds = Config().timer_settings.get("inactive_player_cleanup", 600)
        self._inactive_cleanup_task = self.bot.loop.create_task(
            self._inactive_cleanup_timer_worker(seconds)
        )
        
    async def add_track(self, raw_tracks: Union[Track, List[Track]], *, start_time: int = 0, end_time: int = 0, at_front: bool = False, duplicate: bool = True) -> int:
        """Adds one or more tracks to the queue."""
        tracks: List[Track] = []
        _duplicate_tracks = [] if self.queue._allow_duplicate and duplicate else self.queue.queued_uris()
        raw_tracks = raw_tracks[0] if isinstance(raw_tracks, List) and len(raw_tracks) == 1 else raw_tracks

        try:
            if (is_list := isinstance(raw_tracks, List)):
                for track in raw_tracks:
                    if track.uri in _duplicate_tracks:
                        continue

                    self._validate_time(track, start_time, end_time)
                    self.queue.put_at_front(track) if at_front else self.queue.put(track)  
                    tracks.append(track)
                    _duplicate_tracks.append(track.uri)
            else:
                if raw_tracks.uri in _duplicate_tracks:
                    raise DuplicateTrack(self.get_msg("queue.errors.duplicateTrack"))
                
                self._validate_time(raw_tracks, start_time, end_time)
                position = self.queue.put_at_front(raw_tracks) if at_front else self.queue.put(raw_tracks)
                tracks.append(raw_tracks)
                
        finally:
            if tracks:
                if self.channel.members and len([m for m in self.channel.members if not m.bot]) > 0:
                    self._cancel_inactive_cleanup_timer()
                if self.is_ipc_connected:
                    await self.send_ws({"op": "addTrack", "tracks": [track.track_id for track in tracks], "position": -1 if is_list else position}, tracks[0].requester)

                self._logger.debug(f"Player in {self.guild.name}({self.guild.id}) has been added {len(tracks)} tracks into the queue.")
                return len(tracks) if is_list else position
    
    async def remove_track(self, index: int, index2: int = None, remove_target: Member = None, requester: Member = None) -> Dict[int, Track]:
        """Removes one or more tracks from the queue."""
        removed_tracks = self.queue.remove(index, index2, remove_target)
        if removed_tracks and self.is_ipc_connected:
            await self.send_ws({
                "op": "removeTrack",
                "indexes": list(removed_tracks.keys()),
                "firstTrackId": list(removed_tracks.values())[0].track_id
            }, requester=requester)

        return removed_tracks
    
    async def seek(self, position: float, requester: Member = None) -> float:
        """Seeks to a position in the currently playing track milliseconds"""
        if not self._current:
            raise VoicelinkException("Nothing is playing right now")
        
        if position < 0 or position > self._current.length:
            raise TrackInvalidPosition("Seek position must be between 0 and the track length")

        await self.send(method=RequestMethod.PATCH, data={"position": position})
        if self.is_ipc_connected:
            await self.send_ws({"op": "updatePosition", "position": position}, requester)
        
        self._logger.debug(f"Player in {self.guild.name}({self.guild.id}) has been seeking to {position}.")
        return self._position

    async def set_pause(self, pause: bool, requester: Member = None) -> bool:
        """Sets the pause state of the currently playing track."""

        self._paused = pause
        self.pause_votes.clear() if pause else self.resume_votes.clear()
        await self.send(method=RequestMethod.PATCH, data={"paused": pause})

        if self.is_ipc_connected:
            await self.send_ws({"op": "updatePause", "pause": pause}, requester)
        
        self._logger.debug(f"Player in {self.guild.name}({self.guild.id}) has been {'paused' if pause else 'resumed'}.")
        return self._paused

    async def set_volume(self, volume: int, requester: Member = None) -> int:
        """Sets the volume of the player as an integer. Lavalink accepts values from 0 to 500."""
        await self.send(method=RequestMethod.PATCH, data={"volume": volume})
        self._volume = volume

        if self.is_ipc_connected:
            await self.send_ws({"op": "updateVolume", "volume": volume}, requester)

        self._logger.debug(f"Player in {self.guild.name}({self.guild.id}) has been update the volume to {volume}.")
        return self._volume

    async def shuffle(self, queue_type: str, requester: Member = None) -> None:
        """Shuffles the tracks in the specified queue or history."""
        replacement = self.queue.tracks() if queue_type == "queue" else self.queue.history()
        if len(replacement) < 3:
            raise VoicelinkException(self.get_msg('player.controls.shuffle.error'))
        
        shuffle(replacement)
        self.queue.replace(queue_type, replacement)
        self.shuffle_votes.clear()
        if self.is_ipc_connected:
            await self.send_ws({
                "op": "shuffleTrack",
                "tracks": [{"trackId": track.track_id, "requesterId": str(track.requester.id)} for track in replacement],
                "queue_type": queue_type
            }, requester)
        
        self._logger.debug(f"Player in {self.guild.name}({self.guild.id}) has been shuffled the queue.")

    async def swap_track(self, index1: int, index2: int, requester: Member = None) -> Tuple[Track, Track]:
       """Swaps two tracks in the queue at the specified indices."""
       track1, track2 = self.queue.swap(index1, index2)
       if self.is_ipc_connected:
           await self.send_ws({
                "op": "swapTrack",
                "index1": {"index": index1, "trackId": track1.track_id},
                "index2": {"index": index2, "trackId": track2.track_id}
            }, requester)
       return track1, track2

    async def move_track(self, index: int, new_index: int, requester: Member = None) -> Optional[Track]:
        """Moves a track from its current position to a new position in the queue."""
        moved_track = self.queue.move(index, new_index)

        if self.is_ipc_connected:
            await self.send_ws({"op": "moveTrack", "movedTrack": {"index": index, "trackId": moved_track.track_id}, "newIndex": new_index}, requester)

        return moved_track
    
    async def set_repeat(self, mode: LoopType = None, requester: Member = None) -> LoopType:
        """Sets the repeat mode for the queue."""
        if not mode:
            mode = self.queue._repeat.next()
        
        if not isinstance(mode, LoopType):
            raise VoicelinkException("Invalid repeat mode.")
        
        self.queue._repeat.set_mode(mode)
        
        if self.is_ipc_connected:
            await self.send_ws({"op": "repeatTrack", "repeatMode": mode.name.lower()}, requester)

        self._logger.debug(f"Player in {self.guild.name}({self.guild.id}) has been update the repeat mode to {mode.name.lower()}.")
        return mode
    
    async def add_filter(self, filter: Filter, requester: Member = None, fast_apply: bool = False) -> Filters:
        """Adds a filter to the player's audio stream."""
        try:
            self._filters.add_filter(filter=filter)
        except FilterTagAlreadyInUse:
            raise FilterTagAlreadyInUse(self.get_msg("effects.tagInUse"))
        
        payload = self._filters.get_all_payloads()
        await self.send(method=RequestMethod.PATCH, data={"filters": payload})
        if fast_apply:
            await self.seek(self.position)
        
        if self.is_ipc_connected:
            await self.send_ws({
                "op": "updateFilter",
                "filter": {"tag": filter.tag, "scope": filter.scope, "payload": filter.payload},
                "type": "add"
            }, requester)

        self._logger.debug(f"Player in {self.guild.name}({self.guild.id}) has been applied a {filter.tag} filter.")
        return self._filters

    async def clear_queue(self, queue_type: str, requester: Member = None) -> None:
        """Clears the queue or the history of tracks."""
        queue_type = queue_type.lower()
        if queue_type == 'history':
            self.queue.history_clear(self.is_playing)
        elif queue_type == "queue":
            self.queue.clear()
        
        if self.is_ipc_connected:
            await self.send_ws({
                "op": "clearQueue",
                "queueType": queue_type
            }, requester)

    async def remove_filter(self, filter_tag: str, requester: Member = None, fast_apply: bool = False) -> Filters:
        self._filters.remove_filter(filter_tag=filter_tag)
        payload = self._filters.get_all_payloads()
        await self.send(method=RequestMethod.PATCH, data={"filters": payload})
        if fast_apply:
            await self.seek(self.position)
        
        if self.is_ipc_connected:
            await self.send_ws({
                "op": "updateFilter",
                "filter": {"tag": filter_tag},
                "type": "remove"
            }, requester)

        self._logger.debug(f"Player in {self.guild.name}({self.guild.id}) has been removed a {filter_tag} filter.")
        return self._filters
    
    async def reset_filter(self, *, requester: Member = None, fast_apply=False) -> None:
        """Resets all filters applied to the player's audio stream."""
        if not self._filters:
            raise FilterInvalidArgument("You must have filters applied first in order to use this method.")
        
        self._filters.reset_filters()
        await self.send(method=RequestMethod.PATCH, data={"filters": {}})
        if fast_apply:
            await self.seek(self.position)

        if self.is_ipc_connected:
            await self.send_ws({
                "op": "updateFilter",
                "type": "reset"
            }, requester)

        self._logger.debug(f"Player in {self.guild.name}({self.guild.id}) has been removed all filters.")

    async def change_node(self, identifier: str = None) -> None:
        """Changes the audio processing node for the guild.."""
        try:
            node = NodePool.get_node(identifier=identifier)
        except:
            return await self.teardown()

        self._node._players.pop(self.guild.id)
        self._node = node
        self._node._players[self.guild.id] = self

        await self._dispatch_voice_update(self._voice_state)

        if self.current:
            await self.request_playback_recovery(resume_failed=True)
    
    async def get_recommendations(self, *, track: Optional[Track] = None) -> bool:
        """Fetches and adds recommended tracks based on the provided track or recent history."""
        if not track:
            try:
                track = choice(self.queue.history(incTrack=True)[-5:])
            except IndexError:
                return False

        tracks = await track.get_recommendations(self._node)
        if tracks:
            await self.add_track(tracks, duplicate=False)
            
            self._logger.debug(f"Player in {self.guild.name}({self.guild.id}) has been requested recommendations.")
            return True
        return False
    
    async def update_voice_status(self, remove_status: bool = False) -> None:
        """Updates the voice status of the channel based on the specified template."""
        template = self.settings.get("stage_announce_template", Config().voice_status_template)
        if not template or not self.channel:
            return
        
        try:
            rv = {key: func() if callable(func) else func for key, func in self._ph.variables.items()}
            status = None if remove_status else self._ph.replace(text=template, variables=rv)
            # if self.channel.status != status:
            if self.channel.type == ChannelType.voice:
                await self.channel.edit(status=status)

        except Exception as e:
            self._logger.error(
                f"Failed to update voice status in channel '{self.channel.name}' "
                f"({self.channel.id}) for guild '{self.channel.guild}' "
                f"({self.channel.guild.id})", 
                exc_info=e
            )

    async def send_ws(self, payload, requester: Member = None):
        """Sends a WebSocket payload to the bot's IPC (Inter-Process Communication) system."""
        payload['guildId'] = str(self.guild.id)
        if requester:
            payload['requesterId'] = str(requester.id)
        await self._ipc_client.send(payload)

    async def _inactive_cleanup_timer_worker(self, seconds: int) -> None:
        try:
            await asyncio.sleep(seconds)
            if not self._guild or not self._node:
                return
            if self._guild.id not in self._node._players:
                return

            members = self.channel.members if self.channel else []
            has_non_bot = any(not m.bot or not m.voice.self_deaf for m in members)
            # Empty channel: always pause/teardown. If people remain: only when idle (not playing + empty queue).
            if has_non_bot and (self.is_playing or not self.queue.is_empty):
                return

            self._inactive_cleanup_task = None

            if self.settings.get("24/7", False):
                if not self.is_paused:
                    await self.set_pause(True)
            else:
                await self.teardown()
        except asyncio.CancelledError:
            return
        except Exception as e:
            # Logger is best-effort; timer cleanup should never crash the loop.
            try:
                guild_id = self._guild.id if self._guild else "unknown"
            except Exception:
                guild_id = "unknown"
            if self._logger:
                self._logger.error(
                    f"Inactive cleanup timer failed for guild {guild_id}",
                    exc_info=e
                )