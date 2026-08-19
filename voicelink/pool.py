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

from . import (
    __version__
)

from .enums import SearchType, NodeAlgorithm
from .exceptions import (
    NodeConnectionFailure,
    NodeCreationError,
    NodeException,
    NodeNotAvailable,
    NoNodesAvailable,
    TrackLoadError
)
from .objects import Playlist, Track
from .resume import enable_session_resuming, websocket_headers
from .utils import ExponentialBackoff, NodeStats, NodeInfo, Ping
from .enums import RequestMethod
from .ratelimit import YTRatelimit, YTToken, STRATEGY
from .config import Config
from .health import health_store

if TYPE_CHECKING:
    from .player import Player

URL_REGEX = re.compile(
    r"https?://(?:www\.)?.+"
)

NODE_VERSION = "v4"

class Node:
    """The base class for a node. 
       This node object represents a Lavalink node.
    """

    def __init__(
        self,
        *,
        pool,
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
        logger: Optional[logging.Logger] = None
    ):
        self._bot: Bot = bot
        self._host: str = host
        self._port: int = port
        self._pool: NodePool = pool
        self._password: str = password
        self._identifier: str = identifier
        self._heartbeat: int = heartbeat
        self._secure: bool = secure
        self._logger: Optional[logging.Logger] = logger
        self._stats: Optional[NodeStats] = None

        self._websocket_uri: str = f"{'wss' if self._secure else 'ws'}://{self._host}:{self._port}/" + NODE_VERSION + "/websocket"
        self._rest_uri: str = f"{'https' if self._secure else 'http'}://{self._host}:{self._port}"

        self._session: aiohttp.ClientSession = session or aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30, connect=10)
        )
        self._websocket: aiohttp.ClientWebSocketResponse = None
        self._task: asyncio.Task = None

        self.resume_key: str = resume_key or str(os.urandom(8).hex())
        self._session_id: str = None
        self._resumable_session_id: str = None
        self._available: bool = None
        self._last_ready_resumed: bool = False
        self._ready_event: asyncio.Event = asyncio.Event()

        self._headers: Dict[str, str] = websocket_headers(
            password=self._password,
            user_id=str(bot.user.id),
            client_name=f"Voicelink/{__version__}",
        )

        self._players: Dict[int, Player] = {}
        self._info: Optional[NodeInfo] = None
        
        self.yt_ratelimit: Optional[YTRatelimit] = STRATEGY.get(yt_ratelimit.get("strategy"))(self, yt_ratelimit) if yt_ratelimit and yt_ratelimit.get("tokens") else None

        self._bot.add_listener(self._update_handler, "on_socket_response")

    def __repr__(self):
        return (
            f"<Voicelink.node ws_uri={self._websocket_uri} rest_uri={self._rest_uri} "
            f"player_count={len(self._players)}>"
        )
    
    def get_player(self, guild_id: int) -> Optional[Player]:
        """Takes a guild ID as a parameter. Returns a voicelink Player object."""
        return self._players.get(guild_id, None)
    
    def _sync_health(self, available: bool) -> None:
        version = None
        plugins = None
        if self._info:
            version = getattr(self._info.version, "semver", None)
            plugins = self._info.plugins
        health_store.record_node(
            self._identifier,
            available=available,
            version=version,
            plugins=plugins,
        )

    async def broadcast_playback_health(self, *, guild_id: int = None, playback_failure: dict = None) -> None:
        for player in self._players.copy().values():
            if guild_id is not None and getattr(player.guild, "id", None) != guild_id:
                continue
            if not getattr(player, "is_ipc_connected", False):
                continue
            payload = health_store.ipc_payload(
                guild_id=player.guild.id,
                voice_connected=player.is_connected,
                playback_failure=playback_failure if guild_id == player.guild.id else None,
            )
            await player.send_ws(payload)

    @property
    def is_connected(self) -> bool:
        """"Property which returns whether this node is connected or not"""
        return self._websocket is not None and not self._websocket.closed


    @property
    def stats(self) -> NodeStats:
        """Property which returns the node stats."""
        return self._stats

    @property
    def players(self) -> Dict[int, Player]:
        """Property which returns a dict containing the guild ID and the player object."""
        return self._players

    @property
    def bot(self) -> Bot:
        """Property which returns the discord.py client linked to this node"""
        return self._bot

    @property
    def player_count(self) -> int:
        """Property which returns how many players are connected to this node"""
        return len(self.players)

    @property
    def pool(self) -> NodePool:
        """Property which returns the pool this node is apart of"""
        return self._pool

    @property
    def latency(self) -> float:
        """Property which returns the latency of the node"""
        return Ping(self._host, port=self._port).get_ping()

    async def _update_handler(self, data: dict) -> None:
        await self._bot.wait_until_ready()

        if not data:
            return

        if data["t"] == "VOICE_SERVER_UPDATE":
            guild_id = int(data["d"]["guild_id"])
            try:
                player = self._players[guild_id]
                await player.on_voice_server_update(data["d"])
            except KeyError:
                return

        elif data["t"] == "VOICE_STATE_UPDATE":
            if int(data["d"]["user_id"]) != self._bot.user.id:
                return

            guild_id = int(data["d"]["guild_id"])
            try:
                player = self._players[guild_id]
                await player.on_voice_state_update(data["d"])
            except KeyError:
                return
            
    async def _listen(self) -> None:
        backoff = ExponentialBackoff(base=7)

        while True:
            try:
                msg = await self._websocket.receive()

                if msg.type == aiohttp.WSMsgType.CLOSED:
                    self._available = False
                    self._sync_health(False)
                    self._logger.warning(f"WebSocket closed for node [{self._identifier}]")
                    for player in self._players.copy().values():
                        suspend = getattr(player, "suspend_playback_watchdog", None)
                        if callable(suspend):
                            suspend()
                    await NodePool.broadcast_playback_health()
                    break

                elif msg.type == aiohttp.WSMsgType.ERROR:
                    self._logger.error(f"WebSocket error for node [{self._identifier}]")
                    self._available = False
                    self._sync_health(False)
                    for player in self._players.copy().values():
                        suspend = getattr(player, "suspend_playback_watchdog", None)
                        if callable(suspend):
                            suspend()
                    await NodePool.broadcast_playback_health()
                    break
                
                self._bot.loop.create_task(self._handle_payload(msg.json()))

            except aiohttp.ClientConnectionError as e:
                self._logger.error(f"Connection error: {e}")
                self._available = False
                self._sync_health(False)
                await NodePool.broadcast_playback_health()
                break
            
            except Exception as e:
                self._logger.exception(f"Unexpected error: {e}")
                self._available = False
                self._sync_health(False)
                await NodePool.broadcast_playback_health()
                break

        while not self._available:
            retry = backoff.delay()
            self._logger.info(f"Trying to reconnect node [{self._identifier}] in {round(retry)}s")
            await asyncio.sleep(retry)
            try:
                await self.connect()
            except Exception as e:
                self._logger.error(f"Reconnection failed: {e}")

    async def _handle_payload(self, data: dict) -> None:
        op = data.get("op", None)
        if not op:
            return

        if op == "ready":
            self._session_id = data.get("sessionId")
            self._last_ready_resumed = bool(data.get("resumed"))
            if self._last_ready_resumed:
                if self._session_id:
                    self._resumable_session_id = self._session_id
            elif self._session_id:
                self._resumable_session_id = self._session_id
            self._ready_event.set()
            self._bot.loop.create_task(self._enable_resuming())

        if op == "stats":
            self._stats = NodeStats(data)
            return

        if "guildId" in data:
            if not (player := self._players.get(int(data["guildId"]))):
                return

        if op == "event":
            await player._dispatch_event(data)
        elif op == "playerUpdate":
            await player._update_state(data)

    def _rest_kind(self, method: RequestMethod, query: str, data: Union[dict, str]) -> str:
        q = (query or "").lower()
        if "loadtracks" in q:
            return "LOADTRACKS"
        if q.startswith("sessions/") and "/players/" not in q:
            return "SESSION"
        if "/players/" in q:
            if method == RequestMethod.GET:
                return "PLAYER_GET"
            if method == RequestMethod.DELETE:
                return "PLAYER_DELETE"
            if method == RequestMethod.PATCH and isinstance(data, dict):
                if "encodedTrack" in data:
                    return "PLAYER_STOP" if data.get("encodedTrack") is None else "PLAYER_PLAY"
                return "PLAYER_PATCH"
        return "REST"

    def _truncate_body(self, raw: str) -> str:
        encoded = (raw or "").encode("utf-8", "replace")[:512]
        return encoded.decode("utf-8", "replace")

    async def send(
        self,
        method: RequestMethod,
        query: str,
        data: Union[dict, str] = {},
        kind: str = None,
    ) -> dict:
        if not self._available:
            raise NodeNotAvailable(f"The node '{self._identifier}' is unavailable.")
        
        uri: str = f"{self._rest_uri}/{NODE_VERSION}/{query}"
        rest_kind = kind or self._rest_kind(method, query, data)
        timeout = aiohttp.ClientTimeout(total=30, connect=10)
        try:
            async with self._session.request(
                method=method.value,
                url=uri,
                headers={"Authorization": self._password},
                json=data if not isinstance(data, str) else None,
                timeout=timeout,
            ) as resp:
                raw = await resp.text()
                if resp.status >= 300:
                    raise NodeException(
                        "Getting errors from Lavalink REST api",
                        method=method.value,
                        path=query,
                        kind=rest_kind,
                        status=resp.status,
                        body=self._truncate_body(raw),
                        node_id=self._identifier,
                    )
                
                if method == RequestMethod.DELETE:
                    if not raw:
                        return {}
                    return await resp.json(content_type=None)

                if not raw:
                    return {}
                try:
                    return await resp.json(content_type=None)
                except Exception:
                    return {}
        except NodeException:
            raise
        except asyncio.TimeoutError as exc:
            raise NodeException(
                "Lavalink REST request timed out",
                method=method.value,
                path=query,
                kind=rest_kind,
                node_id=self._identifier,
            ) from exc
        except aiohttp.ClientError as exc:
            raise NodeException(
                "Lavalink REST request failed",
                method=method.value,
                path=query,
                kind=rest_kind,
                node_id=self._identifier,
            ) from exc

    async def connect(self) -> Node:
        """Initiates a connection with a Lavalink node and adds it to the node pool."""

        try:
            if self._available:
                self._logger.info(f"Node [{self._identifier}] already connected.")
                return
            
            self._ready_event.clear()
            self._headers = websocket_headers(
                password=self._password,
                user_id=str(self._bot.user.id),
                client_name=f"Voicelink/{__version__}",
                session_id=self._resumable_session_id,
            )
            self._websocket = await self._session.ws_connect(
                self._websocket_uri, headers=self._headers, heartbeat=self._heartbeat
            )

            self._task = self._bot.loop.create_task(self._listen())
            self._available = True
            try:
                await asyncio.wait_for(self._ready_event.wait(), timeout=10)
            except asyncio.TimeoutError:
                self._logger.warning(f"Node [{self._identifier}] did not receive a ready event in time.")
            self._info = NodeInfo(await self.send(RequestMethod.GET, query="info"))
            self._sync_health(True)
            await NodePool.broadcast_playback_health()
            
            self._logger.info(f"Node [{self._identifier}] is connected!")
        
        except aiohttp.ClientConnectorError:
            raise NodeConnectionFailure(
                f"The connection to node '{self._identifier}' failed."
            )
        except aiohttp.WSServerHandshakeError:
            raise NodeConnectionFailure(
                f"The password for node '{self._identifier}' is invalid."
            )
        except aiohttp.InvalidURL:
            raise NodeConnectionFailure(
                f"The URI for node '{self._identifier}' is invalid."
            )
        
        if self.players:
            if self._last_ready_resumed:
                for player in self.players.copy().values():
                    resumed = getattr(player, "on_session_resumed", None)
                    if callable(resumed):
                        await resumed()
            else:
                await self.reconnect()

        return self

    async def _enable_resuming(self) -> None:
        try:
            if self._session_id:
                await enable_session_resuming(self, self._session_id)
        except Exception as e:
            if self._logger:
                self._logger.warning(f"Failed to enable Lavalink session resuming on [{self._identifier}]: {e}")
              
    async def disconnect(self, remove_from_pool: bool = False) -> None:
        """Disconnects a connected Lavalink node and removes it from the node pool.
           This also destroys any players connected to the node.
        """
        self._available = False
        self._sync_health(False)
        await NodePool.broadcast_playback_health()
        for player in self.players.copy().values():
            await player.teardown()
        
        await self._websocket.close()
        if remove_from_pool:
            del self._pool._nodes[self._identifier]
        self._task.cancel()
        
        self._logger.info(f"Node [{self._identifier}] is disconnected!")

    async def reconnect(self) -> None:
        await asyncio.sleep(10)
        for player in self.players.copy().values():
            await asyncio.sleep(3)
            try:
                if player._voice_state:
                    await player._dispatch_voice_update(player._voice_state)

                recover = getattr(player, "request_playback_recovery", None)
                if callable(recover):
                    await recover(resume_failed=True)
                elif player.current:
                    await player.play(track=player.current, start=min(player._last_position, player.current.length))

                    if player.is_paused:
                        await player.set_pause(True)
            except Exception:
                await player.teardown()
            await asyncio.sleep(2)

    async def build_track(
        self,
        identifier: str,
        requester: Member = None
    ) -> Track:
        """
        Builds a track using a valid track identifier

        You can also pass in a discord.py Context object to get a
        Context object on the track it builds.
        """

        data = await self.send(RequestMethod.GET, f"decodetrack?encodedTrack={identifier}")
        return Track(track_id=identifier, info=data, requester=requester)

    async def get_tracks(
        self,
        query: str,
        *,
        requester: Member,
        search_type: SearchType = None
    ) -> Union[List[Track], Playlist]:
        """
        Fetches tracks from the node's REST api to parse into Lavalink.

        You can also pass in a discord.py Context object to get a
        Context object on any track you search.
        """
        if not search_type:
            search_type = Config().search_platform
            
        if not URL_REGEX.match(query) and ':' not in query:
            query = f"{search_type}:{query}"

        response: dict[str, Any] = await self.send(RequestMethod.GET, f"loadtracks?identifier={quote(query)}")
        data = response.get("data")
        load_type = response.get("loadType")

        if not load_type:
            raise TrackLoadError("There was an error while trying to load this track.")
        
        elif load_type == "empty":
            return None

        elif load_type == "error":
            raise TrackLoadError(f"{data['message']} [{data['severity']}]")

        elif load_type in ("playlist", "recommendations"):
            return Playlist(playlist_info=data["info"], tracks=data["tracks"], requester=requester)

        elif load_type == "search":
            return [Track(track_id=track["encoded"], info=track["info"], requester=requester) for track in data]

        elif load_type == "track":
            return [Track(track_id=data["encoded"], info=data["info"], requester=requester)]
    
    async def update_refresh_yt_access_token(self, token: YTToken) -> dict:
        if not self._available:
            raise NodeNotAvailable(f"The node '{self._identifier}' is unavailable.")
        
        uri: str = f"{self._rest_uri}/youtube"
        async with self._session.request(
            method="POST",
            url=uri,
            headers={"Authorization": self._password},
            json={"refreshToken": token.token}
        ) as resp:
            if resp.status >= 300:
                raise NodeException(
                    "Getting errors from Lavalink REST api",
                    method="POST",
                    path="/youtube",
                    kind="YOUTUBE",
                    status=resp.status,
                    node_id=self._identifier,
                )

class NodePool:
    """The base class for the node pool.
       This holds all the nodes that are to be used by the bot.
    """

    _nodes: Dict[str, Node] = {}

    def __repr__(self):
        return f"<Voicelink.NodePool node_count={self.node_count}>"

    @property
    def nodes(self) -> Dict[str, Node]:
        """Property which returns a dict with the node identifier and the Node object."""
        return self._nodes

    @property
    def node_count(self) -> Optional[Node]:
        return len(self._nodes.values())
    
    @classmethod
    def get_best_node(cls, *, algorithm: NodeAlgorithm) -> Node:
        """Fetches the best node based on an NodeAlgorithm.
         This option is preferred if you want to choose the best node
         from a multi-node setup using either the node's latency
         or the node's voice region.
         Use NodeAlgorithm.BY_PING if you want to get the best node
         based on the node's latency.
         Use NodeAlgorithm.by_region if you want to get the best node
         based on the node's voice region. This method will only work
         if you set a voice region when you create a node.
         Use NodeAlgorithm.BY_PLAYERS if you want to get the best node
         based on how players it has. This method will return a node with
         the least amount of players
        """
        available_nodes = [node for node in cls._nodes.values() if node._available]

        if not available_nodes:
            raise NoNodesAvailable("There are no nodes available.")

        if algorithm == NodeAlgorithm.BY_PING:
            tested_nodes = {node: node.latency for node in available_nodes}
            return min(tested_nodes, key=tested_nodes.get)

        elif algorithm == NodeAlgorithm.BY_PLAYERS:
            tested_nodes = {node: len(node.players.keys()) for node in available_nodes}
            return min(tested_nodes, key=tested_nodes.get)

    @classmethod
    async def broadcast_playback_health(cls, *, guild_id: int = None, playback_failure: dict = None) -> None:
        for node in cls._nodes.values():
            await node.broadcast_playback_health(guild_id=guild_id, playback_failure=playback_failure)

    @classmethod
    def get_node(cls, *, identifier: str = None) -> Node:
        """Fetches a node from the node pool using it's identifier.
           If no identifier is provided, it will choose a node at random.
        """

        available_nodes = { node
            for _, node in cls._nodes.items() if node.is_connected
        }

        if identifier:
            available_nodes = { node for node in available_nodes if node._identifier == identifier }

        if not available_nodes:
            raise NoNodesAvailable("There are no nodes available.")

        nodes = {node: len(node.players.keys()) for node in available_nodes}
        return min(nodes, key=nodes.get)

    @classmethod
    async def create_node(
        cls,
        *,
        bot: Client,
        host: str,
        port: str,
        password: str,
        identifier: str,
        secure: bool = False,
        heartbeat: int = 30,
        yt_ratelimit: dict = None,
        session: Optional[aiohttp.ClientSession] = None,
        resume_key: Optional[str] = None,
        logger: Optional[logging.Logger] = None
    ) -> Node:
        """Creates a Node object to be then added into the node pool.
        """
        if identifier in cls._nodes.keys():
            raise NodeCreationError(f"A node with identifier '{identifier}' already exists.")
        
        if not logger:
            logger = logging.getLogger("vocard")
            
        node = Node(
            pool=cls, bot=bot, host=host, port=port, password=password,
            identifier=identifier, secure=secure, heartbeat=heartbeat, yt_ratelimit=yt_ratelimit,
            session=session, resume_key=resume_key, logger=logger
        )

        await node.connect()
        cls._nodes[node._identifier] = node
        return node