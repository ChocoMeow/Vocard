import discord
import voicelink
import re

from discord import app_commands
from discord.ext import commands
from tldextract import extract
from function import (
    time as ctime,
    get_playlist,
    create_account,
    checkroles,
    update_playlist,
    update_inbox,
    get_lang,
    playlist_name,
    embed_color
)

from datetime import datetime
from view import PlaylistView, InboxView

def assign_playlistId(existed:list) -> str:
    for i in range(200, 210):
        if str(i) not in existed:
            return str(i)

async def check_playlist_perms(userid:int, authorid:int, dId:str) -> dict:
    playlist = await get_playlist(authorid, 'playlist', dId)
    if not playlist or userid not in playlist['perms']['read']:
        return {}
    return playlist

async def check_playlist(interaction: discord.Interaction, name:str = None, full:bool = False, share:bool = True) -> dict:
    user = await get_playlist(interaction.user.id, 'playlist')
    if not user:
        return None
    await interaction.response.defer()
    if full:
        return user
    if not name:
        return {'playlist': user['200'], 'position': 1, 'id': "200"}
        
    for index, data in enumerate(user, start=1):
        playlist = user[data]
        if playlist['name'].lower() == name:
            if playlist['type'] == 'share' and share:
                playlist = await check_playlist_perms(interaction.user.id, playlist['user'], playlist['referId'])
                if not playlist or interaction.user.id not in playlist['perms']['read']:
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

class Playlist(commands.GroupCog, name="playlist"):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.description = "This is the Vocard playlist system. You can save your favorites and use Vocard to play on any server."
    
    async def playlist_autocomplete(self, interaction: discord.Interaction, current: str) -> list:
        playlists = playlist_name.get(str(interaction.user.id), None)
        if not playlists:
            playlists_raw = await get_playlist(interaction.user.id, 'playlist')
            playlists = playlist_name[str(interaction.user.id)] = [value['name'] for value in playlists_raw.values()] if playlists_raw else []
        if current:
            return [ app_commands.Choice(name=p, value=p) for p in playlists if current in p ]
        return [ app_commands.Choice(name=p, value=p) for p in playlists ]

    @app_commands.command(
        name = "play",
        description = "Play all songs from your favorite playlist."
    )
    @app_commands.describe(
        name = "Input the name of your custom playlist",
        value = "Play the specific track from your custom playlist."
    )
    @app_commands.autocomplete(name=playlist_autocomplete)
    @app_commands.guild_only()
    async def play(self, interaction: discord.Interaction, name: str = None, value: int = None) -> None:
        result = await check_playlist(interaction, name.lower() if name else None)
        if not result:
            return await create_account(interaction)
        if not result['playlist']:
            return await interaction.followup.send(get_lang(interaction.guild_id, 'playlistNotFound').format(name), ephemeral=True)
        rank, max_p, max_t = await checkroles(interaction.user.id)
        if result['position'] > max_p:
            return await interaction.followup.send(get_lang(interaction.guild_id, 'playlistNotAccess'), ephemeral=True)

        player: voicelink.Player = interaction.guild.voice_client
        if not player:
            player = await connect_channel(interaction)

        if result['playlist']['type'] == 'link':
            tracks = await search_playlist(result['playlist']['uri'], interaction.user, timeNeed=False)
        else:
            if not result['playlist']['tracks']:
                return await interaction.followup.send(get_lang(interaction.guild_id, 'playlistNoTrack').format(result['playlist']['name']), ephemeral=True)

            playtrack = []
            for track in result['playlist']['tracks'][:max_t]:
                track['info']['length'] *= 1000
                playtrack.append(voicelink.Track(track_id=track['id'], info=track['info'], requester=interaction.user, spotify= True if extract(track['info']['uri']).domain == 'spotify' else False))
            tracks = {"name": result['playlist']['name'], "tracks": playtrack}
        
        if not tracks:
            return await interaction.followup.send(get_lang(interaction.guild_id, 'playlistNoTrack').format(result['playlist']['name']), ephemeral=True)
        
        if value and 0 < value <= (len(tracks['tracks'])):
            tracks['tracks'] = [tracks['tracks'][value - 1]]
        for track in tracks['tracks']:
            await player.queue.put(track)
        
        await interaction.followup.send(get_lang(interaction.guild_id, 'playlistPlay').format(result['playlist']['name'], len(tracks['tracks'][:max_t])))
        
        if not player.is_playing:
            await player.do_next()

    @app_commands.command(
        name = "view",
        description = "List all your playlist and all songs in your favourite playlist."
    )
    @app_commands.guild_only()
    async def view(self, interaction: discord.Interaction) -> None:
        user = await check_playlist(interaction, full=True)
        if not user:
            return await create_account(interaction)
        rank, max_p, max_t = await checkroles(interaction.user.id)

        results = []
        for index, data in enumerate(user, start=1):
            playlist = user[data]
            time = 0
            try:
                if playlist['type'] == 'link':
                    tracks = await search_playlist(playlist['uri'], requester=interaction.user)
                    results.append({'emoji':('🔒' if max_p < index else '🔗'), 'id': data, 'time': tracks['time'], 'name':playlist['name'], 'tracks': tracks['tracks'], 'perms': playlist['perms'], 'type': playlist['type']})
                else:
                    if share := playlist['type'] == 'share':
                        playlist = await check_playlist_perms(interaction.user.id, playlist['user'], playlist['referId'])
                        if not playlist:
                            await update_playlist(interaction.user.id, {f"playlist.{data}":1}, mode=False)
                            continue
                        if playlist['type'] == 'link':
                            tracks = await search_playlist(playlist['uri'], requester=interaction.user)
                            results.append({'emoji':('🔒' if max_p < index else '🤝'), 'id': data, 'time': tracks['time'], 'name':user[data]['name'], 'tracks': tracks['tracks'], 'perms': playlist['perms'], 'owner': user[data]['user'], 'type': 'share'})
                            continue
                    for track in playlist['tracks']:
                        time += track['info']['length'] * 1000
                    results.append({'emoji':('🔒' if max_p < index else ('🤝' if share else '❤️')), 'id': data, 'time': ctime(time), 'name':user[data]['name'], 'tracks': playlist['tracks'], 'perms': playlist['perms'], 'owner': user[data].get('user', None), 'type': user[data]['type']})
            except:
                results.append({'emoji': '⛔', 'id': data, 'time': '00:00', 'name': 'Error', 'tracks': [], 'type': 'error'})

        embed=discord.Embed(title=get_lang(interaction.guild_id, 'playlistViewTitle').format(interaction.user.name),
                    description='```%0s %4s %10s %10s %10s\n' % tuple(get_lang(interaction.guild_id, 'playlistViewHeaders')) + '\n'.join('%0s %3s. %10s %10s %10s'% (info['emoji'], info['id'], f"[{info['time']}]", info['name'], len(info['tracks'])) for info in results) + '```',
                    color=embed_color)
        embed.add_field(name=get_lang(interaction.guild_id, 'playlistMaxP'), value=f"➥ {len(user)}/{max_p}", inline=True)
        embed.add_field(name=get_lang(interaction.guild_id, 'playlistMaxT'), value=f"➥ {max_t}", inline=True)
        embed.set_footer(text=get_lang(interaction.guild_id, 'playlistFooter'))
        
        view = PlaylistView(embed, results, interaction.user)
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)
        view.response = await interaction.original_response()

    @app_commands.command(
        name = "create",
        description = "Create your custom playlist."
    )
    @app_commands.describe(
        name = "Give a name to your playlist.",
        link = "Provide a playlist link if you are creating link playlist."
    )
    @app_commands.guild_only()
    async def create(self, interaction: discord.Interaction, name: str, link: str = None):
        if len(name) > 10:
            return await interaction.response.send_message(get_lang(interaction.guild_id, 'playlistOverText'), ephemeral=True)
        isLinkType = True if link else False
        rank, max_p, max_t = await checkroles(interaction.user.id)
        if isLinkType and rank != "Gold":
            return await interaction.response.send_message(get_lang(interaction.guild_id, 'playlistCreateError'), ephemeral=True)
        user = await check_playlist(interaction, full=True)
        if not user:
            return await create_account(interaction)

        if len(user) >= max_p:
            return await interaction.followup.send(get_lang(interaction.guild_id, 'overPlaylistCreation').format(max_p), ephemeral=True)
        for data in user:
            if user[data]['name'].lower() == name.lower():
                return await interaction.followup.send(get_lang(interaction.guild_id, 'playlistExists'), ephemeral=True)
        if isLinkType:
            tracks = await voicelink.NodePool.get_node().get_tracks(link, requester=interaction.user)
            if not isinstance(tracks, voicelink.Playlist):
                return await interaction.followup.send(get_lang(interaction.guild_id, 'playlistNotInvaildUrl'), ephemeral=True)
        
        playlist_name.pop(str(interaction.user.id), None)
        data = {'uri': link, 'perms': {'read': []}, 'name': name, 'type': 'link'} if isLinkType else {'tracks': [], 'perms': {'read': [], 'write': [], 'remove': []}, 'name': name, 'type': 'playlist'}
        await update_playlist(interaction.user.id, { f"playlist.{assign_playlistId([data for data in user])}": data })
        await interaction.followup.send(get_lang(interaction.guild_id, 'playlistCreated'))
    
    @app_commands.command(
        name = "delete",
        description = "Delete your custom playlist."
    )
    @app_commands.describe(
        name = "The name of the playlist."
    )
    @app_commands.guild_only()
    @app_commands.autocomplete(name=playlist_autocomplete)
    async def delete(self, interaction: discord.Interaction, name: str):
        result = await check_playlist(interaction, name.lower(), share=False)
        if not result:
            return await create_account(interaction)
        if not result['playlist']:
            return await interaction.followup.send(get_lang(interaction.guild_id, 'playlistNotFound').format(name), ephemeral=True)
        if result['id'] == "200":
            return await interaction.followup.send(get_lang(interaction.guild_id, 'playlistDeleteError'), ephemeral=True)

        if result['playlist']['type'] == 'share':
            await update_playlist(result['playlist']['user'], {f"playlist.{result['playlist']['referId']}.perms.read":interaction.user.id}, pull=True, mode=False)
        
        playlist_name.pop(str(interaction.user.id), None)
        await update_playlist(interaction.user.id, {f"playlist.{result['id']}":1}, mode=False)
        return await interaction.followup.send(get_lang(interaction.guild_id, 'playlistRemove').format(result['playlist']['name']))

    @app_commands.command(
        name = "share",
        description = "Share your custom playlist with your friends."
    )
    @app_commands.describe(
        member = "The user id of your friend.",
        name = "The name of the playlist that you want to share."
    )
    @app_commands.guild_only()
    @app_commands.autocomplete(name=playlist_autocomplete)
    async def share(self, interaction: discord.Interaction, member: discord.Member, name: str):
        if member.id == interaction.user.id:
            return await interaction.response.send_message(get_lang(interaction.guild_id, 'playlistSendErrorPlayer'), ephemeral=True)
        if member.bot:
            return await interaction.response.send_message(get_lang(interaction.guild_id, 'playlistSendErrorBot'), ephemeral=True)
        result = await check_playlist(interaction, name.lower(), share=False)
        if not result:
            return await create_account(interaction)
        if not result['playlist']:
            return await interaction.followup.send(get_lang(interaction.guild_id, 'playlistNotFound').format(name), ephemeral=True)
 
        if result['playlist']['type'] == 'share':
            return await interaction.followup.send(get_lang(interaction.guild_id, 'playlistBelongs').format(result['playlist']['user']), ephemeral=True)
        if member.id in result['playlist']['perms']['read']:
            return await interaction.followup.send(get_lang(interaction.guild_id, 'playlistShare').format(member), ephemeral=True)

        receiver = await get_playlist(member.id)
        if not receiver:
            return await interaction.followup.send(get_lang(interaction.guild_id, 'noPlaylistAcc').format(member))
        for mail in receiver['inbox']:
            if mail['sender'] == interaction.user.id and mail['referId'] == result['id']:
                return await interaction.followup.send(get_lang(interaction.guild_id, 'playlistSent'), ephemeral=True)
        if len(receiver['inbox']) >= 10:
            return await interaction.followup.send(get_lang(interaction.guild_id, 'inboxFull').format(member), ephemeral=True)

        await update_inbox(member.id, {'sender': interaction.user.id, 'referId': result['id'], 'time': datetime.now(),'title': f'Playlist invitation from {interaction.user}', 'description': f"You are invited to use this playlist.\nPlaylist Name: {result['playlist']['name']}\nPlaylist type: {result['playlist']['type']}", 'type': 'invite'})
        return await interaction.followup.send(get_lang(interaction.guild_id, 'invitationSent').format(member))

    @app_commands.command(
        name = "rename",
        description = "Rename your custom playlist."
    )
    @app_commands.describe(
        name = "The name of your playlist.",
        newname = "The new name of your playlist."
    )
    @app_commands.guild_only()
    @app_commands.autocomplete(name=playlist_autocomplete)
    async def rename(self, interaction: discord.Interaction, name: str, newname: str) -> None:
        if len(newname) > 10:
            return await interaction.response.send_message(get_lang(interaction.guild_id, 'playlistOverText'), ephemeral=True)
        if name.lower() == newname.lower():
            return await interaction.response.send_message(get_lang(interaction.guild_id, 'playlistSameName'), ephemeral=True)
        user = await check_playlist(interaction, full=True)
        if not user:
            return await create_account(interaction)
        found, id = False, 0
        for data in user:
            if user[data]['name'].lower() == name.lower():
                found, id = True, data
            if user[data]['name'].lower() == newname.lower():
                return await interaction.followup.send(get_lang(interaction.guild_id, 'playlistExists'), ephemeral=True)

        if not found:
            return await interaction.followup.send(get_lang(interaction.guild_id, 'playlistNotFound').format(name), ephemeral=True)
        
        playlist_name.pop(str(interaction.user.id), None)
        await update_playlist(interaction.user.id, {f'playlist.{id}.name': newname})
        await interaction.followup.send(get_lang(interaction.guild_id, 'playlistRenamed').format(name, newname))

    @app_commands.command(
        name = "inbox",
        description = "Show your playlist invitation."
    )
    @app_commands.guild_only()
    async def inbox(self, interaction: discord.Interaction) -> None:
        user = await get_playlist(interaction.user.id)
        if user is None:
            return await create_account(interaction)
        if not user['inbox']:
            return await interaction.response.send_message(get_lang(interaction.guild_id, 'inboxNoMsg'), ephemeral=True)
        
        inbox = user['inbox'].copy()
        view = InboxView(interaction.user.name, user['inbox'])
        await interaction.response.send_message(embed=view.build_embed(), view=view, ephemeral=True)
        view.response = await interaction.original_response()
        await view.wait()

        if inbox == user['inbox']:
            return 
        updateData, dId = {}, {dId for dId in user["playlist"]}
        for data in view.newplaylist[:(5 - len(user['playlist']))]:
            addId = assign_playlistId(dId)
            await update_playlist(data['sender'], {f"playlist.{data['referId']}.perms.read": interaction.user.id}, push=True)
            updateData[f'playlist.{addId}'] = {'user':data['sender'], 'referId': data['referId'], 'name': f"Share{data['time'].strftime('%M%S')}", 'type': 'share'}
            dId.add(addId)

        playlist_name.pop(str(interaction.user.id), None)
        await update_playlist(interaction.user.id, updateData | {'inbox':view.inbox})

    @app_commands.command(
        name = "add",
        description = "Add tracks in to your custom playlist."
    )
    @app_commands.describe(
        name = "The name of the playlist.",
        query = "Input a query or a searchable link."
    )
    @app_commands.guild_only()
    @app_commands.autocomplete(name=playlist_autocomplete)
    async def add(self, interaction: discord.Interaction, name: str, query: str) -> None:
        result = await check_playlist(interaction, name.lower(), share=False)
        if not result:
            return await create_account(interaction)
        if not result['playlist']:
            return await interaction.followup.send(get_lang(interaction.guild_id, 'playlistNotFound').format(name), ephemeral=True)
        if result['playlist']['type'] in ['share', 'link']:
            return await interaction.followup.send(get_lang(interaction.guild_id, 'playlistNotAllow'), ephemeral=True)
        rank, max_p, max_t = await checkroles(interaction.user.id)

        if len(result['playlist']['tracks']) >= max_t:
            return await interaction.followup.send(get_lang(interaction.guild_id, 'playlistLimitTrack').format(max_t), ephemeral=True)

        results = await voicelink.NodePool.get_node().get_tracks(query, requester = interaction.user)
        if not results:
            return await interaction.followup.send(get_lang(interaction.guild_id, 'noTrackFound'))
        if isinstance(results, voicelink.Playlist):
            return await interaction.followup.send(get_lang(interaction.guild_id, 'playlistPlaylistLink'), ephemeral=True)
        if results[0].is_stream:
            return await interaction.followup.send(get_lang(interaction.guild_id, 'playlistStream'), ephemeral=True)

        await update_playlist(interaction.user.id, {f'playlist.{result["id"]}.tracks':{'id': results[0].track_id, 'info': {'identifier': results[0].identifier,
                                                                                                                        'author': results[0].author,
                                                                                                                        'length': results[0].length / 1000,
                                                                                                                        'title': results[0].title,
                                                                                                                        'uri': results[0].uri}}}, push=True)
        await interaction.followup.send(get_lang(interaction.guild_id, 'playlistAdded').format(results[0].title, interaction.user, result['playlist']['name']))
    
    @app_commands.command(
        name = "remove",
        description = "Remove song from your favorite playlist."
    )
    @app_commands.describe(
        name = "The name of the playlist.",
        position = "Input a position from the playlist to be removed."
    )
    @app_commands.guild_only()
    @app_commands.autocomplete(name=playlist_autocomplete)
    async def remove(self, interaction: discord.Interaction, name: str, position: int):
        result = await check_playlist(interaction, name.lower(), share=False)
        if not result:
            return await create_account(interaction)
        if not result['playlist']:
            return await interaction.followup.send(get_lang(interaction.guild_id, 'playlistNotFound').format(name), ephemeral=True)
        if result['playlist']['type'] in ['link', 'share']:
            return await interaction.followup.send(get_lang(interaction.guild_id, 'playlistNotAllow'), ephemeral=True)
        if not 0 < position <= len(result['playlist']['tracks']):
            return await interaction.followup.send(get_lang(interaction.guild_id, 'playlistPositionNotFound').format(position, name))
            
        await update_playlist(interaction.user.id, {f'playlist.{result["id"]}.tracks': result['playlist']['tracks'][position - 1]}, pull=True, mode=False)
        await interaction.followup.send(get_lang(interaction.guild_id, 'playlistRemoved').format(result['playlist']['tracks'][position - 1]['info']['title'], interaction.user, name))
    
    @app_commands.command(
        name = "clear",
        description = "Remove all songs from your favorite playlist."
    )
    @app_commands.guild_only()
    @app_commands.autocomplete(name=playlist_autocomplete)
    async def clear(self, interaction: discord.Interaction, name: str) -> None:
        result = await check_playlist(interaction, name.lower(), share=False)
        if not result:
            return await create_account(interaction)
        if not result['playlist']:
            return await interaction.followup.send(get_lang(interaction.guild_id, 'playlistNotFound').format(name), ephemeral=True)
        
        if result['playlist']['type'] in ['link', 'share']:
            return await interaction.followup.send(get_lang(interaction.guild_id, 'playlistNotAllow'), ephemeral=True)
        
        await update_playlist(interaction.user.id, {f'playlist.{result["id"]}.tracks': []})
        await interaction.followup.send(get_lang(interaction.guild_id, 'playlistClear').format(name))

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Playlist(bot))