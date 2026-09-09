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

import asyncio
import os
import re
import aiohttp
import logging

from discord import Client, Member
from discord.ext.commands import Bot
from typing import Dict, Optional, Union, List, Any, TYPE_CHECKING
from urllib.parse import quote

from . import __version__
from .enums import SearchType, NodeAlgorithm, RequestMethod, ReconnectStrategy
from .exceptions import (
    NodeConnectionFailure,
    NodeCreationError,
    NodeException,
    NodeNotAvailable,
    NoNodesAvailable,
    TrackLoadError
)
from .objects import Playlist, Track
from .utils import ExponentialBackoff, NodeStats, NodeInfo, Ping, NodeTimeouts
from .ratelimit import YTRatelimit, YTToken, STRATEGY
from .config import Config

if TYPE_CHECKING:
    from .player import Player

URL_REGEX = re.compile(r"https?://(?:www\.)?.+")
NODE_VERSION = "v4"


class Node:
    """The base class for a node. Represents a Lavalink node."""

    def __init__(
        self,
        *,
        pool: "NodePool",
        bot: Bot,
        host: str,
        port: int,
        password: str,
        identifier: str,
        secure: bool = False,
        heartbeat: int = 30,
        yt_ratelimit: dict = None,
        session: Optional[aiohttp.ClientSession] = None,
        resume_key: Optional[str] = None,
        logger: Optional[logging.Logger] = None,
        reconnect_strategy: ReconnectStrategy = ReconnectStrategy.TRY_ONCE,
        timeouts: Optional[Union[NodeTimeouts, Dict[str, int]]] = None,
    ):
        self._bot: Bot = bot
        self._host: str = host
        self._port: int = port
        self._pool: "NodePool" = pool
        self._password: str = password
        self._identifier: str = identifier
        self._heartbeat: int = heartbeat
        self._secure: bool = secure
        self._logger: logging.Logger = logger or logging.getLogger("vocard")
        self._stats: Optional[NodeStats] = None
        self._reconnect_strategy: ReconnectStrategy = reconnect_strategy
        self._timeouts: NodeTimeouts = NodeTimeouts.from_value(timeouts)

        self._websocket_uri: str = f"{'wss' if secure else 'ws'}://{host}:{port}/{NODE_VERSION}/websocket"
        self._rest_uri: str = f"{'https' if secure else 'http'}://{host}:{port}"

        self._session: aiohttp.ClientSession = session or aiohttp.ClientSession()
        self._websocket: Optional[aiohttp.ClientWebSocketResponse] = None
        self._task: Optional[asyncio.Task] = None
        self._ping_task: Optional[asyncio.Task] = None
        self._tasks: set[asyncio.Task] = set()  # keeps refs to fire-and-forget payload tasks so errors aren't lost
        self._closing: bool = False  # set by disconnect() so _listen doesn't try to auto-reconnect

        self.resume_key: str = resume_key or str(os.urandom(8).hex())
        self._session_id: Optional[str] = None
        self._available: bool = False
        self._latency: float = float("inf")  # refreshed by _ping_loop; inf until first measurement

        self._headers: Dict[str, str] = {
            "Authorization": password,
            "User-Id": str(bot.user.id),
            "Client-Name": f"Voicelink/{__version__}",
            "Resume-Key": self.resume_key,
        }

        self._players: Dict[int, "Player"] = {}
        self._info: Optional[NodeInfo] = None
        self.yt_ratelimit: Optional[YTRatelimit] = (
            STRATEGY.get(yt_ratelimit.get("strategy"))(self, yt_ratelimit)
            if yt_ratelimit and yt_ratelimit.get("tokens") else None
        )

        self._bot.add_listener(self._update_handler, "on_socket_response")

    def __repr__(self):
        return (
            f"<Voicelink.node ws_uri={self._websocket_uri} rest_uri={self._rest_uri} "
            f"player_count={len(self._players)}>"
        )

    def get_player(self, guild_id: int) -> Optional["Player"]:
        """Returns the Player for a guild ID, if one exists on this node."""
        return self._players.get(guild_id)

    @property
    def is_connected(self) -> bool:
        return self._websocket is not None and not self._websocket.closed

    @property
    def stats(self) -> Optional[NodeStats]:
        return self._stats

    @property
    def players(self) -> Dict[int, "Player"]:
        return self._players

    @property
    def bot(self) -> Bot:
        return self._bot

    @property
    def player_count(self) -> int:
        return len(self._players)

    @property
    def pool(self) -> "NodePool":
        return self._pool

    @property
    def latency(self) -> float:
        """Cached round-trip latency to the node, refreshed roughly every heartbeat."""
        return self._latency

    async def _ping_loop(self) -> None:
        while True:
            try:
                self._latency = await self._bot.loop.run_in_executor(
                    None, lambda: Ping(self._host, port=self._port).get_ping()
                )
            except Exception:
                self._logger.debug(f"Latency check failed for node [{self._identifier}]")
            await asyncio.sleep(self._heartbeat)

    async def _update_handler(self, data: dict) -> None:
        await self._bot.wait_until_ready()
        if not data:
            return

        event_type, payload = data.get("t"), data.get("d")
        if event_type is None or payload is None:
            return

        if event_type == "VOICE_SERVER_UPDATE":
            guild_id = payload.get("guild_id")
            if guild_id is not None and (player := self._players.get(int(guild_id))):
                await player.on_voice_server_update(payload)

        elif event_type == "VOICE_STATE_UPDATE":
            if int(payload.get("user_id", 0)) != self._bot.user.id:
                return
            guild_id = payload.get("guild_id")
            if guild_id is not None and (player := self._players.get(int(guild_id))):
                await player.on_voice_state_update(payload)

    async def _connect_websocket(self) -> None:
        """Handshake + fetch node info. Raises and leaves the node unavailable on failure."""
        try:
            self._websocket = await self._session.ws_connect(
                self._websocket_uri, headers=self._headers,
                heartbeat=self._heartbeat, timeout=self._timeouts.ws_handshake_timeout,
            )
        except aiohttp.ClientConnectorError as exc:
            raise NodeConnectionFailure(f"The connection to node '{self._identifier}' failed.") from exc
        except aiohttp.WSServerHandshakeError as exc:
            raise NodeConnectionFailure(f"The password for node '{self._identifier}' is invalid.") from exc
        except aiohttp.InvalidURL as exc:
            raise NodeConnectionFailure(f"The URI for node '{self._identifier}' is invalid.") from exc

        self._available = True  # send() requires this; rolled back below if the info call fails
        try:
            self._info = NodeInfo(await self.send(RequestMethod.GET, query="info"))
        except Exception:
            self._available = False
            if self._websocket and not self._websocket.closed:
                await self._websocket.close()
            self._websocket = None
            raise

    async def connect(self) -> "Node":
        """Connects to the Lavalink node. Safe to call again after a disconnect."""
        if self._available:
            self._logger.info(f"Node [{self._identifier}] already connected.")
            return self

        self._closing = False
        await self._connect_websocket()

        if self._task is None or self._task.done():
            self._task = self._bot.loop.create_task(self._listen())
        if self._ping_task is None or self._ping_task.done():
            self._ping_task = self._bot.loop.create_task(self._ping_loop())

        self._logger.info(f"Node [{self._identifier}] is connected!")

        if self._players:
            await self._reattach_players()

        return self

    async def disconnect(self, remove_from_pool: bool = False) -> None:
        """Disconnects the node, tearing down any players attached to it."""
        self._closing = True
        self._available = False

        for player in list(self._players.values()):
            try:
                await player.teardown()
            except Exception:
                self._logger.exception(f"Error tearing down a player on node [{self._identifier}]")

        if self._websocket and not self._websocket.closed:
            await self._websocket.close()

        for task in (self._task, self._ping_task):
            if task and not task.done():
                task.cancel()

        self._bot.remove_listener(self._update_handler, "on_socket_response")

        if remove_from_pool:
            self._pool.remove_node(self._identifier)

        self._logger.info(f"Node [{self._identifier}] is disconnected!")

    async def _listen(self) -> None:
        """Owns this node's socket for its whole lifetime, including reconnects."""
        backoff = ExponentialBackoff(base=7)

        while True:
            await self._receive_loop()

            if self._closing:
                return

            if not self._reconnect_strategy.reconnect_on_drop:
                self._logger.warning(
                    f"Node [{self._identifier}] disconnected. "
                    f"Reconnect strategy is {self._reconnect_strategy}, not reconnecting."
                )
                return

            if not await self._reconnect(backoff):
                return
            backoff = ExponentialBackoff(base=7)

    async def _receive_loop(self) -> None:
        while True:
            try:
                msg = await self._websocket.receive()
            except asyncio.CancelledError:
                raise
            except (aiohttp.ClientConnectionError, ConnectionResetError, OSError) as exc:
                self._logger.error(f"Connection error on node [{self._identifier}]: {exc}")
                self._available = False
                return
            except Exception:
                self._logger.exception(f"Unexpected error receiving from node [{self._identifier}]")
                self._available = False
                return

            if msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.CLOSING):
                self._available = False
                self._logger.warning(f"WebSocket for node [{self._identifier}] closed")
                return

            if msg.type == aiohttp.WSMsgType.ERROR:
                self._available = False
                self._logger.error(f"WebSocket error for node [{self._identifier}]: {self._websocket.exception()}")
                return

            if msg.type in (aiohttp.WSMsgType.PING, aiohttp.WSMsgType.PONG):
                continue

            if msg.type not in (aiohttp.WSMsgType.TEXT, aiohttp.WSMsgType.BINARY):
                continue

            try:
                data = msg.json()
            except ValueError as exc:
                self._logger.warning(f"Bad payload from node [{self._identifier}]: {exc}")
                continue

            task = self._bot.loop.create_task(self._handle_payload(data))
            self._tasks.add(task)
            task.add_done_callback(self._on_payload_task_done)

    def _on_payload_task_done(self, task: asyncio.Task) -> None:
        self._tasks.discard(task)
        if not task.cancelled() and (exc := task.exception()):
            self._logger.error(f"Unhandled error processing payload on node [{self._identifier}]", exc_info=exc)

    async def _reconnect(self, backoff: ExponentialBackoff) -> bool:
        while not self._available:
            if self._closing:
                return False

            retry = backoff.delay()
            self._logger.info(f"Trying to reconnect node [{self._identifier}] in {round(retry)}s")
            await asyncio.sleep(retry)
            if self._closing:
                return False

            try:
                await self._connect_websocket()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self._logger.error(f"Reconnection attempt failed for node [{self._identifier}]: {exc}")
                continue

            self._logger.info(f"Node [{self._identifier}] reconnected successfully.")
            if self._players:
                await self._reattach_players()
            return True
        return True

    async def _handle_payload(self, data: dict) -> None:
        op = data.get("op")
        if op == "ready":
            self._session_id = data.get("sessionId")
            self._logger.info(f"Node [{self._identifier}] ready (session_id={self._session_id})")
            return

        if op == "stats":
            self._stats = NodeStats(data)
            return

        if op not in ("event", "playerUpdate"):
            return

        guild_id = data.get("guildId")
        if guild_id is None:
            return

        try:
            player = self._players.get(int(guild_id))
        except (TypeError, ValueError):
            self._logger.warning(f"Malformed guildId {guild_id!r} from node [{self._identifier}]")
            return

        if player is None:
            return

        try:
            if op == "event":
                await player._dispatch_event(data)
            else:
                await player._update_state(data)
        except Exception:
            self._logger.exception(f"Error handling '{op}' for guild {guild_id} on node [{self._identifier}]")

    async def send(self, method: RequestMethod, query: str, data: Optional[Union[dict, str]] = None) -> Optional[dict]:
        if not self._available:
            raise NodeNotAvailable(f"The node '{self._identifier}' is unavailable.")

        uri = f"{self._rest_uri}/{NODE_VERSION}/{query}"
        try:
            async with self._session.request(
                method=method.value, url=uri, headers={"Authorization": self._password},
                json=data or {}, timeout=aiohttp.ClientTimeout(total=self._timeouts.rest_request_timeout),
            ) as resp:
                if resp.status == 204:  # e.g. LavaLyrics with no results
                    return None
                if resp.status >= 300:
                    body = await resp.text()
                    raise NodeException(f"Lavalink REST call failed ({resp.status}) for '{query}': {body[:300]}")
                if method == RequestMethod.DELETE:
                    return await resp.json(content_type=None)
                return await resp.json()
        except asyncio.TimeoutError as exc:
            raise NodeException(f"Request to node [{self._identifier}] timed out for '{query}'") from exc
        except aiohttp.ClientError as exc:
            raise NodeException(f"Request to node [{self._identifier}] failed for '{query}': {exc}") from exc

    async def _reattach_players(self) -> None:
        """Restores voice state and resumes playback for every player after a (re)connect."""
        await asyncio.sleep(self._timeouts.reattach_initial_delay)
        for player in list(self._players.values()):
            await asyncio.sleep(self._timeouts.reattach_per_player_delay)
            try:
                if player._voice_state:
                    await player._dispatch_voice_update(player._voice_state)
                if player.current:
                    await player.play(track=player.current, start=min(player._last_position, player.current.length))
                    if player.is_paused:
                        await player.set_pause(True)
            except asyncio.CancelledError:
                raise
            except Exception:
                self._logger.exception(f"Failed to restore a player on node [{self._identifier}]; tearing down.")
                await player.teardown()
            await asyncio.sleep(self._timeouts.reattach_settle_delay)

    async def build_track(self, identifier: str, requester: Member = None) -> Track:
        """Builds a Track from a valid encoded track identifier."""
        data = await self.send(RequestMethod.GET, f"decodetrack?encodedTrack={identifier}")
        return Track(track_id=identifier, info=data, requester=requester)

    async def get_tracks(
        self, query: str, *, requester: Member, search_type: SearchType = None
    ) -> Union[List[Track], Playlist, None]:
        """Fetches tracks from the node's REST API for a query or URL."""
        search_type = search_type or Config().search_platform
        if not URL_REGEX.match(query) and ":" not in query:
            query = f"{search_type}:{query}"

        response: Dict[str, Any] = await self.send(RequestMethod.GET, f"loadtracks?identifier={quote(query)}")
        data, load_type = response.get("data"), response.get("loadType")

        if not load_type:
            raise TrackLoadError("There was an error while trying to load this track.")
        if load_type == "empty":
            return None
        if load_type == "error":
            raise TrackLoadError(f"{data['message']} [{data['severity']}]")
        if load_type in ("playlist", "recommendations"):
            return Playlist(playlist_info=data["info"], tracks=data["tracks"], requester=requester)
        if load_type == "search":
            return [Track(track_id=t["encoded"], info=t["info"], requester=requester) for t in data]
        if load_type == "track":
            return [Track(track_id=data["encoded"], info=data["info"], requester=requester)]

        raise TrackLoadError(f"Unknown loadType '{load_type}' returned by node [{self._identifier}].")

    async def update_refresh_yt_access_token(self, token: YTToken) -> Optional[dict]:
        if not self._available:
            raise NodeNotAvailable(f"The node '{self._identifier}' is unavailable.")

        try:
            async with self._session.request(
                method="POST", url=f"{self._rest_uri}/youtube",
                headers={"Authorization": self._password}, json={"refreshToken": token.token},
                timeout=aiohttp.ClientTimeout(total=self._timeouts.rest_request_timeout),
            ) as resp:
                if resp.status >= 300:
                    body = await resp.text()
                    raise NodeException(f"Failed to refresh YT token ({resp.status}): {body[:300]}")
                if resp.status == 204:
                    return None
                return await resp.json(content_type=None)
        except asyncio.TimeoutError as exc:
            raise NodeException(f"YT token refresh on node [{self._identifier}] timed out") from exc
        except aiohttp.ClientError as exc:
            raise NodeException(f"YT token refresh on node [{self._identifier}] failed: {exc}") from exc


class NodePool:
    """Holds all Lavalink nodes used by the bot."""

    _nodes: Dict[str, Node] = {}

    def __repr__(self):
        return f"<Voicelink.NodePool node_count={self.node_count}>"

    @property
    def nodes(self) -> Dict[str, Node]:
        return self._nodes

    @property
    def node_count(self) -> int:
        return len(self._nodes)

    @classmethod
    def remove_node(cls, identifier: str) -> None:
        cls._nodes.pop(identifier, None)

    @classmethod
    def get_best_node(cls, *, algorithm: NodeAlgorithm) -> Node:
        """Picks the best available node by ping latency or player count."""
        available = [n for n in cls._nodes.values() if n._available]
        if not available:
            raise NoNodesAvailable("There are no nodes available.")

        if algorithm == NodeAlgorithm.BY_PING:
            return min(available, key=lambda n: n.latency)
        if algorithm == NodeAlgorithm.BY_PLAYERS:
            return min(available, key=lambda n: len(n.players))

        raise ValueError(f"Unsupported NodeAlgorithm: {algorithm!r}")

    @classmethod
    def get_node(cls, *, identifier: str = None) -> Node:
        """Fetches the least-loaded connected node, optionally by identifier."""
        candidates = [n for n in cls._nodes.values() if n.is_connected]
        if identifier:
            candidates = [n for n in candidates if n._identifier == identifier]
        if not candidates:
            raise NoNodesAvailable("There are no nodes available.")
        return min(candidates, key=lambda n: len(n.players))

    @classmethod
    async def create_node(
        cls, *, bot: Client, host: str, port: str, password: str, identifier: str,
        secure: bool = False, heartbeat: int = 30, yt_ratelimit: dict = None,
        session: Optional[aiohttp.ClientSession] = None, resume_key: Optional[str] = None,
        logger: Optional[logging.Logger] = None,
        reconnect_strategy: Union[str, ReconnectStrategy] = ReconnectStrategy.RECONNECT_ON_DROP,
        timeouts: Optional[Union[NodeTimeouts, Dict[str, int]]] = None,
    ) -> Node:
        """Creates a Node, connects it (retrying per the reconnect strategy), and adds it to the pool."""
        if identifier in cls._nodes:
            raise NodeCreationError(f"A node with identifier '{identifier}' already exists.")

        logger = logger or logging.getLogger("vocard")
        strategy = ReconnectStrategy.from_value(reconnect_strategy)
        max_retries = strategy.max_startup_retries
        backoff = ExponentialBackoff(base=7) if max_retries != 1 else None

        node = Node(
            pool=cls, bot=bot, host=host, port=port, password=password, identifier=identifier,
            secure=secure, heartbeat=heartbeat, yt_ratelimit=yt_ratelimit, session=session,
            resume_key=resume_key, logger=logger, reconnect_strategy=strategy,
            timeouts=timeouts,
        )

        attempt = 0
        last_error: Optional[Exception] = None
        while True:
            attempt += 1
            try:
                await node.connect()
                cls._nodes[identifier] = node
                return node
            except Exception as e:
                last_error = e
                if max_retries is not None and attempt >= max_retries:
                    break
                retry = backoff.delay()
                logger.warning(
                    f"Node [{identifier}] failed to connect "
                    f"({attempt}/{max_retries or 'inf'}): {e}. Retrying in {round(retry)}s..."
                )
                await asyncio.sleep(retry)

        bot.remove_listener(node._update_handler, "on_socket_response")
        raise last_error