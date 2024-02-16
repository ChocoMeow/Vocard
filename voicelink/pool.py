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

from discord import Client, Member
from discord.ext.commands import Bot
from typing import Dict, Optional, TYPE_CHECKING, Union, List
from urllib.parse import quote

from . import (
    __version__, 
    spotify,
)

from .enums import SearchType, NodeAlgorithm
from .exceptions import (
    InvalidSpotifyClientAuthorization,
    NodeConnectionFailure,
    NodeCreationError,
    NodeException,
    NodeNotAvailable,
    NoNodesAvailable,
    TrackLoadError
)
from .objects import Playlist, Track
from .utils import ExponentialBackoff, NodeStats, Ping

if TYPE_CHECKING:
    from .player import Player

SPOTIFY_URL_REGEX = re.compile(
    r"https?://open.spotify.com/(?P<type>album|playlist|track|artist)/(?P<id>[a-zA-Z0-9]+)"
)

DISCORD_MP3_URL_REGEX = re.compile(
    r"https?://cdn.discordapp.com/attachments/(?P<channel_id>[0-9]+)/"
    r"(?P<message_id>[0-9]+)/(?P<file>[a-zA-Z0-9_.]+)+"
)

URL_REGEX = re.compile(
    r"https?://(?:www\.)?.+"
)

NODE_VERSION = "v4"
CALL_METHOD = ["PATCH", "DELETE"]

class Node:
    """The base class for a node. 
       This node object represents a Lavalink node. 
       To enable Spotify searching, pass in a proper Spotify Client ID and Spotify Client Secret
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
        session: Optional[aiohttp.ClientSession] = None,
        spotify_client_id: Optional[str] = None,
        spotify_client_secret: Optional[str] = None,
        resume_key: Optional[str] = None

    ):
        self._bot: Bot = bot
        self._host: str = host
        self._port: int = port
        self._pool: NodePool = pool
        self._password: str = password
        self._identifier: str = identifier
        self._heartbeat: int = heartbeat
        self._secure: bool = secure
       
        self._websocket_uri: str = f"{'wss' if self._secure else 'ws'}://{self._host}:{self._port}/" + NODE_VERSION + "/websocket"
        self._rest_uri: str = f"{'https' if self._secure else 'http'}://{self._host}:{self._port}"

        self._session: aiohttp.ClientSession = session or aiohttp.ClientSession()
        self._websocket: aiohttp.ClientWebSocketResponse = None
        self._task: asyncio.Task = None

        self.resume_key: str = resume_key or str(os.urandom(8).hex())
        self._session_id: str = None
        self._available: bool = None

        self._headers: Dict[str, str] = {
            "Authorization": self._password,
            "User-Id": str(bot.user.id),
            "Client-Name": f"Voicelink/{__version__}",
            'Resume-Key': self.resume_key
        }

        self._players: Dict[int, Player] = {}

        self._spotify_client_id: Optional[str] = spotify_client_id
        self._spotify_client_secret: Optional[str] = spotify_client_secret
        self._spotify_client: Optional[spotify.Client] = None
        
        self._bot.add_listener(self._update_handler, "on_socket_response")

    def __repr__(self):
        return (
            f"<Voicelink.node ws_uri={self._websocket_uri} rest_uri={self._rest_uri} "
            f"player_count={len(self._players)}>"
        )
    
    @property
    def spotify_client(self) -> Optional[spotify.Client]:
        if not self._spotify_client:
            if not self._spotify_client_id or not self._spotify_client_secret:
                return None
            
            self._spotify_client = spotify.Client(
                self._spotify_client_id, self._spotify_client_secret
            )

        return self._spotify_client
    
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
        #await self._bot.wait_until_ready()

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
            except:
                break
            if msg.type == aiohttp.WSMsgType.CLOSED:
                self._available = False

                retry = backoff.delay()
                print(f"Trying to reconnect {self._identifier} with {round(retry)}s")
                await asyncio.sleep(retry)
                if not self.is_connected:
                    try:
                        await self.connect()
                    except:
                        pass
            else:
                self._bot.loop.create_task(self._handle_payload(msg.json()))

    async def _handle_payload(self, data: dict) -> None:
        op = data.get("op", None)
        if not op:
            return

        if op == "ready":
            self._session_id = data.get("sessionId")

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

    async def send(
        self, method: int, 
        guild_id: Union[str, int] = None, 
        query: str = None, 
        data: Union[dict, str] = {}
    ) -> dict:
        if not self._available:
            raise NodeNotAvailable(f"The node '{self._identifier}' is unavailable.")
        
        uri: str = f"{self._rest_uri}/{NODE_VERSION}" \
                   f"/sessions/{self._session_id}/players" \
                   f"/{guild_id}" if guild_id else "" \
                   f"?{query}" if query else ""
        
        async with self._session.request(
            method=CALL_METHOD[method],
            url=uri,
            headers={"Authorization": self._password},
            json=data
        ) as resp:
            if resp.status >= 300:
                raise NodeException(f"Getting errors from Lavalink REST api")
            
            if method == CALL_METHOD[1]:
                return await resp.json(content_type=None)

            return await resp.json()
        
    def get_player(self, guild_id: int) -> Optional[Player]:
        """Takes a guild ID as a parameter. Returns a voicelink Player object."""
        return self._players.get(guild_id, None)

    async def connect(self) -> Node:
        """Initiates a connection with a Lavalink node and adds it to the node pool."""

        try:
            self._websocket = await self._session.ws_connect(
                self._websocket_uri, headers=self._headers, heartbeat=self._heartbeat
            )

            self._task = self._bot.loop.create_task(self._listen())
            self._available = True

            print(f"{self._identifier} is connected!")
        
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
            await self.reconnect()

        return self
              
    async def disconnect(self) -> None:
        """Disconnects a connected Lavalink node and removes it from the node pool.
           This also destroys any players connected to the node.
        """
        for player in self.players.copy().values():
            await player.teardown()
        
        if self.spotify_client:
            await self.spotify_client.close()

        await self._websocket.close()
        del self._pool._nodes[self._identifier]
        self._available = False
        self._task.cancel()

    async def reconnect(self) -> None:
        await asyncio.sleep(10)
        for player in self.players.copy().values():
            try:
                if player._voice_state:
                    await player._dispatch_voice_update(player._voice_state)

                if player.current:
                    await player.play(track=player.current, start=min(player._last_position, player.current.length))

                    if player.is_paused:
                        await player.set_pause(True)
            except:
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

        async with self._session.get(
            f"{self._rest_uri}/" + NODE_VERSION + "/decodetrack?",
            headers={"Authorization": self._password},
            params={"track": identifier}
        ) as resp:
            if not resp.status == 200:
                raise TrackLoadError(
                    f"Failed to build track. Check if the identifier is correct and try again."
                )

            data: dict = await resp.json()
            return Track(track_id=identifier, info=data, requester=requester)

    async def get_tracks(
        self,
        query: str,
        *,
        requester: Member,
        search_type: SearchType = SearchType.ytsearch
    ) -> Union[List[Track], Playlist]:
        """Fetches tracks from the node's REST api to parse into Lavalink.

           If you passed in Spotify API credentials, you can also pass in a
           Spotify URL of a playlist, album or track and it will be parsed accordingly.

           You can also pass in a discord.py Context object to get a
           Context object on any track you search.
        """

        if not URL_REGEX.match(query) and not re.match(r"(?:ytm?|sc)search:.", query):
            query = f"{search_type}:{query}"

        if SPOTIFY_URL_REGEX.match(query):
            try:
                if not self.spotify_client:
                    raise InvalidSpotifyClientAuthorization(
                    "You did not provide proper Spotify client authorization credentials. "
                    "If you would like to use the Spotify searching feature, "
                    "please obtain Spotify API credentials here: https://developer.spotify.com/"
                )

                spotify_results = await self.spotify_client.search(query=query)
            except Exception as _:
                raise TrackLoadError("Not able to find the provided Spotify entity, is it private?")
                
            if isinstance(spotify_results, spotify.Track):
                return [
                    Track(
                        track_id=None,
                        info=spotify_results.to_dict(),
                        requester=requester,
                        search_type=search_type,
                        spotify_track=spotify_results,
                    )
                ]

            tracks = [
                Track(
                    track_id=None,
                    info=track.to_dict(),
                    requester=requester,
                    search_type=search_type,
                    spotify_track=track,
                ) for track in spotify_results.tracks if track.uri
            ]

            return Playlist(
                playlist_info={"name": spotify_results.name, "selectedTrack": 0},
                tracks=tracks,
                requester=requester,
                spotify=True,
                spotify_playlist=spotify_results
            )

        elif discord_url := DISCORD_MP3_URL_REGEX.match(query):
            async with self._session.get(
                url=f"{self._rest_uri}/" + NODE_VERSION + f"/loadtracks?identifier={quote(query)}",
                headers={"Authorization": self._password}
            ) as response:
                data: dict = await response.json()

            try:
                track: dict = data["tracks"][0]
                info: dict = track.get("info")
            except:
                raise TrackLoadError("Not able to find the provided track.")

            return [
                Track(
                    track_id=None,
                    info={
                        "title": discord_url.group("file"),
                        "author": "Unknown",
                        "length": info.get("length"),
                        "uri": info.get("uri"),
                        "position": info.get("position"),
                        "identifier": info.get("identifier")
                    },
                    requester=requester
                )
            ]

        else:
            async with self._session.get(
                url=f"{self._rest_uri}/" + NODE_VERSION + f"/loadtracks?identifier={quote(query)}",
                headers={"Authorization": self._password}
            ) as response:
                data = await response.json()

        load_type = data.get("loadType")

        if not load_type:
            raise TrackLoadError("There was an error while trying to load this track.")

        elif load_type == "error":
            exception = data["data"]
            raise TrackLoadError(f"{exception['message']} [{exception['severity']}]")

        elif load_type == "empty":
            return None

        elif load_type == "playlist":
            data = data.get("data")
            
            return Playlist(
                playlist_info=data["info"],
                tracks=data["tracks"],
                requester=requester
            )

        elif load_type == "search":
            return [
                Track(
                    track_id=track["encoded"],
                    info=track["info"],
                    requester=requester
                )
                for track in data["data"]
            ]

        elif load_type == "track":
            track = data["data"]
            return [
                Track(
                    track_id=track["encoded"],
                    info=track["info"],
                    requester=requester
                )
            ]
    
    async def spotifySearch(self, query: str, *, requester: Member) -> Optional[List[Track]]:
        try:
            if not self.spotify_client:
                raise InvalidSpotifyClientAuthorization(
                "You did not provide proper Spotify client authorization credentials. "
                "If you would like to use the Spotify searching feature, "
                "please obtain Spotify API credentials here: https://developer.spotify.com/"
            )
                
            tracks = await self._spotify_client.trackSearch(query=query)
        except Exception as _:
            raise TrackLoadError("Not able to find the provided Spotify entity, is it private?")
            
        return [ 
            Track(
                track_id=None,
                requester=requester,
                search_type=SearchType.ytsearch,
                spotify_track=track,
                info=track.to_dict()
            )
            for track in tracks ]

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
         Use NodeAlgorithm.by_ping if you want to get the best node
         based on the node's latency.
         Use NodeAlgorithm.by_region if you want to get the best node
         based on the node's voice region. This method will only work
         if you set a voice region when you create a node.
         Use NodeAlgorithm.by_players if you want to get the best node
         based on how players it has. This method will return a node with
         the least amount of players
        """
        available_nodes = [node for node in cls._nodes.values() if node._available]

        if not available_nodes:
            raise NoNodesAvailable("There are no nodes available.")

        if algorithm == NodeAlgorithm.by_ping:
            tested_nodes = {node: node.latency for node in available_nodes}
            return min(tested_nodes, key=tested_nodes.get)

        elif algorithm == NodeAlgorithm.by_players:
            tested_nodes = {node: len(node.players.keys()) for node in available_nodes}
            return min(tested_nodes, key=tested_nodes.get)

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
        spotify_client_id: Optional[str] = None,
        spotify_client_secret: Optional[str] = None,
        session: Optional[aiohttp.ClientSession] = None,
        resume_key: Optional[str] = None,
    ) -> Node:
        """Creates a Node object to be then added into the node pool.
           For Spotify searching capabilites, pass in valid Spotify API credentials.
        """
        if identifier in cls._nodes.keys():
            raise NodeCreationError(f"A node with identifier '{identifier}' already exists.")

        node = Node(
            pool=cls, bot=bot, host=host, port=port, password=password,
            identifier=identifier, secure=secure, heartbeat=heartbeat, spotify_client_id=spotify_client_id, 
            session=session, spotify_client_secret=spotify_client_secret,
            resume_key=resume_key
        )

        await node.connect()
        cls._nodes[node._identifier] = node
        return node