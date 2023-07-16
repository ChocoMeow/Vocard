import discord
import voicelink

from io import StringIO
from discord import app_commands
from discord.ext import commands
from function import (
    time as ctime,
    get_playlist,
    create_account,
    checkroles,
    update_playlist,
    update_inbox,
    get_lang,
    playlist_name,
    settings,
    get_aliases,
    cooldown_check
)

from datetime import datetime
from views import PlaylistView, InboxView, HelpView

def assign_playlistId(existed: list) -> str:
    for i in range(200, 210):
        if str(i) not in existed:
            return str(i)

async def check_playlist_perms(userid: int, authorid: int, dId: str) -> dict:
    playlist = await get_playlist(authorid, 'playlist', dId)
    if not playlist or userid not in playlist['perms']['read']:
        return {}
    return playlist

async def check_playlist(ctx: commands.Context, name: str = None, full: bool = False, share: bool = True) -> dict:
    user = await get_playlist(ctx.author.id, 'playlist')
    if not user:
        return None
    await ctx.defer()
    if full:
        return user
    if not name:
        return {'playlist': user['200'], 'position': 1, 'id': "200"}

    for index, data in enumerate(user, start=1):
        playlist = user[data]
        if playlist['name'].lower() == name:
            if playlist['type'] == 'share' and share:
                playlist = await check_playlist_perms(ctx.author.id, playlist['user'], playlist['referId'])
                if not playlist or ctx.author.id not in playlist['perms']['read']:
                    return {'playlist': None, 'position': index, 'id': data}
            return {'playlist': playlist, 'position': index, 'id': data}
    return {'playlist': None, 'position': None, 'id': None}

async def search_playlist(url: str, requester: discord.Member, timeNeed=True):
    try:
        tracks = await voicelink.NodePool.get_node().get_tracks(url, requester=requester)
        tracks = {"name": tracks.name, "tracks": tracks.tracks}
        if timeNeed:
            time = 0
            for track in tracks['tracks']:
                time += track.length
    except:
        return None
    return tracks | ({'time': ctime(time)} if timeNeed else {})

class Playlists(commands.Cog, name="playlist"):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.description = "This is the Vocard playlist system. You can save your favorites and use Vocard to play on any server."

    async def playlist_autocomplete(self, interaction: discord.Interaction, current: str) -> list:
        playlists = playlist_name.get(str(interaction.user.id), None)
        if not playlists:
            playlists_raw = await get_playlist(interaction.user.id, 'playlist')
            playlists = playlist_name[str(interaction.user.id)] = [
                value['name'] for value in playlists_raw.values()] if playlists_raw else []
        if current:
            return [app_commands.Choice(name=p, value=p) for p in playlists if current in p]
        return [app_commands.Choice(name=p, value=p) for p in playlists]

    @commands.hybrid_group(
        name="playlist", 
        aliases=get_aliases("playlist"),
        invoke_without_command=True
    )
    async def playlist(self, ctx: commands.Context):
        view = HelpView(self.bot, ctx.author)
        embed = view.build_embed(self.qualified_name)
        message = await ctx.send(embed=embed, view=view)
        view.response = message

    @playlist.command(name="play", aliases=get_aliases("play"))
    @app_commands.describe(
        name="Input the name of your custom playlist",
        value="Play the specific track from your custom playlist."
    )
    @app_commands.autocomplete(name=playlist_autocomplete)
    @commands.dynamic_cooldown(cooldown_check, commands.BucketType.guild)
    async def play(self, ctx: commands.Context, name: str = None, value: int = None) -> None:
        "Play all songs from your favorite playlist."
        result = await check_playlist(ctx, name.lower() if name else None)
        if not result:
            return await create_account(ctx)
        if not result['playlist']:
            return await ctx.send(get_lang(ctx.guild.id, 'playlistNotFound').format(name), ephemeral=True)
        rank, max_p, max_t = await checkroles(ctx.author.id)
        if result['position'] > max_p:
            return await ctx.send(get_lang(ctx.guild.id, 'playlistNotAccess'), ephemeral=True)

        player: voicelink.Player = ctx.guild.voice_client
        if not player:
            player = await voicelink.connect_channel(ctx)

        if result['playlist']['type'] == 'link':
            tracks = await search_playlist(result['playlist']['uri'], ctx.author, timeNeed=False)
        else:
            if not result['playlist']['tracks']:
                return await ctx.send(get_lang(ctx.guild.id, 'playlistNoTrack').format(result['playlist']['name']), ephemeral=True)

            playtrack = []
            for track in result['playlist']['tracks'][:max_t]:
                playtrack.append(voicelink.Track(track_id=track, info=voicelink.decode(track), requester=ctx.author))
                    
            tracks = {"name": result['playlist']['name'], "tracks": playtrack}

        if not tracks:
            return await ctx.send(get_lang(ctx.guild.id, 'playlistNoTrack').format(result['playlist']['name']), ephemeral=True)

        if value and 0 < value <= (len(tracks['tracks'])):
            tracks['tracks'] = [tracks['tracks'][value - 1]]
        await player.add_track(tracks['tracks'])
        await ctx.send(get_lang(ctx.guild.id, 'playlistPlay').format(result['playlist']['name'], len(tracks['tracks'][:max_t])))

        if not player.is_playing:
            await player.do_next()

    @playlist.command(name="view", aliases=get_aliases("view"))
    @commands.dynamic_cooldown(cooldown_check, commands.BucketType.guild)
    async def view(self, ctx: commands.Context) -> None:
        "List all your playlist and all songs in your favourite playlist."
        user = await check_playlist(ctx, full=True)
        if not user:
            return await create_account(ctx)
        rank, max_p, max_t = await checkroles(ctx.author.id)

        results = []
        for index, data in enumerate(user, start=1):
            playlist = user[data]
            time = 0
            try:
                if playlist['type'] == 'link':
                    tracks = await search_playlist(playlist['uri'], requester=ctx.author)
                    results.append({'emoji': ('🔒' if max_p < index else '🔗'), 'id': data, 'time': tracks['time'], 'name': playlist['name'], 'tracks': tracks['tracks'], 'perms': playlist['perms'], 'type': playlist['type']})
                else:
                    if share := playlist['type'] == 'share':
                        playlist = await check_playlist_perms(ctx.author.id, playlist['user'], playlist['referId'])
                        if not playlist:
                            await update_playlist(ctx.author.id, {f"playlist.{data}": 1}, mode=False)
                            continue
                        if playlist['type'] == 'link':
                            tracks = await search_playlist(playlist['uri'], requester=ctx.author)
                            results.append({'emoji': ('🔒' if max_p < index else '🤝'), 'id': data, 'time': tracks['time'], 'name': user[data]['name'], 'tracks': tracks['tracks'], 'perms': playlist['perms'], 'owner': user[data]['user'], 'type': 'share'})
                            continue
                    init = []
                    for track in playlist['tracks']:
                        dt = voicelink.decode(track)
                        time += dt.get("length", 0)
                        init.append(dt)
                    playlist['tracks'] = init
                    results.append({'emoji': ('🔒' if max_p < index else ('🤝' if share else '❤️')), 'id': data, 'time': ctime(time), 'name': user[data]['name'], 'tracks': playlist['tracks'], 'perms': playlist['perms'], 'owner': user[data].get('user', None), 'type': user[data]['type']})
            
            except Exception as e:
                results.append({'emoji': '⛔', 'id': data, 'time': '00:00', 'name': 'Error', 'tracks': [], 'type': 'error'})

        embed = discord.Embed(title=get_lang(ctx.guild.id, 'playlistViewTitle').format(ctx.author.name),
                              description='```%0s %4s %10s %10s %10s\n' % tuple(get_lang(ctx.guild.id, 'playlistViewHeaders')) + '\n'.join('%0s %3s. %10s %10s %10s' % (info['emoji'], info['id'], f"[{info['time']}]", info['name'], len(info['tracks'])) for info in results) + '```',
                              color=settings.embed_color)
        
        embed.add_field(name=get_lang(ctx.guild.id, 'playlistMaxP'), value=f"➥ {len(user)}/{max_p}", inline=True)
        embed.add_field(name=get_lang(ctx.guild.id, 'playlistMaxT'), value=f"➥ {max_t}", inline=True)
        embed.set_footer(text=get_lang(ctx.guild.id, 'playlistFooter'))

        view = PlaylistView(embed, results, ctx.author)
        messsage = await ctx.send(embed=embed, view=view, ephemeral=True)
        view.response = messsage 

    @playlist.command(name="create", aliases=get_aliases("create"))
    @app_commands.describe(
        name="Give a name to your playlist.",
        link="Provide a playlist link if you are creating link playlist."
    )
    @commands.dynamic_cooldown(cooldown_check, commands.BucketType.guild)
    async def create(self, ctx: commands.Context, name: str, link: str = None):
        "Create your custom playlist."
        if len(name) > 10:
            return await ctx.send(get_lang(ctx.guild.id, 'playlistOverText'), ephemeral=True)
        
        rank, max_p, max_t = await checkroles(ctx.author.id)
        user = await check_playlist(ctx, full=True)
        if not user:
            return await create_account(ctx)

        if len(user) >= max_p:
            return await ctx.send(get_lang(ctx.guild.id, 'overPlaylistCreation').format(max_p), ephemeral=True)
        
        for data in user:
            if user[data]['name'].lower() == name.lower():
                return await ctx.send(get_lang(ctx.guild.id, 'playlistExists').format(name), ephemeral=True)
        if link:
            tracks = await voicelink.NodePool.get_node().get_tracks(link, requester=ctx.author)
            if not isinstance(tracks, voicelink.Playlist):
                return await ctx.send(get_lang(ctx.guild.id, 'playlistNotInvaildUrl'), ephemeral=True)

        playlist_name.pop(str(ctx.author.id), None)
        data = {'uri': link, 'perms': {'read': []}, 'name': name, 'type': 'link'} if link else {'tracks': [], 'perms': {'read': [], 'write': [], 'remove': []}, 'name': name, 'type': 'playlist'}
        await update_playlist(ctx.author.id, {f"playlist.{assign_playlistId([data for data in user])}": data})
        await ctx.send(get_lang(ctx.guild.id, 'playlistCreated').format(name))

    @playlist.command(name="delete", aliases=get_aliases("delete"))
    @app_commands.describe(name="The name of the playlist.")
    @app_commands.autocomplete(name=playlist_autocomplete)
    @commands.dynamic_cooldown(cooldown_check, commands.BucketType.guild)
    async def delete(self, ctx: commands.Context, name: str):
        "Delete your custom playlist."
        result = await check_playlist(ctx, name.lower(), share=False)
        if not result:
            return await create_account(ctx)
        if not result['playlist']:
            return await ctx.send(get_lang(ctx.guild.id, 'playlistNotFound').format(name), ephemeral=True)
        if result['id'] == "200":
            return await ctx.send(get_lang(ctx.guild.id, 'playlistDeleteError'), ephemeral=True)

        if result['playlist']['type'] == 'share':
            await update_playlist(result['playlist']['user'], {f"playlist.{result['playlist']['referId']}.perms.read": ctx.author.id}, pull=True, mode=False)

        playlist_name.pop(str(ctx.author.id), None)
        await update_playlist(ctx.author.id, {f"playlist.{result['id']}": 1}, mode=False)
        return await ctx.send(get_lang(ctx.guild.id, 'playlistRemove').format(result['playlist']['name']))

    @playlist.command(name="share", aliases=get_aliases("share"))
    @app_commands.describe(
        member="The user id of your friend.",
        name="The name of the playlist that you want to share."
    )
    @app_commands.autocomplete(name=playlist_autocomplete)
    @commands.dynamic_cooldown(cooldown_check, commands.BucketType.guild)
    async def share(self, ctx: commands.Context, member: discord.Member, name: str):
        "Share your custom playlist with your friends."
        if member.id == ctx.author.id:
            return await ctx.send(get_lang(ctx.guild.id, 'playlistSendErrorPlayer'), ephemeral=True)
        if member.bot:
            return await ctx.send(get_lang(ctx.guild.id, 'playlistSendErrorBot'), ephemeral=True)
        result = await check_playlist(ctx, name.lower(), share=False)
        if not result:
            return await create_account(ctx)
        if not result['playlist']:
            return await ctx.send(get_lang(ctx.guild.id, 'playlistNotFound').format(name), ephemeral=True)

        if result['playlist']['type'] == 'share':
            return await ctx.send(get_lang(ctx.guild.id, 'playlistBelongs').format(result['playlist']['user']), ephemeral=True)
        if member.id in result['playlist']['perms']['read']:
            return await ctx.send(get_lang(ctx.guild.id, 'playlistShare').format(member), ephemeral=True)

        receiver = await get_playlist(member.id)
        if not receiver:
            return await ctx.send(get_lang(ctx.guild.id, 'noPlaylistAcc').format(member))
        for mail in receiver['inbox']:
            if mail['sender'] == ctx.author.id and mail['referId'] == result['id']:
                return await ctx.send(get_lang(ctx.guild.id, 'playlistSent'), ephemeral=True)
        if len(receiver['inbox']) >= 10:
            return await ctx.send(get_lang(ctx.guild.id, 'inboxFull').format(member), ephemeral=True)

        await update_inbox(member.id, {'sender': ctx.author.id, 'referId': result['id'], 'time': datetime.now(), 'title': f'Playlist invitation from {ctx.author}', 'description': f"You are invited to use this playlist.\nPlaylist Name: {result['playlist']['name']}\nPlaylist type: {result['playlist']['type']}", 'type': 'invite'})
        return await ctx.send(get_lang(ctx.guild.id, 'invitationSent').format(member))

    @playlist.command(name="rename", aliases=get_aliases("rename"))
    @app_commands.describe(
        name="The name of your playlist.",
        newname="The new name of your playlist."
    )
    @app_commands.autocomplete(name=playlist_autocomplete)
    @commands.dynamic_cooldown(cooldown_check, commands.BucketType.guild)
    async def rename(self, ctx: commands.Context, name: str, newname: str) -> None:
        "Rename your custom playlist."
        if len(newname) > 10:
            return await ctx.send(get_lang(ctx.guild.id, 'playlistOverText'), ephemeral=True)
        if name.lower() == newname.lower():
            return await ctx.send(get_lang(ctx.guild.id, 'playlistSameName'), ephemeral=True)
        user = await check_playlist(ctx, full=True)
        if not user:
            return await create_account(ctx)
        found, id = False, 0
        for data in user:
            if user[data]['name'].lower() == name.lower():
                found, id = True, data
            if user[data]['name'].lower() == newname.lower():
                return await ctx.send(get_lang(ctx.guild.id, 'playlistExists'), ephemeral=True)

        if not found:
            return await ctx.send(get_lang(ctx.guild.id, 'playlistNotFound').format(name), ephemeral=True)

        playlist_name.pop(str(ctx.author.id), None)
        await update_playlist(ctx.author.id, {f'playlist.{id}.name': newname})
        await ctx.send(get_lang(ctx.guild.id, 'playlistRenamed').format(name, newname))

    @playlist.command(name="inbox", aliases=get_aliases("inbox"))
    @commands.dynamic_cooldown(cooldown_check, commands.BucketType.guild)
    async def inbox(self, ctx: commands.Context) -> None:
        "Show your playlist invitation."
        user = await get_playlist(ctx.author.id)
        if user is None:
            return await create_account(ctx)
        if not user['inbox']:
            return await ctx.send(get_lang(ctx.guild.id, 'inboxNoMsg'), ephemeral=True)

        inbox = user['inbox'].copy()
        view = InboxView(ctx.author, user['inbox'])
        message = await ctx.send(embed=view.build_embed(), view=view, ephemeral=True)
        view.response = message
        await view.wait()

        if inbox == user['inbox']:
            return
        updateData, dId = {}, {dId for dId in user["playlist"]}
        for data in view.newplaylist[:(5 - len(user['playlist']))]:
            addId = assign_playlistId(dId)
            await update_playlist(data['sender'], {f"playlist.{data['referId']}.perms.read": ctx.author.id}, push=True)
            updateData[f'playlist.{addId}'] = {'user': data['sender'], 'referId': data['referId'],
                                               'name': f"Share{data['time'].strftime('%M%S')}", 'type': 'share'}
            dId.add(addId)

        playlist_name.pop(str(ctx.author.id), None)
        await update_playlist(ctx.author.id, updateData | {'inbox': view.inbox})

    @playlist.command(name="add", aliases=get_aliases("add"))
    @commands.dynamic_cooldown(cooldown_check, commands.BucketType.guild)
    @app_commands.describe(
        name="The name of the playlist.",
        query="Input a query or a searchable link."
    )
    @app_commands.autocomplete(name=playlist_autocomplete)
    async def add(self, ctx: commands.Context, name: str, query: str) -> None:
        "Add tracks in to your custom playlist."
        result = await check_playlist(ctx, name.lower(), share=False)
        if not result:
            return await create_account(ctx)
        if not result['playlist']:
            return await ctx.send(get_lang(ctx.guild.id, 'playlistNotFound').format(name), ephemeral=True)
        if result['playlist']['type'] in ['share', 'link']:
            return await ctx.send(get_lang(ctx.guild.id, 'playlistNotAllow'), ephemeral=True)
        
        rank, max_p, max_t = await checkroles(ctx.author.id)
        if len(result['playlist']['tracks']) >= max_t:
            return await ctx.send(get_lang(ctx.guild.id, 'playlistLimitTrack').format(max_t), ephemeral=True)

        results = await voicelink.NodePool.get_node().get_tracks(query, requester=ctx.author)
        if not results:
            return await ctx.send(get_lang(ctx.guild.id, 'noTrackFound'))
        
        if isinstance(results, voicelink.Playlist):
            return await ctx.send(get_lang(ctx.guild.id, 'playlistPlaylistLink'), ephemeral=True)
        
        if results[0].is_stream:
            return await ctx.send(get_lang(ctx.guild.id, 'playlistStream'), ephemeral=True)

        await update_playlist(ctx.author.id, {f'playlist.{result["id"]}.tracks': results[0].track_id}, push=True)
        await ctx.send(get_lang(ctx.guild.id, 'playlistAdded').format(results[0].title, ctx.author, result['playlist']['name']))

    @playlist.command(name="remove", aliases=get_aliases("remove"))
    @commands.dynamic_cooldown(cooldown_check, commands.BucketType.guild)
    @app_commands.describe(
        name="The name of the playlist.",
        position="Input a position from the playlist to be removed."
    )
    @app_commands.autocomplete(name=playlist_autocomplete)
    async def remove(self, ctx: commands.Context, name: str, position: int):
        "Remove song from your favorite playlist."
        result = await check_playlist(ctx, name.lower(), share=False)
        if not result:
            return await create_account(ctx)
        if not result['playlist']:
            return await ctx.send(get_lang(ctx.guild.id, 'playlistNotFound').format(name), ephemeral=True)
        if result['playlist']['type'] in ['link', 'share']:
            return await ctx.send(get_lang(ctx.guild.id, 'playlistNotAllow'), ephemeral=True)
        if not 0 < position <= len(result['playlist']['tracks']):
            return await ctx.send(get_lang(ctx.guild.id, 'playlistPositionNotFound').format(position, name))

        await update_playlist(ctx.author.id, {f'playlist.{result["id"]}.tracks': result['playlist']['tracks'][position - 1]}, pull=True, mode=False)
        
        track = voicelink.decode(result['playlist']['tracks'][position - 1])
        await ctx.send(get_lang(ctx.guild.id, 'playlistRemoved').format(track.get("title"), ctx.author, name))

    @playlist.command(name="clear", aliases=get_aliases("clear"))
    @commands.dynamic_cooldown(cooldown_check, commands.BucketType.guild)
    @app_commands.autocomplete(name=playlist_autocomplete)
    async def clear(self, ctx: commands.Context, name: str) -> None:
        "Remove all songs from your favorite playlist."
        result = await check_playlist(ctx, name.lower(), share=False)
        if not result:
            return await create_account(ctx)
        if not result['playlist']:
            return await ctx.send(get_lang(ctx.guild.id, 'playlistNotFound').format(name), ephemeral=True)

        if result['playlist']['type'] in ['link', 'share']:
            return await ctx.send(get_lang(ctx.guild.id, 'playlistNotAllow'), ephemeral=True)

        await update_playlist(ctx.author.id, {f'playlist.{result["id"]}.tracks': []})
        await ctx.send(get_lang(ctx.guild.id, 'playlistClear').format(name))

    @playlist.command(name="export", aliases=get_aliases("export"))
    @commands.dynamic_cooldown(cooldown_check, commands.BucketType.guild)
    @app_commands.autocomplete(name=playlist_autocomplete)
    async def export(self, ctx: commands.Context, name: str) -> None:
        "Exports the entire playlist to a text file"
        result = await check_playlist(ctx, name.lower())
        if not result:
            return await create_account(ctx)
        if not result['playlist']:
            return await ctx.send(get_lang(ctx.guild.id, 'playlistNotFound').format(name), ephemeral=True)
        
        if result['playlist']['type'] == 'link':
            tracks = await search_playlist(result['playlist']['uri'], ctx.author, timeNeed=False)
        else:
            if not result['playlist']['tracks']:
                return await ctx.send(get_lang(ctx.guild.id, 'playlistNoTrack').format(result['playlist']['name']), ephemeral=True)

            playtrack = []
            for track in result['playlist']['tracks']:
                playtrack.append(voicelink.Track(track_id=track, info=voicelink.decode(track), requester=ctx.author))
                    
            tracks = {"name": result['playlist']['name'], "tracks": playtrack}

        if not tracks:
            return await ctx.send(get_lang(ctx.guild.id, 'playlistNoTrack').format(result['playlist']['name']), ephemeral=True)

        temp = ""
        raw = "----------->Raw Info<-----------\n"

        total_length = 0
        for index, track in enumerate(tracks['tracks'], start=1):
            temp += f"{index}. {track.title} [{ctime(track.length)}]\n"
            raw += track.track_id
            if index != len(tracks['tracks']):
                raw += ","
            total_length += track.length

        temp = "!Remember do not change this file!\n------------->Info<-------------\nPlaylist: {} ({})\nRequester: {} ({})\nTracks: {} - {}\n------------>Tracks<------------\n".format(
            tracks['name'], result['playlist']['type'],
            ctx.author.name, ctx.author.id,
            len(tracks['tracks']), ctime(total_length)
        ) + temp
        temp += raw

        await ctx.send(content="", file=discord.File(StringIO(temp), filename=f"{tracks['name']}_playlist.txt"))

    @playlist.command(name="import", aliases=get_aliases("import"))
    @app_commands.describe(name="Give a name to your playlist.")
    @commands.dynamic_cooldown(cooldown_check, commands.BucketType.guild)
    async def _import(self, ctx: commands.Context, name: str, attachment: discord.Attachment):
        "Create your custom playlist."
        if len(name) > 10:
            return await ctx.send(get_lang(ctx.guild.id, 'playlistOverText'), ephemeral=True)
        
        rank, max_p, max_t = await checkroles(ctx.author.id)
        user = await check_playlist(ctx, full=True)
        if not user:
            return await create_account(ctx)

        if len(user) >= max_p:
            return await ctx.send(get_lang(ctx.guild.id, 'overPlaylistCreation').format(max_p), ephemeral=True)
        
        for data in user:
            if user[data]['name'].lower() == name.lower():
                return await ctx.send(get_lang(ctx.guild.id, 'playlistExists').format(name), ephemeral=True)

        try:
            bytes = await attachment.read()
            track_ids = bytes.split(b"\n")[-1]
            track_ids = track_ids.decode().split(",")

            playlist_name.pop(str(ctx.author.id), None)
            data = {'tracks': track_ids, 'perms': {'read': [], 'write': [], 'remove': []}, 'name': name, 'type': 'playlist'}
            await update_playlist(ctx.author.id, {f"playlist.{assign_playlistId([data for data in user])}": data})
            await ctx.send(get_lang(ctx.guild.id, 'playlistCreated').format(name))

        except:
            return await ctx.send(get_lang(ctx.guild.id, "decodeError"), ephemeral=True)

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Playlists(bot))
