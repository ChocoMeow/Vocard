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

import discord
import re
import voicelink
import traceback

from discord.ext import commands
from typing import Optional, Dict, Type, Union, Any

from ..config import Config
from ..utils import format_ms, send_localized_message
from ..language import LangHandler
from ..mongodb import MongoDBHandler
    
def key(interaction: discord.Interaction):
    return interaction.user

class ButtonOnCooldown(commands.CommandError):
    def __init__(self, retry_after: float) -> None:
        self.retry_after = retry_after
        
class ControlButton(discord.ui.Button):
    def __init__(
        self,
        player: "voicelink.Player",
        btn_data: Dict[str, Any],
        default_states: Optional[str] = None,
        **kwargs
    ):
        super().__init__(**kwargs)

        self.player: voicelink.Player = player
        self.btn_data: Dict[str, Any] = btn_data
        self.change_states(default_states)

    def _get_button_config(self, states: Optional[str]) -> Dict[str, Any]:
        """Retrieve button configuration based on states."""
        if states and "states" in self.btn_data:
            return self.btn_data["states"].get(states, {})
        return self.btn_data

    def _get_button_style(self, style_name: Optional[str]) -> discord.ButtonStyle:
        """Retrieve the corresponding ButtonStyle based on the provided style name."""
        if style_name:
            for name, btn_style in discord.ButtonStyle.__members__.items():
                if name.lower() == style_name.lower():
                    return btn_style
            
        return discord.ButtonStyle.gray
    
    def change_states(self, states: str) -> None:
        """Change the button's emoji and label based on the provided state."""
        states = states.lower() if states else None
        state_config = self._get_button_config(states)
        if state_config:
            self.emoji = state_config.get("emoji") or None
            self.style = self._get_button_style(state_config.get("style"))
            self.label = self.player._ph.replace(state_config.get("label"), {})
    
    async def send(self, interaction: discord.Interaction, key: str, *params, view: discord.ui.View = None, ephemeral: bool = False) -> None:
        stay = self.player.settings.get("controller_msg", True)
        return await send_localized_message(
            interaction, key, *params,
            view=view,
            delete_after=None if ephemeral or stay else 10,
            ephemeral=ephemeral
        )

class Back(ControlButton):
    def __init__(self, **kwargs):
        super().__init__(
            disabled=False if kwargs["player"].queue.history() or not kwargs["player"].current else True,
            **kwargs
        )
    
    async def callback(self, interaction: discord.Interaction):
        if not self.player.is_privileged(interaction.user):
            if interaction.user in self.player.previous_votes:
                return await self.send(interaction, "voting.voted", ephemeral=True)
            else:
                self.player.previous_votes.add(interaction.user)
                if len(self.player.previous_votes) >= (required := self.player.required()):
                    pass
                else:
                    return await self.send(interaction, "player.controls.back.vote", interaction.user, len(self.player.previous_votes), required)

        if not self.player.is_playing:
            self.player.queue.backto(1)
            await self.player.do_next()
        else:
            self.player.queue.backto(2)
            await self.player.stop()

        await self.send(interaction, "player.controls.back.success", interaction.user)

        if self.player.queue._repeat.mode == voicelink.LoopType.TRACK:
            await self.player.set_repeat(voicelink.LoopType.OFF)
        
class PlayPause(ControlButton):
    def __init__(self, **kwargs):
        self.playing_status = lambda player, reverse=False: "pause" if (player.is_paused and not reverse) or (not player.is_paused and reverse) else "resume"

        super().__init__(
            default_states="pause",
            disabled=kwargs["player"].current is None,
            **kwargs
        )
    
    async def callback(self, interaction: discord.Interaction):
        is_paused = not self.player.is_paused
        vote_type = self.playing_status(self.player, True)
        votes = getattr(self.player, f"{vote_type}_votes")

        if not self.player.is_privileged(interaction.user):
            if interaction.user in votes:
                return await self.send(interaction, "voting.voted", ephemeral=True)
            else:
                votes.add(interaction.user)
                if len(votes) < (required := self.player.required()):
                    return await self.send(interaction, f"{vote_type}Vote", interaction.user, len(votes), required)

        self.change_states(self.playing_status(self.player))
        await self.player.set_pause(is_paused, interaction.user)
        await interaction.response.edit_message(view=self.view)

class Skip(ControlButton):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
    
    async def callback(self, interaction: discord.Interaction):
        if not self.player.is_playing:
            return 
        if not self.player.is_privileged(interaction.user):
            if interaction.user == self.player.current.requester:
                pass 
            elif interaction.user in self.player.skip_votes:
                return await self.send(interaction, "voting.voted", ephemeral=True)
            else:
                self.player.skip_votes.add(interaction.user)
                if len(self.player.skip_votes) >= (required := self.player.required()):
                    pass
                else:
                    return await self.send(interaction, "player.controls.skip.vote", interaction.user, len(self.player.skip_votes), required)

        await self.send(interaction, "player.controls.skip.success", interaction.user)

        if self.player.queue._repeat.mode == voicelink.LoopType.TRACK:
            await self.player.set_repeat(voicelink.LoopType.OFF)
        await self.player.stop()

class Stop(ControlButton):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    async def callback(self, interaction: discord.Interaction):
        if not self.player.is_privileged(interaction.user):
            if interaction.user in self.player.stop_votes:
                return await self.send(interaction, "voting.voted", ephemeral=True)
            else:
                self.player.stop_votes.add(interaction.user)
                if len(self.player.stop_votes) >= (required := self.player.required(leave=True)):
                    pass
                else:
                    return await self.send(interaction, "player.controls.leave.vote", interaction.user, len(self.player.stop_votes), required)
        
        await self.send(interaction, "player.controls.leave.success", interaction.user)
        await self.player.teardown()

class AddFav(ControlButton):
    def __init__(self, **kwargs):
        super().__init__(disabled=kwargs["player"].current is None, **kwargs)
    
    async def callback(self, interaction: discord.Interaction):
        track = self.player.current
        if not track:
            return await self.send(interaction, "player.errors.noTrackPlaying")
        if track.is_stream:
            return await self.send(interaction, "playlist.errors.streamNotAllowed")
        user = await MongoDBHandler.get_user(interaction.user.id, d_type='playlist')
        _, max_t, _ = Config().get_playlist_config()
        if len(user['200']['tracks']) >= max_t:
            return await self.send(interaction, "playlist.errors.trackLimited", max_t, ephemeral=True)

        if track.track_id in user['200']['tracks']:
            return await self.send(interaction, "playlist.errors.trackRepeated", ephemeral=True)
        respond = await MongoDBHandler.update_user(interaction.user.id, {"$push": {'playlist.200.tracks': track.track_id}})
        if respond:
            await self.send(interaction, "playlist.actions.trackAdded", track.title, interaction.user.mention, user['200']['name'], ephemeral=True)
        else:
            await self.send(interaction, "playlist.errors.track", ephemeral=True)

class Loop(ControlButton):
    def __init__(self, **kwargs):
        super().__init__(
            default_states=kwargs["player"].queue._repeat.peek_next().name,
            **kwargs
        )
    
    async def callback(self, interaction: discord.Interaction):
        if not self.player.is_privileged(interaction.user):
            return await self.send(interaction, 'permissions.missingMode', ephemeral=True)

        await self.player.set_repeat(requester=interaction.user)
        self.change_states(self.player.queue._repeat.peek_next().name)

        await interaction.response.edit_message(view=self.view)
        
class VolumeUp(ControlButton):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
    
    async def callback(self, interaction: discord.Interaction):
        if not self.player.is_privileged(interaction.user):
            return await self.send(interaction, "permissions.missingFunction")

        value = value if (value := self.player.volume + 20) <= 150 else 150
        await self.player.set_volume(value, interaction.user)

        await self.send(interaction, 'settings.actions.volumeSet', value, ephemeral=True)

class VolumeDown(ControlButton):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
    
    async def callback(self, interaction: discord.Interaction):
        if not self.player.is_privileged(interaction.user):
            return await self.send(interaction, "permissions.missingFunction")

        value = value if (value := self.player.volume - 20) >= 0 else 0
        await self.player.set_volume(value, interaction.user)

        await self.send(interaction, 'settings.actions.volumeSet', value, ephemeral=True)

class VolumeMute(ControlButton):
    def __init__(self, **kwargs):
        super().__init__(
            default_states="muted" if kwargs["player"].volume else "mute",
            **kwargs
        )
    
    async def callback(self, interaction: discord.Interaction):
        if not self.player.is_privileged(interaction.user):
            return await self.send(interaction, "permissions.missingFunction")

        is_muted = self.player.volume != 0
        value = 0 if is_muted else self.player.settings.get("volume", 100)
        self.change_states("muted" if value else "mute")
        await self.player.set_volume(value, interaction.user)
        await interaction.response.edit_message(view=self.view)

class AutoPlay(ControlButton):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
    
    async def callback(self, interaction: discord.Interaction):
        if not self.player.is_privileged(interaction.user):
            return await self.send(interaction, "permissions.missingAutoPlay", ephemeral=True)

        check = not self.player.settings.get("autoplay", False)
        self.player.settings['autoplay'] = check
        await self.send(interaction, 'autoplay', await LangHandler.get_lang(interaction.guild_id, 'common.status.enabled' if check else "common.status.disabled"))

        if not self.player.is_playing:
            await self.player.do_next()

class Shuffle(ControlButton):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
    
    async def callback(self, interaction: discord.Interaction):
        if not self.player.is_privileged(interaction.user):
            if interaction.user in self.player.shuffle_votes:
                return await self.send(interaction, 'voting.voted', ephemeral=True)
            else:
                self.player.shuffle_votes.add(interaction.user)
                if len(self.player.shuffle_votes) >= (required := self.player.required()):
                    pass
                else:
                    return await self.send(interaction, 'player.controls.shuffle.vote', interaction.user, len(self.player.shuffle_votes), required)
        
        await self.player.shuffle("queue", interaction.user)
        await self.send(interaction, 'player.controls.shuffle.success')

class Forward(ControlButton):
    def __init__(self, **kwargs):
        super().__init__(
            disabled=kwargs["player"].current is None,
            **kwargs
        )
        
    async def callback(self, interaction: discord.Interaction):
        if not self.player.is_privileged(interaction.user):
            return await self.send(interaction, 'permissions.missingPosition', ephemeral=True)

        if not self.player.current:
            return await self.send(interaction, 'player.errors.noTrackPlaying', ephemeral=True)

        position = int(self.player.position + 10000)

        await self.player.seek(position)
        await self.send(interaction, 'forward', format_ms(position))

class Rewind(ControlButton):
    def __init__(self, **kwargs):
        super().__init__(
            disabled=kwargs["player"].current is None,
            **kwargs
        )
        
    async def callback(self, interaction: discord.Interaction):
        if not self.player.is_privileged(interaction.user):
            return await self.send(interaction, 'permissions.missingPosition', ephemeral=True)

        if not self.player.current:
            return await self.send(interaction, 'player.errors.noTrackPlaying', ephemeral=True)

        position = 0 if (value := int(self.player.position - 30000)) <= 0 else value
        
        await self.player.seek(position)
        await self.send(interaction, 'rewind', format_ms(position))

class Lyrics(ControlButton):
    def __init__(self, **kwargs):
        super().__init__(
            disabled=kwargs["player"].current is None,
            **kwargs
        )
        
    async def callback(self, interaction: discord.Interaction):
        from . import LyricsView
        if not self.player or not self.player.is_playing:
            return await self.send(interaction, "player.errors.noTrackPlaying", ephemeral=True)
        
        title = self.player.current.title
        artist = self.player.current.author
        
        lyrics_platform = voicelink.LYRICS_PLATFORMS.get(Config().lyrics_platform)
        if lyrics_platform:
            lyrics = await lyrics_platform().get_lyrics(title, artist)
            if not lyrics:
                return await self.send(interaction, "lyrics.notFound", ephemeral=True)

            view = LyricsView(name=title, source={_: re.findall(r'.*\n(?:.*\n){,22}', v or "") for _, v in lyrics.items()}, author=interaction.user)
            view.response = await self.send(interaction, view.build_embed(), view=view, ephemeral=True)

class Tracks(discord.ui.Select):
    def __init__(self, player: "voicelink.Player", btn_data, **kwargs):
        self.player: voicelink.Player = player
        
        if player.queue.is_empty:
            raise ValueError("Player queue is empty, cannot create Tracks row instance.")
        
        options = []
        for index, track in enumerate(self.player.queue.tracks(), start=1):
            if index > min(max(btn_data.get("max_options", 10), 1), 25):
                break
            options.append(discord.SelectOption(label=f"{index}. {track.title[:40]}", description=f"{track.author[:30]} · " + ("Live" if track.is_stream else track.formatted_length), emoji=track.emoji))

        super().__init__(
            placeholder=self.player._ph.replace(btn_data.get("label"), {}),
            options=options,
            disabled=player.queue.is_empty,
            **kwargs
        )
    
    async def callback(self, interaction: discord.Interaction):
        if not self.player.is_privileged(interaction.user):
            return await send_localized_message(interaction, "permissions.missingFunction", ephemeral=True)
        
        self.player.queue.skipto(int(self.values[0].split(". ")[0]))
        await self.player.stop()

        if self.player.settings.get("controller_msg", True):
            await send_localized_message(interaction, "player.controls.skip.success", interaction.user)

class Effects(discord.ui.Select):
    def __init__(self, player: "voicelink.Player", btn_data, row):

        self.player: voicelink.Player = player
        
        options = [discord.SelectOption(label="None", value="None")]
        for name in voicelink.Filters.get_available_filters():
            options.append(discord.SelectOption(label=name.capitalize(), value=name))

        super().__init__(
            placeholder=self.player._ph.replace(btn_data.get("label"), {}),
            options=options,
            row=row
        )
    
    async def callback(self, interaction: discord.Interaction):
        if not self.player.is_privileged(interaction.user):
            return await send_localized_message(interaction, "permissions.missingFunction", ephemeral=True)
        
        avalibable_filters = voicelink.Filters.get_available_filters()
        if self.values[0] == "None":
            await self.player.reset_filter(requester=interaction.user)
            return await send_localized_message(interaction, "effects.cleared")
        
        selected_filter = avalibable_filters.get(self.values[0].lower())()
        if self.player.filters.has_filter(filter_tag=selected_filter.tag):
            await self.player.remove_filter(filter_tag=selected_filter.tag, requester=interaction.user)
            await send_localized_message(interaction, "effects.cleared")
        else:
            await self.player.add_filter(selected_filter, requester=interaction.user)
            await send_localized_message(interaction, "effects.added", selected_filter.tag)

BUTTON_TYPE: Dict[str, Type[Union[ControlButton, discord.ui.Select]]] = {
    "back": Back,
    "play-pause": PlayPause,
    "skip": Skip,
    "stop": Stop,
    "add-fav": AddFav,
    "loop": Loop,
    "volumeup": VolumeUp,
    "volumedown": VolumeDown,
    "volumemute": VolumeMute,
    "autoplay": AutoPlay,
    "shuffle": Shuffle,
    "forward": Forward,
    "rewind": Rewind,
    "lyrics": Lyrics,
    "tracks": Tracks,
    "effects": Effects
}

class InteractiveController(discord.ui.View):
    def __init__(self, player):
        super().__init__(timeout=None)

        self.player: voicelink.Player = player
        for row_num, btn_row in enumerate(Config().controller.get("buttons")):
            for btn_name, btn_data in btn_row.items():
                btn_class = BUTTON_TYPE.get(btn_name.lower())
                if not btn_class:
                    continue
                
                try:
                    self.add_item(btn_class(player=player, btn_data=btn_data, row=row_num))
                except ValueError:
                    pass
                
        self.cooldown = commands.CooldownMapping.from_cooldown(2.0, 10.0, key)
            
    async def interaction_check(self, interaction: discord.Interaction):
        if not self.player.node._available:
            await send_localized_message(interaction, "player.errors.nodeReconnect", ephemeral=True)
            return False

        if interaction.user.id in Config().bot_access_user:
            return True
            
        if self.player.channel and self.player.is_user_join(interaction.user):
            retry_after = self.cooldown.update_rate_limit(interaction)
            if retry_after:
                raise ButtonOnCooldown(retry_after)
            return True
        else:
            await send_localized_message(interaction, "voice.connection.notInChannel", interaction.user.mention, self.player.channel.mention, ephemeral=True)
            return False

    async def on_error(self, interaction: discord.Interaction, error: Exception, item: discord.ui.Item) -> None:
        if isinstance(error, ButtonOnCooldown):
            sec = int(error.retry_after)
            return await interaction.response.send_message(f"You're on cooldown for {sec} second{'' if sec == 1 else 's'}!", ephemeral=True)
        
        super().on_error(interaction, error, item)