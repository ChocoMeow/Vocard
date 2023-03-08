"""MIT License

Copyright (c) 2023 Vocard Development

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

import time
import function as func

from math import ceil
from asyncio import sleep
from views import InteractiveController
from typing import (
    Any,
    Dict,
    Optional
)

from discord import (
    Client,
    Guild,
    VoiceChannel,
    VoiceProtocol, 
    StageChannel,
    Member,
    Embed,
    ui
)

from discord.ext import commands
from . import events
from .enums import SearchType
from .events import VoicelinkEvent, TrackEndEvent, TrackStartEvent
from .exceptions import VoicelinkException, FilterInvalidArgument, TrackInvalidPosition, TrackLoadError, FilterTagAlreadyInUse
from .filters import Filter, Filters
from .objects import Track
from .pool import Node, NodePool
from .queue import Queue, FairQueue

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
        ctx: commands.Context = None,
    ):
        self.client = client
        self._bot = client
        self.context = ctx
        self.dj: Member = ctx.author
        self.channel = channel
        self._guild = channel.guild if channel else None

        self.settings: dict = func.get_settings(ctx.guild.id)
        self.joinTime = round(time.time())
        self._volume = self.settings.get('volume', 100)
        self.lang = self.settings.get('lang', 'EN') if self.settings.get('lang', 'EN') in func.langs else "EN"
        self.queue = eval(self.settings.get("queueType", "Queue"))(self.settings.get("maxQueue", func.max_queue), self.settings.get("duplicateTrack", True), self.get_msg)

        self._node = NodePool.get_node()
        self._current: Track = None
        self._filters: Filters = Filters()
        self._paused = False
        self._is_connected = False
        self._ping = 0.0

        self._position = 0
        self._last_position = 0
        self._last_update = 0
        self._ending_track: Optional[Track] = None

        self._voice_state = {}

        self.controller = None
        self.updating = False

        self.pause_votes = set()
        self.resume_votes = set()
        self.skip_votes = set()
        self.previous_votes = set()
        self.shuffle_votes = set()
        self.stop_votes = set()

    def __repr__(self):
        return (
            f"<Voicelink.player bot={self.bot} guildId={self.guild.id} "
            f"is_connected={self.is_connected} is_playing={self.is_playing}>"
        )

    @property
    def position(self) -> float:
        """Property which returns the player's position in a track in milliseconds"""
        current = self._current.original

        if not self.is_playing or not self._current:
            return 0

        if self.is_paused:
            return min(self._last_position, current.length)

        difference = (time.time() * 1000) - self._last_update
        position = self._last_position + difference

        if position > current.length:
            return 0

        return min(position, current.length)

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
    def current(self) -> Track:
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
    def filters(self) -> Filter:
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
        return round(self._ping / 1000, 2)
    
    def get_msg(self, mKey: str) -> str:
        return func.langs.get(self.lang, func.langs["EN"])[mKey]

    def required(self, leave=False):
        if self.settings.get('votedisable'):
            return 0

        required = ceil((len(self.channel.members) - 1) / 2.5)
        if leave:
            if len(self.channel.members) == 3:
                required = 2
        
        return required

    async def _update_state(self, data: dict):
        state: dict = data.get("state")
        self._last_update = time.time() * 1000
        self._is_connected = state.get("connected")
        self._last_position = state.get("position")
        self._ping = state.get("ping")

    async def _dispatch_voice_update(self, voice_data: Dict[str, Any]):
        if {"sessionId", "event"} != self._voice_state.keys():
            return

        await self._node.send(
            method=0, guild_id=self._guild.id,
            data = {"voice": {
                "token": voice_data['event']['token'],
                "endpoint": voice_data['event']['endpoint'],
                "sessionId": voice_data['sessionId'],
            }}
        )

    async def on_voice_server_update(self, data: dict):
        self._voice_state.update({"event": data})
        await self._dispatch_voice_update(self._voice_state)

    async def on_voice_state_update(self, data: dict):
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
        event_type = data.get("type")
        event: VoicelinkEvent = getattr(events, event_type)(data, self)

        if isinstance(event, TrackEndEvent) and event.reason != "REPLACED":
            self._current = None

        event.dispatch(self._bot)

        if isinstance(event, TrackStartEvent):
            self._ending_track = self._current

    async def do_next(self):
        if self.is_playing or not self.channel:
            return
        
        if self._paused:
            self._paused = False

        if not self.guild.me.voice:
            await self.connect(timeout=0.0, reconnect=True)
        
        self.pause_votes.clear()
        self.resume_votes.clear()
        self.skip_votes.clear()
        self.previous_votes.clear()
        self.shuffle_votes.clear()
        self.stop_votes.clear()

        track: Track = self.queue.get()

        if not track:
            if self.settings.get("autoplay", False):
                if await func.similar_track(self):
                    return await self.do_next()
        else:
            try:
                await self.play(track, start=track.position)
            except:
                await sleep(5)
                return await self.do_next()

        if self.settings.get('controller', True):
            await self.invoke_controller()
    
    async def invoke_controller(self):
        if self.updating or not self.channel:
            return
        
        self.updating = True

        if not self.controller:
            try:
                self.controller = await self.context.channel.send(embed=await self.build_embed(), view=InteractiveController(self))
            except:
                pass

        elif not await self.is_position_fresh():
            try:
                await self.controller.delete()
            except:
                ui.View.from_message(self.controller).stop()
            try:
                self.controller = await self.context.channel.send(embed= await self.build_embed(), view=InteractiveController(self))
            except:
                pass
        else:
            embed = await self.build_embed()
            if embed:
                try:
                    await self.controller.edit(embed=embed, view=InteractiveController(self))
                except:
                    pass
          
        self.updating = False

    async def build_embed(self):
        track = self.current

        if not track:
            embed=Embed(title=self.get_msg("noTrackPlaying"), description=f"[Vote](https://top.gg/bot/605618911471468554/vote/) | [Support]({func.invite_link}) | [Invite](https://discord.com/oauth2/authorize?client_id=605618911471468554&permissions=2184260928&scope=bot%20applications.commands) | [Questionnaire](https://forms.gle/UqeeEv4GEdCq9hi3A)", color=func.embed_color)
            embed.set_image(url='https://i.imgur.com/dIFBwU7.png')
            
        else:
            try:
                embed = Embed(color=func.embed_color)
                embed.set_author(name=self.get_msg("playerAuthor").format(self.channel.name), icon_url=self.client.user.avatar.url)
                embed.description = self.get_msg("playerDesc").format(track.title, track.uri, (track.requester.mention if track.requester else "<@605618911471468554>"), (f"<@&{self.settings['dj']}>" if self.settings.get('dj') else f"{self.dj.mention}"))
                embed.set_image(url=track.thumbnail if track.thumbnail else "https://cdn.discordapp.com/attachments/674788144931012638/823086668445384704/eq-dribbble.gif")
                embed.set_footer(text=self.get_msg("playerFooter").format(self.queue.count, (self.get_msg("live") if track.is_stream else func.time(track.length)), self.volume, self.get_msg("playerFooter2").format(self.queue.repeat.capitalize()) if self.queue._repeat else ""))
            except:
                embed = Embed(description=self.get_msg("missingTrackInfo"), color=func.embed_color)
        return embed

    async def is_position_fresh(self):
        try:
            async for message in self.context.channel.history(limit=5):
                if message.id == self.controller.id:
                    return True
        except:
            pass

        return False
    
    async def teardown(self):
        timeNow = round(time.time())
        func.update_settings(self.guild.id, {"lastActice": timeNow, "playTime": round(self.settings.get("playTime", 0) + ((timeNow - self.joinTime) / 60), 2)})
        
        try:
            await self.controller.delete()
        except:
            pass

        try:
            await self.destroy()
        except:
            pass
    
    async def is_privileged(self, user: Member):
        if user.id in func.bot_access_user:
            return True
        if 'dj' in self.settings and self.settings['dj']:
            return user.guild_permissions.manage_guild or (self.settings['dj'] in [role.id for role in user.roles])
        return self.dj.id == user.id or user.guild_permissions.manage_guild

    async def get_tracks(
        self,
        query: str,
        *,
        requester: Member,
        search_type: SearchType = SearchType.ytsearch
    ):
        """Fetches tracks from the node's REST api to parse into Lavalink.

        If you passed in Spotify API credentials when you created the node,
        you can also pass in a Spotify URL of a playlist, album or track and it will be parsed
        accordingly.

        You can also pass in a discord.py Context object to get a
        Context object on any track you search.
        """
        return await self._node.get_tracks(query, requester=requester, search_type=search_type)

    async def spotifySearch(self, query: str, *, requester: Member) -> list:

        try:
            tracks = await self._node._spotify_client.trackSearch(query=query)
        except:
            raise TrackLoadError("Not able to find the provided Spotify entity, is it private?")
            
        return [ Track(
                    track_id=track.id,
                    requester=requester,
                    search_type=SearchType.ytsearch,
                    spotify=True,
                    spotify_track=track,
                    info={
                        "title": track.name,
                        "author": track.artists,
                        "length": track.length,
                        "identifier": track.id,
                        "artistId": track.artistId,
                        "uri": track.uri,
                        "isStream": False,
                        "isSeekable": True,
                        "position": 0,
                        "thumbnail": track.image
                    }
                )
                for track in tracks ]

    async def spotifyRelatedTrack(self, seed_artists: str, seed_tracks: str):
        
        tracks = await self._node._spotify_client.similar_track(seed_artists=seed_artists, seed_tracks=seed_tracks)

        return [ Track(
                    track_id=track.id,
                    search_type=SearchType.ytsearch,
                    spotify=True,
                    spotify_track=track,
                    info={
                        "title": track.name,
                        "author": track.artists,
                        "length": track.length,
                        "identifier": track.id,
                        "artistId": track.artistId,
                        "uri": track.uri,
                        "isStream": False,
                        "isSeekable": True,
                        "position": 0,
                        "thumbnail": track.image
                    },
                    requester=self.client.user
                )
                for track in tracks ]

    async def connect(self, *, timeout: float, reconnect: bool, self_deaf: bool = True, self_mute: bool = False):
        await self.guild.change_voice_state(channel=self.channel, self_deaf=True, self_mute=self_mute)
        self._node._players[self.guild.id] = self
        self._is_connected = True

    async def stop(self):
        """Stops the currently playing track."""
        self._current = None
        await self._node.send(method=0, guild_id=self._guild.id, data={'encodedTrack': None})

    async def disconnect(self, *, force: bool = False):
        """Disconnects the player from voice."""
        try:
            await self.guild.change_voice_state(channel=None)
        finally:
            self.cleanup()
            self._is_connected = False
            self.channel = None

    async def destroy(self):
        """Disconnects and destroys the player, and runs internal cleanup."""
        
        try:
            await self.disconnect()
        except:
            # 'NoneType' has no attribute '_get_voice_client_key' raised by self.cleanup() ->
            # assume we're already disconnected and cleaned up
            assert self.channel is None and not self.is_connected
        
        self._node._players.pop(self.guild.id)
        await self._node.send(method=1, guild_id=self._guild.id)
        
    async def play(
        self,
        track: Track,
        *,
        start: int = 0,
        end: int = 0,
        ignore_if_playing: bool = False
    ) -> Track:
        """Plays a track. If a Spotify track is passed in, it will be handled accordingly."""
        if not self._node:
            return track

        if track.spotify:
            if not track.original:
                search: Track = (await self._node.get_tracks(
                    f"ytmsearch:{track.author} - {track.title}",
                    requester=track.requester
                ))
 
                if not search:
                    raise TrackLoadError("Can't not found a playable source!")

                track.original = search[0]
            
        data = {
            "encodedTrack": track.original.track_id if track.original else track.track_id,
            "position": str(start)
        }

        if end > 0:
            data["endTime"] = str(end)
                  
        await self._node.send(
            method=0, guild_id=self._guild.id,
            data=data,
            query=f"noReplace={ignore_if_playing}"
        )

        self._current = track

        if self.volume != 100:
            await self.set_volume(self.volume)
            
        return self._current

    async def add_track(self, raw_tracks: Union[Track, List[Track]], at_font: bool = False) -> int:
        tracks = []
        try:
            if (isList := isinstance(raw_tracks, List)):
                for track in raw_tracks:
                    self.queue.put_at_front(track) if at_font else self.queue.put(track)  
                    tracks.append(track)
            else:
                position = self.queue.put_at_front(raw_tracks) if at_font else self.queue.put(raw_tracks)
                tracks.append(raw_tracks)
        finally:
            return len(tracks) if isList else position
        
    async def seek(self, position: float) -> float:
        """Seeks to a position in the currently playing track milliseconds"""
        if position < 0 or position > self._current.original.length:
            raise TrackInvalidPosition(
                "Seek position must be between 0 and the track length"
            )

        await self._node.send(method=0, guild_id=self._guild.id, data={"position": position})
        return self._position

    async def set_pause(self, pause: bool) -> bool:
        """Sets the pause state of the currently playing track."""
        await self._node.send(method=0, guild_id=self._guild.id, data={"paused": pause})
        self._paused = pause
        return self._paused

    async def set_volume(self, volume: int) -> int:
        """Sets the volume of the player as an integer. Lavalink accepts values from 0 to 500."""
        await self._node.send(method=0, guild_id=self._guild.id, data={"volume": volume})
        self._volume = volume
        return self._volume

    async def add_filter(self, filter: Filter, fast_apply=False) -> Filters:
        try:
            self._filters.add_filter(filter=filter)
        except FilterTagAlreadyInUse:
            raise FilterTagAlreadyInUse(self.get_msg("FilterTagAlreadyInUse"))
        payload = self._filters.get_all_payloads()
        await self._node.send(method=0, guild_id=self._guild.id, data={"filters": payload})
        if fast_apply:
            await self.seek(self.position)
        return self._filters

    async def remove_filter(self, filter_tag: str, fast_apply=False) -> Filters:
        self._filters.remove_filter(filter_tag=filter_tag)
        payload = self._filters.get_all_payloads()
        await self._node.send(method=0, guild_id=self._guild.id, data={"filters": payload})
        if fast_apply:
            await self.seek(self.position)
        
        return self._filters
    
    async def reset_filter(self, *, fast_apply=False) -> None:
        if not self._filters:
            raise FilterInvalidArgument("You must have filters applied first in order to use this method.")
        self._filters.reset_filters()
        await self._node.send(method=0, guild_id=self._guild.id, data={"filters": {}})
        if fast_apply:
            await self.seek(self.position)

    async def change_node(self, identifier: str = None) -> None:
        """Change node.
        """
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

        if self.volume != 100:
            await self.set_volume(self.volume)