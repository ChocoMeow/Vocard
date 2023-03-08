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
    embed_color,
    cooldown_check,
    get_aliases
)

from addons import getLyrics
from views import SearchView, ListView, LinkView, LyricsView, ChapterView, HelpView
from validators import url
from random import shuffle

searchPlatform = {
    "youtube": "ytsearch",
    "youtubemusic": "ytmsearch",
    "soundcloud": "scsearch",
    "apple": "amsearch",
}

async def connect_channel(ctx: commands.Context, channel: discord.VoiceChannel = None) -> voicelink.Player:
    try:
        channel = channel or ctx.author.voice.channel
    except:
        raise voicelink.VoicelinkException(get_lang(ctx.guild.id, 'noChannel'))

    check = channel.permissions_for(ctx.guild.me)
    if check.connect == False or check.speak == False:
        raise voicelink.VoicelinkException(
            get_lang(ctx.guild.id, 'noPermission'))

    player: voicelink.Player = await channel.connect(cls=voicelink.Player(ctx.bot, channel, ctx))
    return player

async def nowplay(ctx: commands.Context, player: voicelink.Player):
    track = player.current
    if not track:
        return await ctx.send(player.get_msg('noTrackPlaying'), ephemeral=True)

    upnext = "\n".join(f"`{index}.` `[{track.formatLength}]` [{track.title[:30]}]({track.uri})" for index, track in enumerate(
        player.queue.tracks()[:2], start=2))
    embed = discord.Embed(description=player.get_msg(
        'nowplayingDesc').format(track.title), color=embed_color)
    embed.set_author(name=track.requester if track.requester else ctx.bot,
                     icon_url=track.requester.display_avatar.url if track.requester else ctx.me.display_avatar.url)

    if upnext:
        embed.add_field(name=player.get_msg('nowplayingField'), value=upnext)
    pbar = "".join(":radio_button:" if i == round(
        player.position // round(track.length // 15)) else "▬" for i in range(15))
    icon = ":red_circle:" if track.is_stream else (
        ":pause_button:" if player.is_paused else ":arrow_forward:")

    embed.add_field(
        name="\u2800", value=f"{icon} {pbar} **[{ctime(player.position)}/{track.formatLength}]**", inline=False)

    return await ctx.send(embed=embed, view=LinkView(player.get_msg('nowplayingLink').format(track.source), track.emoji, track.uri))


async def help_autocomplete(ctx: commands.Context, current: str) -> list:
    return [app_commands.Choice(name=c.capitalize(), value=c) for c in ctx.bot.cogs if c not in ["Nodes", "Task"] and current in c]


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
        self.bot.tree.remove_command(
            self.ctx_menu.name, type=self.ctx_menu.type)

    @commands.hybrid_command(name="connect", aliases=get_aliases("connect"))
    @app_commands.describe(channel="Provide a channel to connect.")
    @commands.dynamic_cooldown(cooldown_check, commands.BucketType.guild)
    async def connect(self, ctx: commands.Context, channel: discord.VoiceChannel = None) -> None:
        "Connect to a voice channel."
        try:
            player = await connect_channel(ctx, channel)
        except discord.errors.ClientException:
            return await ctx.send(get_lang(ctx.guild.id, "alreadyConnected"))

        await ctx.send(player.get_msg('connect').format(player.channel))

    @commands.hybrid_command(name="play", aliases=get_aliases("play"))
    @app_commands.describe(query="Input a query or a searchable link.")
    @commands.dynamic_cooldown(cooldown_check, commands.BucketType.guild)
    async def play(self, ctx: commands.Context, *, query: str) -> None:
        "Loads your input and added it to the queue."
        player: voicelink.Player = ctx.guild.voice_client
        if not player:
            player = await connect_channel(ctx)

        if ctx.author not in player.channel.members:
            if not ctx.author.guild_permissions.manage_guild:
                return await ctx.send(player.get_msg('notInChannel').format(ctx.author.mention, player.channel.mention), ephemeral=True)

        tracks = await player.get_tracks(query, requester=ctx.author)
        if not tracks:
            return await ctx.send(player.get_msg('noTrackFound'))

        try:
            if isinstance(tracks, voicelink.Playlist):
                index = await player.add_track(tracks.tracks)
                await ctx.send(player.get_msg('playlistLoad').format(tracks.name, index))
            else:
                position = await player.add_track(tracks[0])
                await ctx.send((f"`{player.get_msg('live')}`" if tracks[0].is_stream else "") + (player.get_msg('trackLoad_pos').format(tracks[0].title, tracks[0].author, tracks[0].formatLength, position) if position >= 1 and player.is_playing else player.get_msg('trackLoad').format(tracks[0].title, tracks[0].author, tracks[0].formatLength)))
        except voicelink.QueueFull as e:
            await ctx.send(e)
        finally:
            if not player.is_playing:
                await player.do_next()

    @commands.dynamic_cooldown(cooldown_check, commands.BucketType.guild)
    async def _play(self, ctx: commands.Context, message: discord.Message):
        query = ""
        if message.content:
            url = re.findall(
                "http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+", message.content)
            if url:
                query = url[0]
        elif message.attachments:
            query = message.attachments[0].url

        if not query:
            return await ctx.send(get_lang(ctx.guild.id, key="noPlaySource"), ephemeral=True)

        player: voicelink.Player = ctx.guild.voice_client
        if not player:
            player = await connect_channel(ctx)

        if ctx.author not in player.channel.members:
            if not ctx.author.guild_permissions.manage_guild:
                return await ctx.send(player.get_msg('notInChannel').format(ctx.author.mention, player.channel.mention), ephemeral=True)

        tracks = await player.get_tracks(query, requester=ctx.author)
        if not tracks:
            return await ctx.send(player.get_msg('noTrackFound'))

        try:
            if isinstance(tracks, voicelink.Playlist):
                index = await player.add_track(tracks.tracks)
                await ctx.send(player.get_msg('playlistLoad').format(tracks.name, index))
            else:
                position = await player.add_track(tracks[0])
                await ctx.send((f"`{player.get_msg('live')}`" if tracks[0].is_stream else "") + (player.get_msg('trackLoad_pos').format(tracks[0].title, tracks[0].author, tracks[0].formatLength, position) if position >= 1 and player.is_playing else player.get_msg('trackLoad').format(tracks[0].title, tracks[0].author, tracks[0].formatLength)))
        except voicelink.QueueFull as e:
            await ctx.send(e)
        finally:
            if not player.is_playing:
                await player.do_next()

    @commands.hybrid_command(name="search", aliases=get_aliases("search"))
    @app_commands.describe(
        query="Input the name of the song.",
        platform="Select the platform you want to search."
    )
    @app_commands.choices(platform=[
        app_commands.Choice(name="Youtube", value="Youtube"),
        app_commands.Choice(name="Youtube Music", value="YoutubeMusic"),
        app_commands.Choice(name="Spotify", value="Spotify"),
        app_commands.Choice(name="SoundCloud", value="SoundCloud"),
        app_commands.Choice(name="Apple Music", value="Apple")
    ])
    @commands.dynamic_cooldown(cooldown_check, commands.BucketType.guild)
    async def search(self, ctx: commands.Context, *, query: str, platform: str = "Youtube"):
        "Loads your input and added it to the queue."
        player: voicelink.Player = ctx.guild.voice_client
        if not player:
            player = await connect_channel(ctx)

        if ctx.author not in player.channel.members:
            if not ctx.author.guild_permissions.manage_guild:
                return await ctx.send(player.get_msg('notInChannel').format(ctx.author.mention, player.channel.mention), ephemeral=True)

        if url(query):
            return await ctx.send(player.get_msg('noLinkSupport'), ephemeral=True)

        platform = platform.lower()
        if platform != 'spotify':
            query_platform = searchPlatform.get(platform, 'ytsearch') + f":{query}"
            tracks = await player.get_tracks(query=query_platform, requester=ctx.author)
        else:
            tracks = await player.spotifySearch(query=query, requester=ctx.author)

        if not tracks:
            return await ctx.send(player.get_msg('noTrackFound'))

        query_track = "\n".join(
            f"`{index}.` `[{track.formatLength}]` **{track.title[:35]}**" for index, track in enumerate(tracks[0:10], start=1))
        embed = discord.Embed(title=player.get_msg('searchTitle').format(query), description=player.get_msg(
            'searchDesc').format(emoji_source(platform), platform, len(tracks[0:10]), query_track), color=embed_color)
        view = SearchView(tracks=tracks[0:10], lang=player.lang)
        message = await ctx.send(embed=embed, view=view, ephemeral=True)
        view.response = message
        await view.wait()
        if view.values is not None:
            msg = ""
            for value in view.values:
                track = tracks[int(value.split(". ")[0]) - 1]
                position = await player.add_track(track)
                msg += ((f"`{player.get_msg('live')}`" if track.is_stream else "") + (player.get_msg('trackLoad_pos').format(track.title, track.author, track.formatLength,
                        position) if position >= 1 else player.get_msg('trackLoad').format(track.title, track.author, track.formatLength)))
            await ctx.send(msg)

            if not player.is_playing:
                await player.do_next()

    @commands.hybrid_command(name="pause", aliases=get_aliases("pause"))
    @commands.dynamic_cooldown(cooldown_check, commands.BucketType.guild)
    async def pause(self, ctx: commands.Context):
        "Pause the music."
        player: voicelink.Player = ctx.guild.voice_client
        if not player:
            return await ctx.send(get_lang(ctx.guild.id, 'noPlayer'), ephemeral=True)

        if ctx.author not in player.channel.members:
            if not ctx.author.guild_permissions.manage_guild:
                return await ctx.send(player.get_msg('notInChannel').format(ctx.author.mention, player.channel.mention), ephemeral=True)

        if player.is_paused:
            return await ctx.send(player.get_msg('pauseError'))

        if not await player.is_privileged(ctx.author):
            if ctx.author in player.pause_votes:
                return await ctx.send(player.get_msg('voted'), ephemeral=True)
            else:
                player.pause_votes.add(ctx.author)
                if len(player.pause_votes) >= (required := player.required()):
                    pass
                else:
                    return await ctx.send(player.get_msg('pauseVote').format(ctx.author, len(player.pause_votes), required))

        await player.set_pause(True)
        player.pause_votes.clear()
        await ctx.send(player.get_msg('paused').format(ctx.author))

    @commands.hybrid_command(name="resume", aliases=get_aliases("resume"))
    @commands.dynamic_cooldown(cooldown_check, commands.BucketType.guild)
    async def resume(self, ctx: commands.Context):
        "Resume the music."
        player: voicelink.Player = ctx.guild.voice_client
        if not player:
            return await ctx.send(get_lang(ctx.guild.id, 'noPlayer'), ephemeral=True)

        if ctx.author not in player.channel.members:
            if not ctx.author.guild_permissions.manage_guild:
                return await ctx.send(player.get_msg('notInChannel').format(ctx.author.mention, player.channel.mention), ephemeral=True)

        if not player.is_paused:
            return await ctx.send(player.get_msg('resumeError'))

        if not await player.is_privileged(ctx.author):
            if ctx.author in player.resume_votes:
                return await ctx.send(player.get_msg('voted'), ephemeral=True)
            else:
                player.resume_votes.add(ctx.author)
                if len(player.resume_votes) >= (required := player.required()):
                    pass
                else:
                    return await ctx.send(player.get_msg('resumeVote').format(ctx.author, len(player.resume_votes), required))

        await player.set_pause(False)
        player.resume_votes.clear()
        await ctx.send(player.get_msg('resumed').format(ctx.author))

    @commands.hybrid_command(name="skip", aliases=get_aliases("skip"))
    @app_commands.describe(index="Enter a index that you want to skip to.")
    @commands.dynamic_cooldown(cooldown_check, commands.BucketType.guild)
    async def skip(self, ctx: commands.Context, index: int = 0):
        "Skips to the next song or skips to the specified song."
        player: voicelink.Player = ctx.guild.voice_client
        if not player:
            return await ctx.send(get_lang(ctx.guild.id, 'noPlayer'), ephemeral=True)

        if ctx.author not in player.channel.members:
            if not ctx.author.guild_permissions.manage_guild:
                return await ctx.send(player.get_msg('notInChannel').format(ctx.author.mention, player.channel.mention), ephemeral=True)

        if not player.is_playing:
            return await ctx.send(player.get_msg('skipError'), ephemeral=True)

        if not await player.is_privileged(ctx.author):
            if ctx.author == player.current.requester:
                pass
            elif ctx.author in player.skip_votes:
                return await ctx.send(player.get_msg('voted'), ephemeral=True)
            else:
                player.skip_votes.add(ctx.author)
                if len(player.skip_votes) >= (required := player.required()):
                    pass
                else:
                    return await ctx.send(player.get_msg('skipVote').format(ctx.author, len(player.skip_votes), required))

        if not player.node._available:
            return await ctx.send(player.get_msg('nodeReconnect'))

        if index:
            player.queue.skipto(index)

        await ctx.send(player.get_msg('skipped').format(ctx.author))

        if player.queue._repeat == 1:
            player.queue.set_repeat("off")
        await player.stop()

    @commands.hybrid_command(name="back", aliases=get_aliases("back"))
    @app_commands.describe(index="Enter a index that you want to skip back to.")
    @commands.dynamic_cooldown(cooldown_check, commands.BucketType.guild)
    async def back(self, ctx: commands.Context, index: int = 1):
        "Skips back to the previous song or skips to the specified previous song."
        player: voicelink.Player = ctx.guild.voice_client
        if not player:
            return await ctx.send(get_lang(ctx.guild.id, 'noPlayer'), ephemeral=True)

        if ctx.author not in player.channel.members:
            if not ctx.author.guild_permissions.manage_guild:
                return await ctx.send(player.get_msg('notInChannel').format(ctx.author.mention, player.channel.mention), ephemeral=True)

        if not await player.is_privileged(ctx.author):
            if ctx.author in player.previous_votes:
                return await ctx.send(player.get_msg('voted'), ephemeral=True)
            else:
                player.previous_votes.add(ctx.author)
                if len(player.previous_votes) >= (required := player.required()):
                    pass
                else:
                    return await ctx.send(player.get_msg('backVote').format(ctx.author, len(player.previous_votes), required))

        if not player.node._available:
            return await ctx.send(player.get_msg('nodeReconnect'))

        if not player.is_playing:
            player.queue.backto(index)
            await player.do_next()
        else:
            player.queue.backto(index + 1)
            await player.stop()

        await ctx.send(player.get_msg('backed').format(ctx.author))

        if player.queue._repeat == 1:
            player.queue.set_repeat("off")

    @commands.hybrid_command(name="seek", aliases=get_aliases("seek"))
    @app_commands.describe(position="Input position. Exmaple: 1:20.")
    @commands.dynamic_cooldown(cooldown_check, commands.BucketType.guild)
    async def seek(self, ctx: commands.Context, position: str):
        "Change the player position."
        player: voicelink.Player = ctx.guild.voice_client
        if not player:
            return await ctx.send(get_lang(ctx.guild.id, 'noPlayer'), ephemeral=True)

        if ctx.author not in player.channel.members:
            if not ctx.author.guild_permissions.manage_guild:
                return await ctx.send(player.get_msg('notInChannel').format(ctx.author.mention, player.channel.mention), ephemeral=True)

        if not player.current:
            return await ctx.send(player.get_msg('noTrackPlaying'), ephemeral=True)
        if not await player.is_privileged(ctx.author):
            return await ctx.send(player.get_msg('missingPerms_pos'), ephemeral=True)
        if player.position == 0:
            return await ctx.send(player.get_msg('noTrackPlaying'), ephemeral=True)

        num = formatTime(position)
        if num is None:
            return await ctx.send(player.get_msg('timeFormatError'), ephemeral=True)

        await player.seek(num)
        await ctx.send(player.get_msg('seek').format(position))

    @commands.hybrid_command(name="queue", aliases=get_aliases("queue"))
    @commands.dynamic_cooldown(cooldown_check, commands.BucketType.guild)
    async def queue(self, ctx: commands.Context):
        "Display the players queue songs in your queue."
        player: voicelink.Player = ctx.guild.voice_client
        if not player:
            return await ctx.send(get_lang(ctx.guild.id, 'noPlayer'), ephemeral=True)

        if ctx.author not in player.channel.members:
            if not ctx.author.guild_permissions.manage_guild:
                return await ctx.send(player.get_msg('notInChannel').format(ctx.author.mention, player.channel.mention), ephemeral=True)

        if player.queue.is_empty:
            return await nowplay(ctx, player)
        view = ListView(player=player, author=ctx.author)
        message = await ctx.send(embed=view.build_embed(), view=view)
        view.response = message

    @commands.hybrid_command(name="history", aliases=get_aliases("history"))
    @commands.dynamic_cooldown(cooldown_check, commands.BucketType.guild)
    async def history(self, ctx: commands.Context):
        "Display the players queue songs in your history queue."
        player: voicelink.Player = ctx.guild.voice_client
        if not player:
            return await ctx.send(get_lang(ctx.guild.id, 'noPlayer'), ephemeral=True)

        if ctx.author not in player.channel.members:
            if not ctx.author.guild_permissions.manage_guild:
                return await ctx.send(player.get_msg('notInChannel').format(ctx.author.mention, player.channel.mention), ephemeral=True)

        if not player.queue.history():
            return await nowplay(ctx, player)

        view = ListView(player=player, author=ctx.author, isQueue=False)
        message = await ctx.send(embed=view.build_embed(), view=view)
        view.response = message

    @commands.hybrid_command(name="leave", aliases=get_aliases("leave"))
    @commands.dynamic_cooldown(cooldown_check, commands.BucketType.guild)
    async def leave(self, ctx: commands.Context):
        "Disconnects the bot from your voice channel and chears the queue."
        player: voicelink.Player = ctx.guild.voice_client
        if not player:
            return await ctx.send(get_lang(ctx.guild.id, 'noPlayer'), ephemeral=True)

        if ctx.author not in player.channel.members:
            if not ctx.author.guild_permissions.manage_guild:
                return await ctx.send(player.get_msg('notInChannel').format(ctx.author.mention, player.channel.mention), ephemeral=True)

        if not await player.is_privileged(ctx.author):
            if ctx.author in player.stop_votes:
                return await ctx.send(player.get_msg('voted'), ephemeral=True)
            else:
                player.stop_votes.add(ctx.author)
                if len(player.stop_votes) >= (required := player.required(leave=True)):
                    pass
                else:
                    return await ctx.send(player.get_msg('leaveVote').format(ctx.author, len(player.stop_votes), required))

        await ctx.send(player.get_msg('left').format(ctx.author))
        await player.teardown()

    @commands.hybrid_command(name="nowplaying", aliases=get_aliases("nowplaying"))
    @commands.dynamic_cooldown(cooldown_check, commands.BucketType.guild)
    async def nowplaying(self, ctx: commands.Context):
        "Shows details of the current track."
        player: voicelink.Player = ctx.guild.voice_client
        if not player:
            return await ctx.send(get_lang(ctx.guild.id, 'noPlayer'), ephemeral=True)

        if ctx.author not in player.channel.members:
            if not ctx.author.guild_permissions.manage_guild:
                return await ctx.send(player.get_msg('notInChannel').format(ctx.author.mention, player.channel.mention), ephemeral=True)

        await nowplay(ctx, player)

    @commands.hybrid_command(name="loop", aliases=get_aliases("loop"))
    @app_commands.describe(mode="Choose a looping mode.")
    @app_commands.choices(mode=[
        app_commands.Choice(name='Off', value='off'),
        app_commands.Choice(name='Track', value='track'),
        app_commands.Choice(name='Queue', value='queue')
    ])
    @commands.dynamic_cooldown(cooldown_check, commands.BucketType.guild)
    async def loop(self, ctx: commands.Context, mode: str):
        "Changes Loop mode."
        player: voicelink.Player = ctx.guild.voice_client
        if not player:
            return await ctx.send(get_lang(ctx.guild.id, 'noPlayer'), ephemeral=True)

        if ctx.author not in player.channel.members:
            if not ctx.author.guild_permissions.manage_guild:
                return await ctx.send(player.get_msg('notInChannel').format(ctx.author.mention, player.channel.mention), ephemeral=True)

        if not await player.is_privileged(ctx.author):
            return await ctx.send(player.get_msg('missingPerms_mode'), ephemeral=True)

        if mode.lower() not in ['off', 'track', 'queue']:
            mode = "off"
        player.queue.set_repeat(mode)
        await ctx.send(player.get_msg('repeat').format(mode.capitalize()))

    @commands.hybrid_command(name="clear", aliases=get_aliases("clear"))
    @app_commands.describe(queue="Choose a queue that you want to clear.")
    @app_commands.choices(queue=[
        app_commands.Choice(name='Queue', value='queue'),
        app_commands.Choice(name='History', value='history')
    ])
    @commands.dynamic_cooldown(cooldown_check, commands.BucketType.guild)
    async def clear(self, ctx: commands.Context, queue: str = "queue"):
        "Remove all the tracks in your queue or history queue."
        player: voicelink.Player = ctx.guild.voice_client
        if not player:
            return await ctx.send(get_lang(ctx.guild.id, 'noPlayer'), ephemeral=True)

        if ctx.author not in player.channel.members:
            if not ctx.author.guild_permissions.manage_guild:
                return await ctx.send(player.get_msg('notInChannel').format(ctx.author.mention, player.channel.mention), ephemeral=True)

        if not await player.is_privileged(ctx.author):
            return await ctx.send(player.get_msg('missingPerms_queue'), ephemeral=True)

        queue = queue.lower()
        if queue == 'history':
            player.queue.history_clear(player.is_playing)
        else:
            queue = "queue"
            player.queue.clear()

        await ctx.send(player.get_msg('cleared').format(queue.capitalize()))

    @commands.hybrid_command(name="remove", aliases=get_aliases("remove"))
    @app_commands.describe(
        position1="Input a position from the queue to be removed.",
        position2="Set the range of the queue to be removed.",
        member="Remove tracks requested by a specific member."
    )
    @commands.dynamic_cooldown(cooldown_check, commands.BucketType.guild)
    async def remove(self, ctx: commands.Context, position1: int, position2: int = None, member: discord.Member = None):
        "Removes specified track or a range of tracks from the queue."
        player: voicelink.Player = ctx.guild.voice_client
        if not player:
            return await ctx.send(get_lang(ctx.guild.id, 'noPlayer'), ephemeral=True)

        if ctx.author not in player.channel.members:
            if not ctx.author.guild_permissions.manage_guild:
                return await ctx.send(player.get_msg('notInChannel').format(ctx.author.mention, player.channel.mention), ephemeral=True)

        if not await player.is_privileged(ctx.author):
            return await ctx.send(player.get_msg('missingPerms_queue'), ephemeral=True)

        removedTrack = player.queue.remove(position1, position2, member)
        await ctx.send(player.get_msg('removed').format(removedTrack))

    @commands.hybrid_command(name="forward", aliases=get_aliases("forward"))
    @app_commands.describe(position="Input a amount that you to forward to. Exmaple: 1:20")
    @commands.dynamic_cooldown(cooldown_check, commands.BucketType.guild)
    async def forward(self, ctx: commands.Context, position: str = "10"):
        "Forwards by a certain amount of time in the current track. The default is 10 seconds."
        player: voicelink.Player = ctx.guild.voice_client
        if not player:
            return await ctx.send(get_lang(ctx.guild.id, 'noPlayer'), ephemeral=True)

        if ctx.author not in player.channel.members:
            if not ctx.author.guild_permissions.manage_guild:
                return await ctx.send(player.get_msg('notInChannel').format(ctx.author.mention, player.channel.mention), ephemeral=True)

        if not player.current:
            return await ctx.send(player.get_msg('noTrackPlaying'), ephemeral=True)
        if not await player.is_privileged(ctx.author):
            return await ctx.send(player.get_msg('missingPerms_pos'), ephemeral=True)

        num = formatTime(position)
        if num is None:
            return await ctx.send(player.get_msg('timeFormatError'), ephemeral=True)

        await player.seek(player.position + num)
        await ctx.send(player.get_msg('forward').format(ctime(player.position + num)))

    @commands.hybrid_command(name="rewind", aliases=get_aliases("rewind"))
    @app_commands.describe(position="Input a amount that you to rewind to. Exmaple: 1:20")
    @commands.dynamic_cooldown(cooldown_check, commands.BucketType.guild)
    async def rewind(self, ctx: commands.Context, position: str = "10"):
        "Rewind by a certain amount of time in the current track. The default is 10 seconds."
        player: voicelink.Player = ctx.guild.voice_client
        if not player:
            return await ctx.send(get_lang(ctx.guild.id, 'noPlayer'), ephemeral=True)

        if ctx.author not in player.channel.members:
            if not ctx.author.guild_permissions.manage_guild:
                return await ctx.send(player.get_msg('notInChannel').format(ctx.author.mention, player.channel.mention), ephemeral=True)

        if not player.current:
            return await ctx.send(player.get_msg('noTrackPlaying'), ephemeral=True)

        if not await player.is_privileged(ctx.author):
            return await ctx.send(player.get_msg('missingPerms_pos'), ephemeral=True)

        num = formatTime(position)
        if num is None:
            return await ctx.send(player.get_msg('timeFormatError'), ephemeral=True)

        await player.seek(player.position - num)
        await ctx.send(player.get_msg('rewind').format(ctime(player.position - num)))

    @commands.hybrid_command(name="replay", aliases=get_aliases("replay"))
    @commands.dynamic_cooldown(cooldown_check, commands.BucketType.guild)
    async def replay(self, ctx: commands.Context):
        "Reset the progress of the current song."
        player: voicelink.Player = ctx.guild.voice_client
        if not player:
            return await ctx.send(get_lang(ctx.guild.id, 'noPlayer'), ephemeral=True)

        if ctx.author not in player.channel.members:
            if not ctx.author.guild_permissions.manage_guild:
                return await ctx.send(player.get_msg('notInChannel').format(ctx.author.mention, player.channel.mention), ephemeral=True)

        if not player.current:
            return await ctx.send(player.get_msg('noTrackPlaying'), ephemeral=True)

        if not await player.is_privileged(ctx.author):
            return await ctx.send(player.get_msg('missingPerms_pos'), ephemeral=True)

        await player.seek(0)
        await ctx.send(player.get_msg('replay'))

    @commands.hybrid_command(name="shuffle", aliases=get_aliases("shuffle"))
    @commands.dynamic_cooldown(cooldown_check, commands.BucketType.guild)
    async def shuffle(self, ctx: commands.Context):
        "Randomizes the tracks in the queue."
        player: voicelink.Player = ctx.guild.voice_client
        if not player:
            return await ctx.send(get_lang(ctx.guild.id, 'noPlayer'), ephemeral=True)

        if ctx.author not in player.channel.members:
            if not ctx.author.guild_permissions.manage_guild:
                return await ctx.send(player.get_msg('notInChannel').format(ctx.author.mention, player.channel.mention), ephemeral=True)

        if not await player.is_privileged(ctx.author):
            if ctx.author in player.shuffle_votes:
                return await ctx.send(player.get_msg('voted'), ephemeral=True)
            else:
                player.shuffle_votes.add(ctx.author)
                if len(player.shuffle_votes) >= (required := player.required()):
                    pass
                else:
                    return await ctx.send(player.get_msg('shuffleVote').format(ctx.author, len(player.skip_votes), required))
        replacement = player.queue.tracks()
        if len(replacement) < 3:
            return await ctx.send(player.get_msg('shuffleError'))
        shuffle(replacement)
        player.queue.replace("Queue", replacement)
        player.shuffle_votes.clear()
        await ctx.send(player.get_msg('shuffled'))

    @commands.hybrid_command(name="move", aliases=get_aliases("move"))
    @app_commands.describe(
        position1="The track to move. Example: 2",
        position2="The new position to move the track to. Exmaple: 1"
    )
    @commands.dynamic_cooldown(cooldown_check, commands.BucketType.guild)
    async def move(self, ctx: commands.Context, position1: int, position2: int):
        "Moves the specified song to the specified position."
        player: voicelink.Player = ctx.guild.voice_client
        if not player:
            return await ctx.send(get_lang(ctx.guild.id, 'noPlayer'), ephemeral=True)

        if ctx.author not in player.channel.members:
            if not ctx.author.guild_permissions.manage_guild:
                return await ctx.send(player.get_msg('notInChannel').format(ctx.author.mention, player.channel.mention), ephemeral=True)

        if not await player.is_privileged(ctx.author):
            return await ctx.send(player.get_msg('missingPerms_pos'), ephemeral=True)

        player.queue.swap(position1, position2)
        await ctx.send(player.get_msg('moved').format(position1, position2))

    @commands.hybrid_command(name="lyrics", aliases=get_aliases("lyrics"))
    @app_commands.describe(name="Searches for your query and displays the reutned lyrics.")
    @commands.dynamic_cooldown(cooldown_check, commands.BucketType.guild)
    async def lyrics(self, ctx: commands.Context, name: str = None):
        "Displays lyrics for the playing track."
        player: voicelink.Player = ctx.guild.voice_client

        if not name:
            if not player or not player.is_playing:
                return await ctx.send(get_lang(ctx.guild.id, 'noTrackPlaying'), ephemeral=True)
            name = player.current.title + " " + player.current.author
        await ctx.defer()
        song = await getLyrics(name)
        if not song:
            return await ctx.send(get_lang(ctx.guild.id, 'lyricsNotFound'), ephemeral=True)

        view = LyricsView(name=name, source={_: re.findall(
            r'.*\n(?:.*\n){,22}', v) for _, v in song.items()}, author=ctx.author)
        message = await ctx.send(embed=view.build_embed(), view=view)
        view.response = message

    @commands.hybrid_command(name="swapdj", aliases=get_aliases("swapdj"))
    @app_commands.describe(member="Choose a member to transfer the dj role.")
    @commands.dynamic_cooldown(cooldown_check, commands.BucketType.guild)
    async def swapdj(self, ctx: commands.Context, member: discord.Member):
        "Transfer dj to another."
        player: voicelink.Player = ctx.guild.voice_client
        if not player:
            return await ctx.send(get_lang(ctx.guild.id, 'noPlayer'), ephemeral=True)

        if ctx.author not in player.channel.members:
            if not ctx.author.guild_permissions.manage_guild:
                return await ctx.send(player.get_msg('notInChannel').format(ctx.author.mention, player.channel.mention), ephemeral=True)

        if player.dj.id != ctx.author.id or player.settings.get('dj', False):
            return await ctx.send(player.get_msg('notdj').format(f"<@&{player.settings['dj']}>" if player.settings.get('dj') else player.dj.mention), ephemeral=True)

        if player.dj.id == member.id or member.bot:
            return await ctx.send(player.get_msg('djToMe'), ephemeral=True)

        if member not in player.channel.members:
            return await ctx.send(player.get_msg('djnotinchannel').format(member), ephemeral=True)

        player.dj = member
        await ctx.send(player.get_msg('djswap').format(member))

    @commands.hybrid_command(name="chapters", aliases=get_aliases("chapters"))
    @commands.dynamic_cooldown(cooldown_check, commands.BucketType.guild)
    async def chapters(self, ctx: commands.Context):
        "Lists all chapters of the currently playing song (if any)."
        player: voicelink.Player = ctx.guild.voice_client
        if not player:
            return await ctx.send(get_lang(ctx.guild.id, 'noPlayer'), ephemeral=True)

        if ctx.author not in player.channel.members:
            if not ctx.author.guild_permissions.manage_guild:
                return await ctx.send(player.get_msg('notInChannel').format(ctx.author.mention, player.channel.mention), ephemeral=True)

        if not (track := player.current):
            return await ctx.send(player.get_msg('noTrackPlaying'), ephemeral=True)
        if not await player.is_privileged(ctx.author):
            return await ctx.send(player.get_msg('missingPerms_pos'), ephemeral=True)

        if track.source != 'youtube':
            return await ctx.send(player.get_msg('chatpersNotSupport'), ephemeral=True)

        request_uri = "https://youtube.googleapis.com/youtube/v3/videos?part=snippet&id={videoId}&key={key}".format(
            videoId=track.identifier, key=youtube_api_key)

        data = await requests_api(request_uri)
        if not data:
            return await ctx.send(player.get_msg('noChaptersFound'), ephemeral=True)

        try:
            desc = data['items'][0]['snippet']['description']
        except KeyError:
            return await ctx.send(player.get_msg('noChaptersFound'), ephemeral=True)

        chapters = re.findall(
            r"(?P<timestamp>\d+:\d+|\d+:\d+:\d+) (?P<desc>.+)", desc)
        if not chapters:
            return await ctx.send(player.get_msg('noChaptersFound'), ephemeral=True)

        view = ChapterView(player, chapters, author=ctx.author)
        message = await ctx.send(view=view)
        view.response = message

    @commands.hybrid_command(name="autoplay", aliases=get_aliases("autoplay"))
    @commands.dynamic_cooldown(cooldown_check, commands.BucketType.guild)
    async def autoplay(self, ctx: commands.Context):
        "Toggles autoplay mode, it will automatically queue the best songs to play."
        player: voicelink.Player = ctx.guild.voice_client
        if not player:
            return await ctx.send(get_lang(ctx.guild.id, 'noPlayer'), ephemeral=True)

        if not await player.is_privileged(ctx.author):
            return await ctx.send(player.get_msg('missingPerms_autoplay'), ephemeral=True)

        check = not player.settings.get("autoplay", False)
        player.settings['autoplay'] = check
        await ctx.send(player.get_msg('autoplay').format(player.get_msg('enabled') if check else player.get_msg('disabled')))

        if not player.is_playing:
            await player.do_next()

    @commands.hybrid_command(name="help", aliases=get_aliases("help"))
    @app_commands.autocomplete(category=help_autocomplete)
    @commands.dynamic_cooldown(cooldown_check, commands.BucketType.guild)
    async def help(self, ctx: commands.Context, category: str = "News") -> None:
        "Lists all the commands in Vocard."
        if category not in self.bot.cogs:
            category = "News"
        view = HelpView(self.bot, ctx.author)
        embed = view.build_embed(category)
        message = await ctx.send(embed=embed, view=view)
        view.response = message

    @commands.hybrid_command(name="ping", aliases=get_aliases("ping"))
    @commands.dynamic_cooldown(cooldown_check, commands.BucketType.guild)
    async def ping(self, ctx: commands.Context):
        "Test if the bot is alive, and see the delay between your commands and my response."
        player: voicelink.Player = ctx.guild.voice_client
        embed = discord.Embed(color=embed_color)
        embed.add_field(name=get_lang(ctx.guild.id, 'pingTitle1'), value=get_lang(ctx.guild.id, 'pingfield1').format(
            "0", "0", self.bot.latency, '😭' if self.bot.latency > 5 else ('😨' if self.bot.latency > 1 else '👌'), "St Louis, MO, United States"))
        if player:
            embed.add_field(name=get_lang(ctx.guild.id, 'pingTitle2'), value=get_lang(ctx.guild.id, 'pingfield2').format(
                player.node._identifier, player.ping, player.node.player_count, player.channel.rtc_region), inline=False)

        await ctx.send(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Basic(bot))
