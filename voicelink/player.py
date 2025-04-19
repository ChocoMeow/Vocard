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

import time, logging
import function as func

from math import ceil
from asyncio import sleep
from views import InteractiveController
from typing import Any, Dict, List, Optional, Union, Tuple

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
from .enums import SearchType, LoopType, RequestMethod
from .events import VoicelinkEvent, TrackEndEvent, TrackStartEvent, TrackExceptionEvent
from .exceptions import VoicelinkException, FilterInvalidArgument, TrackInvalidPosition, FilterTagAlreadyInUse, DuplicateTrack
from .filters import Filter, Filters
from .objects import Track, Playlist
from .pool import Node, NodePool
from .queue import Queue, FairQueue
from .placeholders import Placeholders, build_embed
from random import shuffle, choice

async def connect_channel(ctx: Union[commands.Context, Interaction], channel: VoiceChannel = None):
    texts = await func.get_lang(ctx.guild.id, "noChannel", "noPermission")
    try:
        channel = channel or ctx.author.voice.channel if isinstance(ctx, commands.Context) else ctx.user.voice.channel
    except:
        raise VoicelinkException(texts[0])

    check = channel.permissions_for(ctx.guild.me)
    if check.connect == False or check.speak == False:
        raise VoicelinkException(texts[1])

    settings = await func.get_settings(channel.guild.id)
    player: Player = await channel.connect(
        cls=Player(
            ctx.bot if isinstance(ctx, commands.Context) else ctx.client,
            channel, ctx, settings
        ))

    if player.volume != 100:
        await player.set_volume(player.volume)

    if ctx.bot.ipc.is_connected:
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
        self._ipc = self._bot.ipc
        self._ipc_connection = False
        
        self.context = ctx
        self.dj: Member = ctx.user if isinstance(ctx, Interaction) else ctx.author
        self.channel: VoiceChannel = channel
        self._guild = channel.guild if channel else None

        self.settings: dict = settings
        self.joinTime: float = round(time.time())
        self._volume: int = self.settings.get('volume', 100)
        self.queue: Queue = eval(self.settings.get("queueType", "Queue"))(self.settings.get("maxQueue", func.settings.max_queue), self.settings.get("duplicateTrack", True), self.get_msg)

        self._node = NodePool.get_node()
        self._current: Optional[Track] = None
        self._filters: Filters = Filters()
        self._paused: bool = False
        self._is_connected: bool = False
        self._ping: float = 0.0
        self._track_is_stuck = False

        self._position: int = 0
        self._last_position: int = 0
        self._last_update: int = 0
        self._ending_track: Optional[Track] = None

        self._voice_state: dict = {}

        self.controller: Union[Message, PartialMessage] = None
        self._updating: bool = False

        self.pause_votes = set()
        self.resume_votes = set()
        self.skip_votes = set()
        self.previous_votes = set()
        self.shuffle_votes = set()
        self.stop_votes = set()

        self._ph = Placeholders(client, self)
        self._logger: Optional[logging.Logger] = self._node._logger

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
        return self.settings.get("autoplay", False)
    
    @property
    def data(self) -> dict:
        return {
            "guild_id": self._guild.id,
            "channel_id": self.channel.id,
            "queue": {
                "tracks": [track.data for track in self.queue._queue],
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
        return self._ipc._is_connected and self._ipc_connection
        
    def get_msg(self, *keys) -> Union[list[str], str]:
        """Retrieves a localized message or list of messages based on the given keys
           for the guild associated with this player.
        """
        return func.get_lang_non_async(self.guild.id, *keys)

    def required(self, leave=False):
        """
        Calculates the number of votes required for a specific action in the voice channel.

        If `leave` is True and the channel has three members, the requirement adjusts to 2 votes.
        """
        if self.settings.get('votedisable'):
            return 0

        required = ceil((len(self.channel.members) - 1) / 2.5)
        if leave:
            if len(self.channel.members) == 3:
                required = 2
        
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
        if user.id in func.settings.bot_access_user:
            return True
        
        manage_perm = user.guild_permissions.manage_guild
        if check_user_join and not self.is_user_join(user):
            raise VoicelinkException(self.get_msg('notInChannel').format(user.mention, self.channel.mention))
            
        if 'dj' in self.settings and self.settings['dj']:
            return manage_perm or (self.settings['dj'] in [role.id for role in user.roles])
        return self.dj.id == user.id or manage_perm
    
    def build_embed(self, current_track: Track = None):
        """Builds an embed based on the current track state."""
        controller = self.settings.get("default_controller", func.settings.controller).get("embeds", {})
        raw = controller.get("active" if current_track else "inactive", {})
        
        return build_embed(raw, self._ph)

    async def send(self, method: RequestMethod, query: str = None, data: Union[Dict, str] = {}) -> Dict:
        """Sends an HTTP request to the node with the given method, query, and data."""
        uri: str = f"sessions/{self._node._session_id}/players/{self._guild.id}" + (f"?{query}" if query else "")
        return await self._node.send(method, query=uri, data=data)
        
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

    async def _dispatch_event(self, data: dict):
        """Dispatches an event based on the type of event data received."""
        event_type = data.get("type")
        event: VoicelinkEvent = getattr(events, event_type)(data, self)

        if isinstance(event, TrackEndEvent) and event.reason != "replaced":
            self._current = None
        
        if isinstance(event, TrackExceptionEvent) and event.exception["message"] == "This content isn’t available.":
            if self._node.yt_ratelimit:
                await self._node.yt_ratelimit.flag_active_token()

        event.dispatch(self._bot)

        if isinstance(event, TrackStartEvent):
            self._ending_track = self._current

        self._logger.debug(f"Player in {self.guild.name}({self.guild.id}) dispatched event {event_type}.")

    async def do_next(self):
        """Processes the next track in the queue."""
        if self._current or self.is_playing or not self.channel:
            return
        
        if self._paused:
            self._paused = False

        if self._track_is_stuck:
            await sleep(10)
            self._track_is_stuck = False

        if not self.guild.me.voice:
            await self.connect(timeout=0.0, reconnect=True)
        
        self.pause_votes.clear()
        self.resume_votes.clear()
        self.skip_votes.clear()
        self.previous_votes.clear()
        self.shuffle_votes.clear()
        self.stop_votes.clear()

        track = self.queue.get()

        if not track:
            if self.autoplay and await self.get_recommendations():
                return await self.do_next()
        else:
            try:
                await self.play(track, start=track.position)
            except Exception as e:
                self._logger.error(f"Something went wrong while playing music in {self.guild.name}({self.guild.id})", exc_info=e)
                await sleep(5)
                return await self.do_next()

            if not track.requester.bot:
                self._bot.loop.create_task(func.update_user(track.requester.id, {
                    "$push": {"history": {"$each": [track.track_id], "$slice": -25}}
                }))

        await self.invoke_controller()
        await self.update_voice_status()

        if self.is_ipc_connected:
            await self.send_ws({
                "op": "trackUpdate", 
                "currentQueuePosition": self.queue._position if track else self.queue._position + 1,
                "trackId": track.track_id if track else None,
                "isPaused": self._paused
            })

    async def invoke_controller(self):
        """Sends or updates the music controller message in the designated channel."""
        if not self.settings.get('controller', True):
            return
        
        if self._updating or not self.channel:
            return
        
        self._updating = True

        try:            
            embed, view = self.build_embed(self.current), InteractiveController(self)
            if not self.controller:
                if request_channel_data := self.settings.get("music_request_channel"):
                    channel = self.bot.get_channel(request_channel_data.get("text_channel_id"))
                    if channel:
                        self.controller = channel.get_partial_message(request_channel_data.get("controller_msg_id"))
                        try:
                            await self.controller.edit(embed=embed, view=view)
                        except errors.NotFound:
                            self.controller = None
                
                # Send a new controller message if none exists
                if not self.controller:
                    self.controller = await self.context.channel.send(embed=embed, view=view)

            elif not await self.is_position_fresh():
                await self.controller.delete()
                self.controller = await self.context.channel.send(embed=embed, view=view)

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
        try:
            await func.update_settings(self.guild.id, {"$set": {
                "lastActice": (timeNow := round(time.time())), 
                "playTime": round(self.settings.get("playTime", 0) + ((timeNow - self.joinTime) / 60), 2)
            }})
            
            if self.is_ipc_connected:
                await self.send_ws({"op": "playerClose"})
        except:
            pass

        try:
            await self.update_voice_status(remove_status=True)
            if self.controller and self.controller.id == self.settings.get("music_request_channel", {}).get("controller_msg_id"):
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
        search_type: SearchType = SearchType.YOUTUBE
    ) -> Union[List[Track], Playlist]:
        """Fetches tracks from the node's REST api to parse into Lavalink.

        You can also pass in a discord.py Context object to get a
        Context object on any track you search.
        """
        return await self._node.get_tracks(query, requester=requester, search_type=search_type)

    async def connect(self, *, timeout: float, reconnect: bool, self_deaf: bool = True, self_mute: bool = False):
        """Connects the player to a voice channel."""
        await self.guild.change_voice_state(channel=self.channel, self_deaf=True, self_mute=self_mute)
        self._node._players[self.guild.id] = self
        self._is_connected = True

        if self.channel:
            self._logger.debug(f"Player in {self.guild.name}({self.guild.id}) has been connected to {self.channel.name}({self.channel.id}).")
            
    async def stop(self):
        """Stops the currently playing track."""
        self._current = None
        await self.send(method=RequestMethod.PATCH, data={'encodedTrack': None})

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
        
        await self.send(method=RequestMethod.PATCH, query=f"noReplace={ignore_if_playing}", data=data)
        if self._node.yt_ratelimit:
            await self._node.yt_ratelimit.handle_request()

        self._current = track

        self._logger.debug(f"Player in {self.guild.name}({self.guild.id}) playing {track.title} from uri {track.uri} with a length of {track.length}")
        return self._current

    def _validate_time(self, track: Track, start_time: int, end_time: int) -> None:
        """Validates the start and end times for a track."""
        if start_time or end_time:
            if not end_time:
                end_time = track.length

            if start_time >= end_time:
                raise VoicelinkException(self.get_msg("invalidStartTime"))

            track_length = track.length
            if not 0 <= start_time <= track_length:
                raise VoicelinkException(self.get_msg("invalidStartTime", func.time(track_length)))
            if not 0 <= end_time <= track_length:
                raise VoicelinkException(self.get_msg("invalidEndTime", func.time(track_length)))

            track.position = start_time
            track.end_time = end_time

    async def add_track(self, raw_tracks: Union[Track, List[Track]], *, start_time: int = 0, end_time: int = 0, at_front: bool = False, duplicate: bool = True) -> int:
        """Adds one or more tracks to the queue."""
        tracks: List[Track] = []
        _duplicate_tracks = [] if self.queue._allow_duplicate and duplicate else [track.uri for track in self.queue._queue]
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
                    raise DuplicateTrack(self.get_msg("voicelinkDuplicateTrack"))
                
                self._validate_time(raw_tracks, start_time, end_time)
                position = self.queue.put_at_front(raw_tracks) if at_front else self.queue.put(raw_tracks)
                tracks.append(raw_tracks)
                
        finally:
            if tracks:
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
            raise VoicelinkException(self.get_msg('shuffleError'))
        
        shuffle(replacement)
        self.queue.replace(queue_type, replacement)
        self.shuffle_votes.clear()
        if self.is_ipc_connected:
            await self.send_ws({
                "op": "shuffleTrack",
                "tracks": [{"trackId": track.track_id, "requesterId": str(track.requester.id)} for track in replacement],
                "queueType": queue_type
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
            raise FilterTagAlreadyInUse(self.get_msg("FilterTagAlreadyInUse"))
        
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
            await self.play(self.current, start=self.position)
            self._last_update = time.time() * 1000

            if self.is_paused:
                await self.set_pause(True)
    
    async def get_recommendations(self, *, track: Optional[Track] = None) -> bool:
        """Get recommendations from Youtube or Spotify."""
        if not track:
            try:
                track = choice(self.queue.history(incTrack=True)[-5:])
            except IndexError:
                return False
            
        tracks = await self._node.get_recommendations(track)
        if tracks:
            await self.add_track(tracks, duplicate=False)
            
            self._logger.debug(f"Player in {self.guild.name}({self.guild.id}) has been requested recommendations.")
            return True
        return False
    
    async def update_voice_status(self, remove_status: bool = False) -> None:
        """Updates the voice status of the channel based on the specified template."""
        template = self.settings.get("stage_announce_template", func.settings.voice_status_template)
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
        await self.bot.ipc.send(payload)