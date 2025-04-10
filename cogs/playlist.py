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

import discord, voicelink, time

from io import StringIO
from discord import app_commands
from discord.ext import commands
from function import (
    send,
    time as ctime,
    get_user,
    update_user,
    check_roles,
    get_lang,
    settings,
    get_aliases,
    cooldown_check,
    logger
)

from views import PlaylistView, InboxView, HelpView

def assign_playlist_id(existed: list) -> str:
    for i in range(200, 210):
        if str(i) not in existed:
            return str(i)

async def check_playlist_perms(user_id: int, author_id: int, d_id: str) -> dict:
    playlist = await get_user(author_id, 'playlist')
    playlist = playlist.get(d_id)
    if not playlist or user_id not in playlist['perms']['read']:
        return {}
    return playlist

async def check_playlist(ctx: commands.Context, name: str = None, full: bool = False, share: bool = True) -> dict:
    user = await get_user(ctx.author.id, 'playlist')

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

async def search_playlist(url: str, requester: discord.Member, time_needed: bool = True) -> dict:
    try:
        tracks = await voicelink.NodePool.get_node().get_tracks(url, requester=requester)
        tracks = {"name": tracks.name, "tracks": tracks.tracks}
        if time_needed:
            time = sum([track.length for track in tracks["tracks"]])
    except:
        return {}
    
    if time_needed:
        tracks["time"] = ctime(time)

    return tracks

class Playlists(commands.Cog, name="playlist"):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.description = "This is the Vocard playlist system. You can save your favorites and use Vocard to play on any server."

    async def playlist_autocomplete(self, interaction: discord.Interaction, current: str) -> list:
        playlists_raw: dict[str, dict] = await get_user(interaction.user.id, 'playlist')
        playlists = [value['name'] for value in playlists_raw.values()] if playlists_raw else []
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
        view.response = send(ctx, embed, view=view)

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

        if not result['playlist']:
            return await send(ctx, 'playlistNotFound', name, ephemeral=True)
        rank, max_p, max_t = check_roles()
        if result['position'] > max_p:
            return await send(ctx, 'playlistNotAccess', ephemeral=True)

        player: voicelink.Player = ctx.guild.voice_client
        if not player:
            player = await voicelink.connect_channel(ctx)

        if result['playlist']['type'] == 'link':
            tracks = await search_playlist(result['playlist']['uri'], ctx.author, time_needed=False)
        else:
            if not result['playlist']['tracks']:
                return await send(ctx, 'playlistNoTrack', result['playlist']['name'], ephemeral=True)

            _tracks = []
            for track in result['playlist']['tracks'][:max_t]:
                _tracks.append(voicelink.Track(track_id=track, info=voicelink.decode(track), requester=ctx.author))
                    
            tracks = {"name": result['playlist']['name'], "tracks": _tracks}

        if not tracks:
            return await send(ctx, 'playlistNoTrack', result['playlist']['name'], ephemeral=True)

        if value and 0 < value <= (len(tracks['tracks'])):
            tracks['tracks'] = [tracks['tracks'][value - 1]]
        await player.add_track(tracks['tracks'])
        await send(ctx, 'playlistPlay', result['playlist']['name'], len(tracks['tracks'][:max_t]))

        if not player.is_playing:
            await player.do_next()

    @playlist.command(name="view", aliases=get_aliases("view"))
    @commands.dynamic_cooldown(cooldown_check, commands.BucketType.guild)
    async def view(self, ctx: commands.Context) -> None:
        "List all your playlist and all songs in your favourite playlist."
        user = await check_playlist(ctx, full=True)
        rank, max_p, max_t = check_roles()

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
                            await update_user(ctx.author.id, {"$unset": {f"playlist.{data}": 1}})
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
        
            except:
                results.append({'emoji': '⛔', 'id': data, 'time': '--:--', 'name': 'Error', 'tracks': [], 'type': 'error'})

        text = await get_lang(ctx.guild.id, "playlistViewTitle", "playlistViewHeaders", "playlistFooter")
        embed = discord.Embed(
            title=text[0].format(ctx.author.display_name),
            description='```prolog\n   %4s %10s %12s %10s\n' % tuple(text[1].split(",")),
            color=settings.embed_color
        )
        
        for index in range(max_p):
            try:
                info = results[index]
                track_info = (info['emoji'], info['id'], f"[{info['time']}]", info['name'], f"{len(info['tracks'])}")
            except IndexError:
                track_info = ("🎵", "-"*3, "[--:--]", "-"*6, f"-")

            embed.description += '%0s %3s. %10s %12s %10s\n' % track_info
            
        embed.description += "```"
        embed.set_footer(text=text[2])

        view = PlaylistView(embed, results, ctx.author)
        view.response = await send(ctx, embed, view=view, ephemeral=True)

    @playlist.command(name="create", aliases=get_aliases("create"))
    @app_commands.describe(
        name="Give a name to your playlist.",
        link="Provide a playlist link if you are creating link playlist."
    )
    @commands.dynamic_cooldown(cooldown_check, commands.BucketType.guild)
    async def create(self, ctx: commands.Context, name: str, link: str = None):
        "Create your custom playlist."
        if len(name) > 10:
            return await send(ctx, 'playlistOverText', ephemeral=True)
        
        rank, max_p, max_t = check_roles()
        user = await check_playlist(ctx, full=True)

        if len(user) >= max_p:
            return await send(ctx, 'overPlaylistCreation', max_p, ephemeral=True)
        
        for data in user:
            if user[data]['name'].lower() == name.lower():
                return await send(ctx, 'playlistExists', name, ephemeral=True)
        if link:
            tracks = await voicelink.NodePool.get_node().get_tracks(link, requester=ctx.author)
            if not isinstance(tracks, voicelink.Playlist):
                return await send(ctx, "playlistNotInvalidUrl", ephemeral=True)

        data = {'uri': link, 'perms': {'read': []}, 'name': name, 'type': 'link'} if link else {'tracks': [], 'perms': {'read': [], 'write': [], 'remove': []}, 'name': name, 'type': 'playlist'}
        await update_user(ctx.author.id, {"$set": {f"playlist.{assign_playlist_id([data for data in user])}": data}})
        await send(ctx, "playlistCreated", name)

    @playlist.command(name="delete", aliases=get_aliases("delete"))
    @app_commands.describe(name="The name of the playlist.")
    @app_commands.autocomplete(name=playlist_autocomplete)
    @commands.dynamic_cooldown(cooldown_check, commands.BucketType.guild)
    async def delete(self, ctx: commands.Context, name: str):
        "Delete your custom playlist."
        result = await check_playlist(ctx, name.lower(), share=False)
        if not result['playlist']:
            return await ctx(ctx, "playlistNotFound", name, ephemeral=True)
        if result['id'] == "200":
            return await send(ctx, "playlistDeleteError", ephemeral=True)

        if result['playlist']['type'] == 'share':
            await update_user(result['playlist']['user'], {"$pull": {f"playlist.{result['playlist']['referId']}.perms.read": ctx.author.id}})

        await update_user(ctx.author.id, {"$unset": {f"playlist.{result['id']}": 1}})
        return await send(ctx, "playlistRemove", result["playlist"]["name"])

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
            return await send(ctx, 'playlistSendErrorPlayer', ephemeral=True)
        if member.bot:
            return await send(ctx, 'playlistSendErrorBot', ephemeral=True)
        result = await check_playlist(ctx, name.lower(), share=False)
        if not result['playlist']:
            return await send(ctx, 'playlistNotFound', name, ephemeral=True)

        if result['playlist']['type'] == 'share':
            return await send(ctx, 'playlistBelongs', result['playlist']['user'], ephemeral=True)
        if member.id in result['playlist']['perms']['read']:
            return await send(ctx, 'playlistShare', member, ephemeral=True)

        receiver = await get_user(member.id)
        if not receiver:
            return await send(ctx, 'noPlaylistAcc', member)
        for mail in receiver['inbox']:
            if mail['sender'] == ctx.author.id and mail['referId'] == result['id']:
                return await send(ctx, 'playlistSent', ephemeral=True)
        if len(receiver['inbox']) >= 10:
            return await send(ctx.guild.id, 'inboxFull', member, ephemeral=True)

        await update_user(
            member.id, 
            {"$push": {"inbox": {
                'sender': ctx.author.id, 
                'referId': result['id'],
                'time': time.time(),
                'title': f'Playlist invitation from {ctx.author}',
                'description': f"You are invited to use this playlist.\nPlaylist Name: {result['playlist']['name']}\nPlaylist type: {result['playlist']['type']}",
                'type': 'invite'
            }}}
        )
        return await send(ctx, "invitationSent", member)

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
            return await send(ctx, 'playlistOverText', ephemeral=True)
        if name.lower() == newname.lower():
            return await send(ctx, 'playlistSameName', ephemeral=True)
        user = await check_playlist(ctx, full=True)
        found, id = False, 0
        for data in user:
            if user[data]['name'].lower() == name.lower():
                found, id = True, data
            if user[data]['name'].lower() == newname.lower():
                return await send(ctx, 'playlistExists', ephemeral=True)

        if not found:
            return await send(ctx.guild.id, 'playlistNotFound', name, ephemeral=True)

        await update_user(ctx.author.id, {"$set": {f'playlist.{id}.name': newname}})
        await send(ctx, 'playlistRenamed', name, newname)

    @playlist.command(name="inbox", aliases=get_aliases("inbox"))
    @commands.dynamic_cooldown(cooldown_check, commands.BucketType.guild)
    async def inbox(self, ctx: commands.Context) -> None:
        "Show your playlist invitation."
        user = await get_user(ctx.author.id)
        rank, max_p, max_t = check_roles()

        if not user['inbox']:
            return await send(ctx, 'inboxNoMsg', ephemeral=True)

        inbox = user['inbox'].copy()
        view = InboxView(ctx.author, user['inbox'])
        view.response = await send(ctx, view.build_embed(), view=view, ephemeral=True)
        await view.wait()

        if inbox == user['inbox']:
            return
        
        update_data, dId = {}, {dId for dId in user["playlist"]}
        for data in view.new_playlist[:(max_p - len(user['playlist']))]:
            addId = assign_playlist_id(dId)
            await update_user(data['sender'], {"$push": {f"playlist.{data['referId']}.perms.read": ctx.author.id}})
            update_data[f'playlist.{addId}'] = {
                'user': data['sender'], 'referId': data['referId'],
                'name': f"Share{time.strftime('%M%S', time.gmtime(int(data['time'])))}",
                'type': 'share'
            }
            update_data["inbox"] = view.inbox
            dId.add(addId)

        if update_data:
            await update_user(ctx.author.id, {"$set": update_data})

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
        if not result['playlist']:
            return await send(ctx, 'playlistNotFound', name, ephemeral=True)
        if result['playlist']['type'] in ['share', 'link']:
            return await send(ctx, 'playlistNotAllow', ephemeral=True)
        
        rank, max_p, max_t = check_roles()
        if len(result['playlist']['tracks']) >= max_t:
            return await send(ctx, 'playlistLimitTrack', max_t, ephemeral=True)

        results = await voicelink.NodePool.get_node().get_tracks(query, requester=ctx.author)
        if not results:
            return await send(ctx, 'noTrackFound')
        
        if isinstance(results, voicelink.Playlist):
            return await send(ctx, 'playlistPlaylistLink', ephemeral=True)
        
        if results[0].is_stream:
            return await send(ctx, 'playlistStream', ephemeral=True)

        await update_user(ctx.author.id, {"$push": {f'playlist.{result["id"]}.tracks': results[0].track_id}})
        await send(ctx, 'playlistAdded', results[0].title, ctx.author, result['playlist']['name'])

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
        if not result['playlist']:
            return await send(ctx, 'playlistNotFound', name, ephemeral=True)
        if result['playlist']['type'] in ['link', 'share']:
            return await send(ctx, 'playlistNotAllow', ephemeral=True)
        if not 0 < position <= len(result['playlist']['tracks']):
            return await send(ctx, 'playlistPositionNotFound', position, name)

        await update_user(ctx.author.id, {"$pull": {f'playlist.{result["id"]}.tracks': result['playlist']['tracks'][position - 1]}})
        
        track = voicelink.decode(result['playlist']['tracks'][position - 1])
        await send(ctx, 'playlistRemoved', track.get("title"), ctx.author, name)

    @playlist.command(name="clear", aliases=get_aliases("clear"))
    @commands.dynamic_cooldown(cooldown_check, commands.BucketType.guild)
    @app_commands.autocomplete(name=playlist_autocomplete)
    async def clear(self, ctx: commands.Context, name: str) -> None:
        "Remove all songs from your favorite playlist."
        result = await check_playlist(ctx, name.lower(), share=False)
        if not result['playlist']:
            return await send(ctx, 'playlistNotFound', name, ephemeral=True)

        if result['playlist']['type'] in ['link', 'share']:
            return await send(ctx, 'playlistNotAllow', ephemeral=True)

        await update_user(ctx.author.id, {"$set": {f'playlist.{result["id"]}.tracks': []}})
        await send(ctx, 'playlistClear', name)

    @playlist.command(name="export", aliases=get_aliases("export"))
    @commands.dynamic_cooldown(cooldown_check, commands.BucketType.guild)
    @app_commands.autocomplete(name=playlist_autocomplete)
    async def export(self, ctx: commands.Context, name: str) -> None:
        "Exports the entire playlist to a text file"
        result = await check_playlist(ctx, name.lower())
        if not result['playlist']:
            return await send(ctx, 'playlistNotFound', name, ephemeral=True)
        
        if result['playlist']['type'] == 'link':
            tracks = await search_playlist(result['playlist']['uri'], ctx.author, time_needed=False)
        else:
            if not result['playlist']['tracks']:
                return await send(ctx, 'playlistNoTrack', result['playlist']['name'], ephemeral=True)

            _tracks = []
            for track in result['playlist']['tracks']:
                _tracks.append(voicelink.Track(track_id=track, info=voicelink.decode(track), requester=ctx.author))
                    
            tracks = {"name": result['playlist']['name'], "tracks": _tracks}

        if not tracks:
            return await send(ctx, 'playlistNoTrack', result['playlist']['name'], ephemeral=True)

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
            ctx.author.display_name, ctx.author.id,
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
            return await send(ctx, 'playlistOverText', ephemeral=True)
        
        rank, max_p, max_t = check_roles()
        user = await check_playlist(ctx, full=True)

        if len(user) >= max_p:
            return await send(ctx, 'overPlaylistCreation', max_p, ephemeral=True)
        
        for data in user:
            if user[data]['name'].lower() == name.lower():
                return await send(ctx, 'playlistExists', name, ephemeral=True)

        try:
            bytes = await attachment.read()
            track_ids = bytes.split(b"\n")[-1]
            track_ids = track_ids.decode().split(",")

            data = {'tracks': track_ids, 'perms': {'read': [], 'write': [], 'remove': []}, 'name': name, 'type': 'playlist'}
            await update_user(ctx.author.id, {"$set": {f"playlist.{assign_playlist_id([data for data in user])}": data}})
            await send(ctx, 'playlistCreated', name)

        except Exception as e:
            logger.error("Decode Error", exc_info=e)
            raise e

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Playlists(bot))