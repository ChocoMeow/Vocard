import discord
import voicelink
import re

from discord import app_commands
from discord.ext import commands
from function import (
    time as ctime,
    formatTime,
    emoji_source,
    youtube_api_key,
    requests_api,
    get_lang,
    embed_color
)

from addons import getLyrics
from view import SearchView, ListView, LinkView, LyricsView, ChapterView, HelpView
from validators import url
from random import shuffle

async def connect_channel(interaction: discord.Interaction, channel: discord.VoiceChannel = None) -> voicelink.Player:
    try:
        channel = channel or interaction.user.voice.channel
    except:
        raise voicelink.VoicelinkException(get_lang(interaction.guild_id, 'noChannel'))

    check = channel.permissions_for(interaction.guild.me)
    if check.connect == False or check.speak == False:
        raise voicelink.VoicelinkException(get_lang(interaction.guild_id, 'noPermission'))

    player: voicelink.Player = await channel.connect(cls=voicelink.Player(interaction.client, channel, interaction))
    return player

async def nowplay(interaction: discord.Interaction, player: voicelink.Player):
    track = player.current
    if not track:
        return await interaction.response.send_message(player.get_msg('noTrackPlaying'), ephemeral=True)

    upnext = "\n".join(f"`{index}.` `[{track.formatLength}]` [{track.title[:30]}]({track.uri})" for index, track in enumerate(player.queue.tracks()[:2], start=2))
    embed=discord.Embed(description=player.get_msg('nowplayingDesc').format(track.title), color=embed_color)       
    embed.set_author(name=track.requester if track.requester else interaction.client, icon_url=track.requester.display_avatar.url if track.requester else interaction.client.user.display_avatar.url)

    if upnext:
        embed.add_field(name=player.get_msg('nowplayingField'), value=upnext)      
    pbar = "".join(":radio_button:" if i == round(player.position // round(track.length // 15)) else "▬" for i in range(15)) 
    icon = ":red_circle:" if track.is_stream else (":pause_button:" if player.is_paused else ":arrow_forward:")

    embed.add_field(name="\u2800", value=f"{icon} {pbar} **[{ctime(player.position)}/{track.formatLength}]**", inline=False)
    
    return await interaction.response.send_message(embed=embed, view=LinkView(player.get_msg('nowplayingLink').format(track.source), track.emoji, track.uri))

async def help_autocomplete(interaction: discord.Interaction, current: str) -> list:
    return [ app_commands.Choice(name=c.capitalize(), value=c) for c in interaction.client.cogs if c not in ["Nodes", "Task"] and current in c ]

class Basic(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.description = "This category is available to anyone on this server. Voting is required in certain commands."
        self.ctx_menu = app_commands.ContextMenu(
            name="play",
            callback=self._play,
        )
        self.bot.tree.add_command(self.ctx_menu)
    
    async def cog_unload(self) -> None:
        self.bot.tree.remove_command(self.ctx_menu.name, type=self.ctx_menu.type)

    @app_commands.command(
        name = "connect",
        description = "Connect to a voice channel."
    )
    @app_commands.describe(
        channel="Provide a channel to connect."
    )
    @app_commands.checks.cooldown(2, 30.0, key=lambda i: (i.guild_id))
    @app_commands.guild_only()
    async def connect(self, interaction: discord.Interaction, channel: discord.VoiceChannel = None) -> None:
        try:
            player = await connect_channel(interaction, channel)
        except discord.errors.ClientException:
            return await interaction.response.send_message(get_lang(interaction.guild_id, "alreadyConnected"))

        await interaction.response.send_message(player.get_msg('connect').format(player.channel))

    @app_commands.command(
        name = "play",
        description = "Loads your input and added it to the queue."
    )
    @app_commands.describe(
        query="Input a query or a searchable link.",
    )
    @app_commands.checks.cooldown(2, 15.0, key=lambda i: (i.guild_id))
    @app_commands.guild_only()
    async def play(self, interaction: discord.Interaction, query: str) -> None:
        player: voicelink.Player = interaction.guild.voice_client
        if not player: 
            player = await connect_channel(interaction)

        if interaction.user not in player.channel.members:
            if not interaction.user.guild_permissions.manage_guild:
                return await interaction.response.send_message(player.get_msg('notInChannel').format(interaction.user.mention, player.channel.mention), ephemeral=True)       

        tracks = await player.get_tracks(query, requester=interaction.user)
        if not tracks:
            return await interaction.response.send_message(player.get_msg('noTrackFound'))

        try:
            if isinstance(tracks, voicelink.Playlist):
                for track in tracks.tracks:
                    await player.queue.put(track)
                await interaction.response.send_message(player.get_msg('playlistLoad').format(tracks.name, len(tracks.tracks)))
            else:
                position = await player.queue.put(tracks[0])
                await interaction.response.send_message((f"`{player.get_msg('live')}`" if tracks[0].is_stream else "") + ( player.get_msg('trackLoad_pos').format(tracks[0].title, tracks[0].author, tracks[0].formatLength, position) if position >= 1 and player.is_playing else player.get_msg('trackLoad').format(tracks[0].title, tracks[0].author, tracks[0].formatLength)))
        except voicelink.QueueFull as e:
            await interaction.response.send_message(e) 
        finally:
            if not player.is_playing:
                await player.do_next()
                
    @app_commands.checks.cooldown(2, 15.0, key=lambda i: (i.guild_id))
    async def _play(self, interaction: discord.Interaction, message: discord.Message):
        query = ""
        if message.content:
            url = re.findall("http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+", message.content)
            if url:
                query = url[0]
        elif message.attachments:
            query = message.attachments[0].url

        if not query:
            return await interaction.response.send_message(get_lang(interaction.guild_id, key="noPlaySource"), ephemeral=True)

        player: voicelink.Player = interaction.guild.voice_client
        if not player: 
            player = await connect_channel(interaction)
        
        if interaction.user not in player.channel.members:
            if not interaction.user.guild_permissions.manage_guild:
                return await interaction.response.send_message(player.get_msg('notInChannel').format(interaction.user.mention, player.channel.mention), ephemeral=True)       

        tracks = await player.get_tracks(query, requester=interaction.user)
        if not tracks:
            return await interaction.response.send_message(player.get_msg('noTrackFound'))

        try:
            if isinstance(tracks, voicelink.Playlist):
                for track in tracks.tracks:
                    await player.queue.put(track)
                await interaction.response.send_message(player.get_msg('playlistLoad').format(tracks.name, len(tracks.tracks)))
            else:
                await player.queue.put(tracks[0])
                await interaction.response.send_message((f"`{player.get_msg('live')}`" if tracks[0].is_stream else "") + ( player.get_msg('trackLoad_pos').format(tracks[0].title, tracks[0].author, tracks[0].formatLength, player.queue.count) if player.queue.count >= 1 and player.is_playing else player.get_msg('trackLoad').format(tracks[0].title, tracks[0].author, tracks[0].formatLength)))
        except voicelink.QueueFull as e:
            await interaction.response.send_message(e) 
        finally:
            if not player.is_playing:
                await player.do_next()

    @app_commands.command(
        name = "search",
        description = "Loads your input and added it to the queue."
    )
    @app_commands.describe(
        query="Input the name of the song.",
        platform="Select the platform you want to search."
    )
    @app_commands.checks.cooldown(2, 15.0, key=lambda i: (i.guild_id))
    @app_commands.choices(platform = [
        app_commands.Choice(name="Youtube", value="Youtube"),
        app_commands.Choice(name="Youtube Music", value="Youtube Music"),
        app_commands.Choice(name="Spotify", value="Spotify"),
        app_commands.Choice(name="SoundCloud", value="SoundCloud"),
        app_commands.Choice(name="Apple Music", value="Apple")
    ])
    @app_commands.guild_only()
    async def search(self, interaction: discord.Interaction, query: str, platform: str = "Youtube"):
        player: voicelink.Player = interaction.guild.voice_client
        if not player: 
            player = await connect_channel(interaction)

        if interaction.user not in player.channel.members:
            if not interaction.user.guild_permissions.manage_guild:
                return await interaction.response.send_message(player.get_msg('notInChannel').format(interaction.user.mention, player.channel.mention), ephemeral=True)       
         
        if url(query):
            return await interaction.response.send_message(player.get_msg('noLinkSupport'), ephemeral=True)
        if platform != 'Spotify':
            query_platform = ("ytsearch" if platform == "Youtube" else "ytmsearch" if platform == "Youtube Music" else "scsearch" if platform == "SoundCloud" else "amsearch") + f":{query}"
            tracks = await player.get_tracks(query=query_platform, requester=interaction.user)
        else:
            tracks = await player.spotifySearch(query=query, requester=interaction.user)
        if not tracks:
            return await interaction.response.send_message(player.get_msg('noTrackFound'))
        query_track = "\n".join(f"`{index}.` `[{track.formatLength}]` **{track.title[:35]}**" for index, track in enumerate(tracks[0:10], start=1))
        embed=discord.Embed(title=player.get_msg('searchTitle').format(query), description=player.get_msg('searchDesc').format(emoji_source(platform.lower()), platform, len(tracks[0:10]), query_track), color=embed_color)
        view = SearchView(tracks=tracks[0:10], lang=player.lang)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        view.response = await interaction.original_response()
        await view.wait()
        if view.values is not None:
            msg = ""
            for value in view.values:
                track = tracks[int(value.split(". ")[0]) - 1]
                await player.queue.put(track)
                msg += ((f"`{player.get_msg('live')}`" if track.is_stream else "") + ( player.get_msg('trackLoad_pos').format(track.title, track.author, track.formatLength, player.queue.count) if player.queue.count >= 1 else player.get_msg('trackLoad').format(track.title, track.author, track.formatLength)) )
            await interaction.followup.send(msg)

            if not player.is_playing:
                await player.do_next()

    @app_commands.command(
        name = "pause",
        description = "Pause the music."
    )
    @app_commands.checks.cooldown(2, 15.0, key=lambda i: (i.guild_id))
    @app_commands.guild_only()
    async def pause(self, interaction: discord.Interaction):
        player: voicelink.Player = interaction.guild.voice_client
        if not player:
            return await interaction.response.send_message(get_lang(interaction.guild_id, 'noPlayer'), ephemeral=True)
        
        if interaction.user not in player.channel.members:
            if not interaction.user.guild_permissions.manage_guild:
                return await interaction.response.send_message(player.get_msg('notInChannel').format(interaction.user.mention, player.channel.mention), ephemeral=True)       
         
        if player.is_paused:
            return await interaction.response.send_message(player.get_msg('pauseError'))

        if not await player.is_privileged(interaction.user):
            if interaction.user in player.pause_votes:
                return await interaction.response.send_message(player.get_msg('voted'), ephemeral=True)
            else:
                player.pause_votes.add(interaction.user)
                if len(player.pause_votes) >= (required := player.required()):
                    pass
                else:
                    return await interaction.response.send_message(player.get_msg('pauseVote').format(interaction.user, len(player.pause_votes), required))

        await player.set_pause(True)
        player.pause_votes.clear()
        await interaction.response.send_message(player.get_msg('paused').format(interaction.user))
    
    @app_commands.command(
        name = "resume",
        description = "Resume the music."
    )
    @app_commands.checks.cooldown(2, 15.0, key=lambda i: (i.guild_id))
    @app_commands.guild_only()
    async def resume(self, interaction: discord.Interaction):
        player: voicelink.Player = interaction.guild.voice_client
        if not player:
            return await interaction.response.send_message(get_lang(interaction.guild_id, 'noPlayer'), ephemeral=True)
        
        if interaction.user not in player.channel.members:
            if not interaction.user.guild_permissions.manage_guild:
                return await interaction.response.send_message(player.get_msg('notInChannel').format(interaction.user.mention, player.channel.mention), ephemeral=True)       
         
        if not player.is_paused:
            return await interaction.response.send_message(player.get_msg('resumeError'))
            
        if not await player.is_privileged(interaction.user):
            if interaction.user in player.resume_votes:
                return await interaction.response.send_message(player.get_msg('voted'), ephemeral=True)
            else:
                player.resume_votes.add(interaction.user)
                if len(player.resume_votes) >= (required := player.required()):
                    pass
                else:
                    return await interaction.response.send_message(player.get_msg('resumeVote').format(interaction.user, len(player.resume_votes), required))

        await player.set_pause(False)
        player.resume_votes.clear()
        await interaction.response.send_message(player.get_msg('resumed').format(interaction.user))

    @app_commands.command(
        name = "skip",
        description = "Skips to the next song or skips to the specified song."
    )
    @app_commands.describe(
        index="Enter a index that you want to skip to."
    )
    @app_commands.checks.cooldown(3, 20.0, key=lambda i: (i.guild_id))
    @app_commands.guild_only()
    async def skip(self, interaction: discord.Interaction, index: int = 0):
        player: voicelink.Player = interaction.guild.voice_client
        if not player:
            return await interaction.response.send_message(get_lang(interaction.guild_id, 'noPlayer'), ephemeral=True)
        
        if interaction.user not in player.channel.members:
            if not interaction.user.guild_permissions.manage_guild:
                return await interaction.response.send_message(player.get_msg('notInChannel').format(interaction.user.mention, player.channel.mention), ephemeral=True)       
         
        if not player.is_playing:
            return await interaction.response.send_message(player.get_msg('skipError'), ephemeral=True)
            
        if not await player.is_privileged(interaction.user):
            if interaction.user == player.current.requester:
                pass
            elif interaction.user in player.skip_votes:
                return await interaction.response.send_message(player.get_msg('voted'), ephemeral=True)
            else:
                player.skip_votes.add(interaction.user)
                if len(player.skip_votes) >= (required := player.required()):
                    pass
                else:
                    return await interaction.response.send_message(player.get_msg('skipVote').format(interaction.user, len(player.skip_votes), required))

        if not player.node._available:
            return await interaction.response.send_message(player.get_msg('nodeReconnect'))

        if index:
            await player.queue.skipto(index)
        
        await interaction.response.send_message(player.get_msg('skipped').format(interaction.user))

        if player.queue.repeat == "Track":
            player.queue.set_repeat("Off")
        await player.stop()

    @app_commands.command(
        name = "back",
        description = "Skips back to the previous song or skips to the specified previous song."
    )
    @app_commands.describe(
        index="Enter a index that you want to skip back to."
    )
    @app_commands.checks.cooldown(3, 20.0, key=lambda i: (i.guild_id))
    @app_commands.guild_only()
    async def back(self, interaction: discord.Interaction, index: int = 1):
        player: voicelink.Player = interaction.guild.voice_client
        if not player:
            return await interaction.response.send_message(get_lang(interaction.guild_id, 'noPlayer'), ephemeral=True)
        
        if interaction.user not in player.channel.members:
            if not interaction.user.guild_permissions.manage_guild:
                return await interaction.response.send_message(player.get_msg('notInChannel').format(interaction.user.mention, player.channel.mention), ephemeral=True)       
         
        if not await player.is_privileged(interaction.user):
            if interaction.user in player.previous_votes:
                return await interaction.response.send_message(player.get_msg('voted'), ephemeral=True)
            else:
                player.previous_votes.add(interaction.user)
                if len(player.previous_votes) >= (required := player.required()):
                    pass
                else:
                    return await interaction.response.send_message(player.get_msg('backVote').format(interaction.user, len(player.previous_votes), required))

        if not player.node._available:
            return await interaction.response.send_message(player.get_msg('nodeReconnect'))
            
        if not player.is_playing:
            player.queue.backto(index)
            await player.do_next()            
        else:
            player.queue.backto(index + 1)
            await player.stop()
        
        await interaction.response.send_message(player.get_msg('backed').format(interaction.user))

        if player.queue.repeat == "Track":
            player.queue.set_repeat("Off")

    @app_commands.command(
        name = "seek",
        description = "Change the player position."
    )
    @app_commands.describe(
        position="Input position. Exmaple: 1:20."
    )
    @app_commands.checks.cooldown(3, 20.0, key=lambda i: (i.guild_id))
    @app_commands.guild_only()
    async def seek(self, interaction: discord.Interaction, position: str):
        player: voicelink.Player = interaction.guild.voice_client
        if not player:
            return await interaction.response.send_message(get_lang(interaction.guild_id, 'noPlayer'), ephemeral=True)
        
        if interaction.user not in player.channel.members:
            if not interaction.user.guild_permissions.manage_guild:
                return await interaction.response.send_message(player.get_msg('notInChannel').format(interaction.user.mention, player.channel.mention), ephemeral=True)       
         
        if not player.current:
            return await interaction.response.send_message(player.get_msg('noTrackPlaying'), ephemeral=True)
        if not await player.is_privileged(interaction.user):
            return await interaction.response.send_message(player.get_msg('missingPerms_pos'), ephemeral=True)
        if player.position == 0:
            return await interaction.response.send_message(player.get_msg('noTrackPlaying'), ephemeral=True)
        
        num = formatTime(position)
        if num is None:
            return await interaction.response.send_message(player.get_msg('timeFormatError'), ephemeral=True)
            
        await player.seek(num)
        await interaction.response.send_message(player.get_msg('seek').format(position))
    
    @app_commands.command(
        name = "queue",
        description = "Display the players queue songs in your queue."
    )
    @app_commands.checks.cooldown(2, 40.0, key=lambda i: (i.guild_id))
    @app_commands.guild_only()
    async def queue(self, interaction: discord.Interaction):
        player: voicelink.Player = interaction.guild.voice_client
        if not player:
            return await interaction.response.send_message(get_lang(interaction.guild_id, 'noPlayer'), ephemeral=True)
        
        if interaction.user not in player.channel.members:
            if not interaction.user.guild_permissions.manage_guild:
                return await interaction.response.send_message(player.get_msg('notInChannel').format(interaction.user.mention, player.channel.mention), ephemeral=True)       
         
        if player.queue.is_empty:
            return await nowplay(interaction, player)
        view = ListView(player=player, author=interaction.user)
        await interaction.response.send_message(embed=view.build_embed(), view=view)
        view.response = await interaction.original_response()
    
    @app_commands.command(
        name = "history",
        description = "Display the players queue songs in your history queue."
    )
    @app_commands.checks.cooldown(2, 40.0, key=lambda i: (i.guild_id))
    @app_commands.guild_only()
    async def history(self, interaction: discord.Interaction):
        player: voicelink.Player = interaction.guild.voice_client
        if not player:
            return await interaction.response.send_message(get_lang(interaction.guild_id, 'noPlayer'), ephemeral=True)
        
        if interaction.user not in player.channel.members:
            if not interaction.user.guild_permissions.manage_guild:
                return await interaction.response.send_message(player.get_msg('notInChannel').format(interaction.user.mention, player.channel.mention), ephemeral=True)       
         
        if not player.queue.history():
            return await nowplay(interaction, player)

        view = ListView(player=player, author=interaction.user, isQueue=False)
        await interaction.response.send_message(embed=view.build_embed(), view=view)
        view.response = await interaction.original_response()

    @app_commands.command(
        name = "leave",
        description = "Disconnects the bot from your voice channel and chears the queue."
    )
    @app_commands.guild_only()
    async def leave(self, interaction: discord.Interaction):
        player: voicelink.Player = interaction.guild.voice_client
        if not player:
            return await interaction.response.send_message(get_lang(interaction.guild_id, 'noPlayer'), ephemeral=True)
        
        if interaction.user not in player.channel.members:
            if not interaction.user.guild_permissions.manage_guild:
                return await interaction.response.send_message(player.get_msg('notInChannel').format(interaction.user.mention, player.channel.mention), ephemeral=True)       
         
        if not await player.is_privileged(interaction.user):
            if interaction.user in player.stop_votes:
                return await interaction.response.send_message(player.get_msg('voted'), ephemeral=True)
            else:
                player.stop_votes.add(interaction.user)
                if len(player.stop_votes) >= (required := player.required(leave=True)):
                    pass
                else:
                    return await interaction.response.send_message(player.get_msg('leaveVote').format(interaction.user, len(player.stop_votes), required))
        
        await interaction.response.send_message(player.get_msg('left').format(interaction.user))
        await player.teardown()
    
    @app_commands.command(
        name = "nowplaying",
        description = "Shows details of the current track."
    )
    @app_commands.checks.cooldown(2, 10.0, key=lambda i: (i.guild_id))
    @app_commands.guild_only()
    async def nowplaying(self, interaction: discord.Interaction):
        player: voicelink.Player = interaction.guild.voice_client
        if not player:
            return await interaction.response.send_message(get_lang(interaction.guild_id, 'noPlayer'), ephemeral=True)
        
        if interaction.user not in player.channel.members:
            if not interaction.user.guild_permissions.manage_guild:
                return await interaction.response.send_message(player.get_msg('notInChannel').format(interaction.user.mention, player.channel.mention), ephemeral=True)       
         
        await nowplay(interaction, player)

    @app_commands.command(
        name = "loop",
        description = "Changes Loop mode."
    )
    @app_commands.describe(
        mode = "Choose a looping mode."
    )
    @app_commands.choices( mode = [
        app_commands.Choice(name='Off', value='Off'),
        app_commands.Choice(name='Track', value='Track'),
        app_commands.Choice(name='Queue', value='Queue')
    ])
    @app_commands.guild_only()
    async def loop(self, interaction: discord.Interaction, mode: str):
        player: voicelink.Player = interaction.guild.voice_client
        if not player:
            return await interaction.response.send_message(get_lang(interaction.guild_id, 'noPlayer'), ephemeral=True)
        
        if interaction.user not in player.channel.members:
            if not interaction.user.guild_permissions.manage_guild:
                return await interaction.response.send_message(player.get_msg('notInChannel').format(interaction.user.mention, player.channel.mention), ephemeral=True)       
         
        if not await player.is_privileged(interaction.user):
            return await interaction.response.send_message(player.get_msg('missingPerms_mode'), ephemeral=True)

        player.queue.set_repeat(mode)
        await interaction.response.send_message(player.get_msg('repeat').format(mode))

    @app_commands.command(
        name = "clear",
        description = "Remove all the tracks in your queue or history queue."
    )
    @app_commands.describe(
        queue = "Choose a queue that you want to clear."
    )
    @app_commands.choices( queue = [
        app_commands.Choice(name='Queue', value='Queue'),
        app_commands.Choice(name='History', value='History')
    ])
    @app_commands.guild_only()
    async def clear(self, interaction: discord.Interaction, queue: str):
        player: voicelink.Player = interaction.guild.voice_client
        if not player:
            return await interaction.response.send_message(get_lang(interaction.guild_id, 'noPlayer'), ephemeral=True)
        
        if interaction.user not in player.channel.members:
            if not interaction.user.guild_permissions.manage_guild:
                return await interaction.response.send_message(player.get_msg('notInChannel').format(interaction.user.mention, player.channel.mention), ephemeral=True)       
         
        if not await player.is_privileged(interaction.user):
            return await interaction.response.send_message(player.get_msg('missingPerms_queue'), ephemeral=True)

        if queue == 'Queue':
            player.queue.clear()
        elif queue == 'History':
            player.queue.history_clear(player.is_playing)
        
        await interaction.response.send_message(player.get_msg('cleared').format(queue))
    
    @app_commands.command(
        name = "remove",
        description = "Removes specified track or a range of tracks from the queue."
    )
    @app_commands.describe(
        position = "Input a position from the queue to be removed.",
        position2 = "Set the range of the queue to be removed.",
        member = "Remove tracks requested by a specific member."
    )
    @app_commands.guild_only()
    async def remove(self, interaction: discord.Interaction, position: int, position2: int = None, member: discord.Member = None):
        player: voicelink.Player = interaction.guild.voice_client
        if not player:
            return await interaction.response.send_message(get_lang(interaction.guild_id, 'noPlayer'), ephemeral=True)
        
        if interaction.user not in player.channel.members:
            if not interaction.user.guild_permissions.manage_guild:
                return await interaction.response.send_message(player.get_msg('notInChannel').format(interaction.user.mention, player.channel.mention), ephemeral=True)       
         
        if not await player.is_privileged(interaction.user):
            return await interaction.response.send_message(player.get_msg('missingPerms_queue'), ephemeral=True)

        removedTrack = player.queue.remove(position, position2, member)
        await interaction.response.send_message(player.get_msg('removed').format(removedTrack))

    @app_commands.command(
        name = "forward",
        description = "Forwards by a certain amount of time in the current track. The default is 10 seconds."
    )
    @app_commands.describe(
        position = "Input a amount that you to forward to. Exmaple: 1:20"
    )
    @app_commands.checks.cooldown(2, 20.0, key=lambda i: (i.guild_id))
    @app_commands.guild_only()
    async def forward(self, interaction: discord.Interaction, position: str = "10"):
        player: voicelink.Player = interaction.guild.voice_client
        if not player:
            return await interaction.response.send_message(get_lang(interaction.guild_id, 'noPlayer'), ephemeral=True)
        
        if interaction.user not in player.channel.members:
            if not interaction.user.guild_permissions.manage_guild:
                return await interaction.response.send_message(player.get_msg('notInChannel').format(interaction.user.mention, player.channel.mention), ephemeral=True)       
         
        if not player.current:
            return await interaction.response.send_message(player.get_msg('noTrackPlaying'), ephemeral=True)
        if not await player.is_privileged(interaction.user):
            return await interaction.response.send_message(player.get_msg('missingPerms_pos'), ephemeral=True)

        num = formatTime(position)
        if num is None:
            return await interaction.response.send_message(player.get_msg('timeFormatError'), ephemeral=True)

        await player.seek(player.position + num)
        await interaction.response.send_message(player.get_msg('forward').format(ctime(player.position + num)))
        
    @app_commands.command(
        name = "rewind",
        description = "Rewind by a certain amount of time in the current track. The default is 10 seconds."
    )
    @app_commands.describe(
        position = "Input a amount that you to rewind to. Exmaple: 1:20"
    )
    @app_commands.checks.cooldown(2, 20.0, key=lambda i: (i.guild_id))
    @app_commands.guild_only()
    async def rewind(self, interaction: discord.Interaction, position: str = "10"):
        player: voicelink.Player = interaction.guild.voice_client
        if not player:
            return await interaction.response.send_message(get_lang(interaction.guild_id, 'noPlayer'), ephemeral=True)
        
        if interaction.user not in player.channel.members:
            if not interaction.user.guild_permissions.manage_guild:
                return await interaction.response.send_message(player.get_msg('notInChannel').format(interaction.user.mention, player.channel.mention), ephemeral=True)       
         
        if not player.current:
            return await interaction.response.send_message(player.get_msg('noTrackPlaying'), ephemeral=True)

        if not await player.is_privileged(interaction.user):
            return await interaction.response.send_message(player.get_msg('missingPerms_pos'), ephemeral=True)

        num = formatTime(position)
        if num is None:
            return await interaction.response.send_message(player.get_msg('timeFormatError'), ephemeral=True)

        await player.seek(player.position - num)
        await interaction.response.send_message(player.get_msg('rewind').format(ctime(player.position - num)))

    @app_commands.command(
        name = "replay",
        description = "Reset the progress of the current song."
    )
    @app_commands.checks.cooldown(2, 20.0, key=lambda i: (i.guild_id))
    @app_commands.guild_only()
    async def replay(self, interaction: discord.Interaction):
        player: voicelink.Player = interaction.guild.voice_client
        if not player:
            return await interaction.response.send_message(get_lang(interaction.guild_id, 'noPlayer'), ephemeral=True)
        
        if interaction.user not in player.channel.members:
            if not interaction.user.guild_permissions.manage_guild:
                return await interaction.response.send_message(player.get_msg('notInChannel').format(interaction.user.mention, player.channel.mention), ephemeral=True)       
         
        if not player.current:
            return await interaction.response.send_message(player.get_msg('noTrackPlaying'), ephemeral=True)

        if not await player.is_privileged(interaction.user):
            return await interaction.response.send_message(player.get_msg('missingPerms_pos'), ephemeral=True)

        await player.seek(0)
        await interaction.response.send_message(player.get_msg('replay'))
    
    @app_commands.command(
        name = "shuffle",
        description = "Randomizes the tracks in the queue."
    )
    @app_commands.checks.cooldown(1, 15.0, key=lambda i: (i.guild_id))
    @app_commands.guild_only()
    async def shuffle(self, interaction: discord.Interaction):
        player: voicelink.Player = interaction.guild.voice_client
        if not player:
            return await interaction.response.send_message(get_lang(interaction.guild_id, 'noPlayer'), ephemeral=True)
        
        if interaction.user not in player.channel.members:
            if not interaction.user.guild_permissions.manage_guild:
                return await interaction.response.send_message(player.get_msg('notInChannel').format(interaction.user.mention, player.channel.mention), ephemeral=True)       
         
        if not await player.is_privileged(interaction.user):    
            if interaction.user in player.shuffle_votes:
                return await interaction.response.send_message(player.get_msg('voted'), ephemeral=True)
            else:
                player.shuffle_votes.add(interaction.user)
                if len(player.shuffle_votes) >= (required := player.required()):
                    pass
                else:
                    return await interaction.response.send_message(player.get_msg('shuffleVote').format(interaction.user, len(player.skip_votes), required))
        replacement = player.queue.tracks()
        if len(replacement) < 3:
            return await interaction.response.send_message(player.get_msg('shuffleError'))
        shuffle(replacement)
        player.queue.replace("Queue", replacement)
        player.shuffle_votes.clear()
        await interaction.response.send_message(player.get_msg('shuffled'))

    @app_commands.command(
        name = "move",
        description = "Moves the specified song to the specified position."
    )
    @app_commands.describe(
        track = "The track to move. Example: 2",
        position = "The new position to move the track to. Exmaple: 1"
    )
    @app_commands.checks.cooldown(2, 15.0, key=lambda i: (i.guild_id))
    @app_commands.guild_only()
    async def move(self, interaction: discord.Interaction, track: int, position: int ):
        player: voicelink.Player = interaction.guild.voice_client
        if not player:
            return await interaction.response.send_message(get_lang(interaction.guild_id, 'noPlayer'), ephemeral=True)
        
        if interaction.user not in player.channel.members:
            if not interaction.user.guild_permissions.manage_guild:
                return await interaction.response.send_message(player.get_msg('notInChannel').format(interaction.user.mention, player.channel.mention), ephemeral=True)       
         
        if not await player.is_privileged(interaction.user):
            return await interaction.response.send_message(player.get_msg('missingPerms_pos'), ephemeral=True)

        player.queue.swap(track, position)
        await interaction.response.send_message(player.get_msg('moved').format(track, position))
    
    @app_commands.command(
        name = "lyrics",
        description = "Displays lyrics for the playing track."
    )
    @app_commands.describe(
        name = "Searches for your query and displays the reutned lyrics.",
    )
    @app_commands.checks.cooldown(2, 60.0, key=lambda i: (i.guild_id))
    @app_commands.guild_only()
    async def lyrics(self, interaction: discord.Interaction, name: str = None):
        player: voicelink.Player = interaction.guild.voice_client
        
        if not name:
            if not player or not player.is_playing:
                return await interaction.response.send_message(get_lang(interaction.guild_id, 'noTrackPlaying'), ephemeral=True)
            name = player.current.title + " " + player.current.author
        await interaction.response.defer()
        song = await getLyrics(name)
        if not song:
            return await interaction.followup.send(get_lang(interaction.guild_id, 'lyricsNotFound'), ephemeral=True)

        view = LyricsView(name=name, source={_: re.findall(r'.*\n(?:.*\n){,22}', v) for _, v in song.items()}, author=interaction.user)
        await interaction.followup.send(embed=view.build_embed(), view=view)
        view.response = await interaction.original_response()

    @app_commands.command(
        name = "swapdj",
        description = "Transfer dj to another."
    )
    @app_commands.describe(
        member = "Choose a member to transfer the dj role."
    )
    @app_commands.guild_only()
    async def swapdj(self, interaction: discord.Interaction, member: discord.Member):
        player: voicelink.Player = interaction.guild.voice_client
        if not player:
            return await interaction.response.send_message(get_lang(interaction.guild_id, 'noPlayer'), ephemeral=True)
        
        if interaction.user not in player.channel.members:
            if not interaction.user.guild_permissions.manage_guild:
                return await interaction.response.send_message(player.get_msg('notInChannel').format(interaction.user.mention, player.channel.mention), ephemeral=True)       
         
        if player.dj.id != interaction.user.id or player.settings.get('dj', False):
            return await interaction.response.send_message(player.get_msg('notdj').format(f"<@&{player.settings['dj']}>" if player.settings.get('dj') else player.dj.mention), ephemeral=True)
        
        if player.dj.id == member.id or member.bot:
            return await interaction.response.send_message(player.get_msg('djToMe'), ephemeral=True)
        
        if member not in player.channel.members:
            return await interaction.response.send_message(player.get_msg('djnotinchannel').format(member), ephemeral=True)
        
        player.dj = member
        await interaction.response.send_message(player.get_msg('djswap').format(member))


    @app_commands.command(
        name = "chapters",
        description = "Lists all chapters of the currently playing song (if any)."
    )
    @app_commands.checks.cooldown(2, 30.0, key=lambda i: (i.guild_id))
    @app_commands.guild_only()
    async def chapters(self, interaction: discord.Interaction):
        player: voicelink.Player = interaction.guild.voice_client
        if not player:
            return await interaction.response.send_message(get_lang(interaction.guild_id, 'noPlayer'), ephemeral=True)
        
        if interaction.user not in player.channel.members:
            if not interaction.user.guild_permissions.manage_guild:
                return await interaction.response.send_message(player.get_msg('notInChannel').format(interaction.user.mention, player.channel.mention), ephemeral=True)       
         
        if not (track := player.current):
            return await interaction.response.send_message(player.get_msg('noTrackPlaying'), ephemeral=True)
        if not await player.is_privileged(interaction.user):
            return await interaction.response.send_message(player.get_msg('missingPerms_pos'), ephemeral=True)
            
        if track.source != 'youtube':
            return await interaction.response.send_message(player.get_msg('chatpersNotSupport'), ephemeral=True)

        request_uri = "https://youtube.googleapis.com/youtube/v3/videos?part=snippet&id={videoId}&key={key}".format(videoId=track.identifier, key=youtube_api_key)

        data = await requests_api(request_uri)
        if not data:
            return await interaction.response.send_message(player.get_msg('noChaptersFound'), ephemeral=True)

        try:
            desc = data['items'][0]['snippet']['description']
        except KeyError:
            return await interaction.response.send_message(player.get_msg('noChaptersFound'), ephemeral=True)
        
        chapters = re.findall(r"(?P<timestamp>\d+:\d+|\d+:\d+:\d+) (?P<desc>.+)", desc)
        if not chapters:
            return await interaction.response.send_message(player.get_msg('noChaptersFound'), ephemeral=True)

        view = ChapterView(player, chapters, author=interaction.user)
        await interaction.response.send_message(view=view)
        view.response = await interaction.original_response()

    @app_commands.command(
        name = "autoplay",
        description = "Toggles autoplay mode, it will automatically queue the best songs to play."
    )
    @app_commands.guild_only()
    async def autoplay(self, interaction: discord.Interaction):
        player: voicelink.Player = interaction.guild.voice_client
        if not player:
            return await interaction.response.send_message(get_lang(interaction.guild_id, 'noPlayer'), ephemeral=True)
        
        if not await player.is_privileged(interaction.user):
            return await interaction.response.send_message(player.get_msg('missingPerms_autoplay'), ephemeral=True)

        check = not player.settings.get("autoplay", False)
        player.settings['autoplay'] = check
        await interaction.response.send_message(player.get_msg('autoplay').format(player.get_msg('enabled') if check else player.get_msg('disabled')))

        if not player.is_playing:
            await player.do_next()

    @app_commands.command(
        name = "help",
        description = "Lists all the commands in Vocard."
    )
    @app_commands.autocomplete(category=help_autocomplete)
    @app_commands.guild_only()
    async def help(self, interaction: discord.Interaction, category: str = "News") -> None:
        if category not in self.bot.cogs:
            category = "News"
        view = HelpView(self.bot, interaction.user)
        embed = view.build_embed(category)
        await interaction.response.send_message(embed=embed, view=view)
        view.response = await interaction.original_response()

    @app_commands.command(
        name = "ping",
        description = "Test if the bot is alive, and see the delay between your commands and my response."
    )
    @app_commands.guild_only()
    async def ping(self, interaction: discord.Interaction):
        player: voicelink.Player = interaction.guild.voice_client
        embed = discord.Embed(color=embed_color)
        embed.add_field(name=get_lang(interaction.guild_id, 'pingTitle1'), value=get_lang(interaction.guild_id, 'pingfield1').format("0", "0", self.bot.latency, '😭' if self.bot.latency > 5 else ('😨' if self.bot.latency > 1 else '👌'), "St Louis, MO, United States"))
        if player:
            embed.add_field(name=get_lang(interaction.guild_id, 'pingTitle2'), value=get_lang(interaction.guild_id, 'pingfield2').format(player.node._identifier, player.ping, player.node.player_count, player.channel.rtc_region), inline=False)

        await interaction.response.send_message(embed=embed)
        
async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Basic(bot))