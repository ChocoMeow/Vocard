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

import time
import discord
import voicelink

from io import StringIO
from typing import Optional, Tuple
from discord import app_commands
from discord.ext import commands
from function import (
    get_aliases,
    cooldown_check,
    logger
)

from voicelink import MongoDBHandler, Config
from voicelink.views import PlaylistViewManager, InboxView, HelpView
from voicelink.utils import format_ms, dispatch_message, send_localized_message

def assign_playlist_id(existed: list) -> str:
    for i in range(200, 210):
        if str(i) not in existed:
            return str(i)

def resolve_owner_display(ctx: commands.Context[commands.Bot], owner_id: int):
    if owner_id == ctx.author.id:
        return ctx.author
    if ctx.guild:
        member = ctx.guild.get_member(owner_id)
        if member:
            return member
    user = ctx.bot.get_user(owner_id)
    return user if user else f"<@{owner_id}>"

async def check_playlist_perms(
    user_id: int,
    author_id: int,
    playlist_id: str,
    *,
    required_perm: Optional[str] = "read"
) -> Tuple[Optional[dict], Optional[str]]:
    """Check if user has the requested permissions for a specific playlist."""
    user_data = await MongoDBHandler.get_user(author_id, d_type='playlist')
    playlist = user_data.get(playlist_id)
    
    if not playlist:
        return None, "not_found"
    
    perms = playlist.get('perms', {})
    if user_id not in perms.get('read', []):
        return None, "no_read"
    
    if required_perm and required_perm != "read":
        if user_id not in perms.get(required_perm, []):
            return None, "no_permission"
    
    return playlist, None

async def check_playlist(
    ctx: commands.Context,
    name: str = None,
    full: bool = False,
    share: bool = True,
    share_perm: Optional[str] = None
) -> dict:
    """Get user's playlist data with various filtering options."""
    user_playlists = await MongoDBHandler.get_user(ctx.author.id, d_type='playlist')

    if isinstance(ctx, discord.Interaction) and not ctx.interaction.response.is_done():
        await ctx.defer()
    
    if full:
        return user_playlists
    
    if not name:
        return {
            'playlist': user_playlists['200'],
            'position': 1,
            'id': "200",
            'is_shared': False,
            'owner_id': ctx.author.id,
            'owner_playlist_id': "200",
            'error': None
        }
    
    for index, playlist_id in enumerate(user_playlists, start=1):
        playlist = user_playlists[playlist_id]
        
        if playlist['name'].lower() == name.lower():
            if playlist['type'] == 'share' and share:
                shared_playlist, error = await check_playlist_perms(
                    ctx.author.id,
                    playlist['user'],
                    playlist['referId'],
                    required_perm=share_perm or "read"
                )
                
                if not shared_playlist:
                    if error == "not_found":
                        await MongoDBHandler.update_user(ctx.author.id, {"$unset": {f"playlist.{playlist_id}": 1}})
                    return {
                        'playlist': None,
                        'position': index,
                        'id': playlist_id,
                        'is_shared': True,
                        'owner_id': playlist['user'],
                        'owner_playlist_id': playlist['referId'],
                        'error': 'permission' if error in {'no_read', 'no_permission'} else None
                    }
                
                return {
                    'playlist': shared_playlist,
                    'position': index,
                    'id': playlist_id,
                    'is_shared': True,
                    'owner_id': playlist['user'],
                    'owner_playlist_id': playlist['referId'],
                    'error': None
                }
            
            return {
                'playlist': playlist,
                'position': index,
                'id': playlist_id,
                'is_shared': False,
                'owner_id': ctx.author.id,
                'owner_playlist_id': playlist_id,
                'error': None
            }
    
    return {
        'playlist': None,
        'position': None,
        'id': None,
        'is_shared': False,
        'owner_id': ctx.author.id,
        'owner_playlist_id': None,
        'error': None
    }

async def search_playlist(url: str, requester: discord.Member, time_needed: bool = True) -> dict:
    """Search for playlist tracks from a URL."""
    try:
        tracks = await voicelink.NodePool.get_node().get_tracks(url, requester=requester)
        result = {"name": tracks.name, "tracks": tracks.tracks}
        
        if time_needed:
            result["time"] = format_ms(sum(track.length for track in tracks.tracks))
        
        return result
    except Exception:
        return {}

async def _process_playlist(ctx: commands.Context, playlist_data: dict, playlist_id: str, is_locked: bool):
    """Process a single playlist and return its formatted data."""
    playlist_type = playlist_data['type']
    
    # Get appropriate emoji
    if is_locked:
        emoji = '🔒'
    elif playlist_type == 'link':
        emoji = '🌐'
    elif playlist_type == 'share':
        emoji = '🤝'
    else:
        emoji = '❤️'
    
    # Handle link playlist
    if playlist_type == 'link':
        tracks = await search_playlist(playlist_data['uri'], requester=ctx.author)
        if not tracks:
            return None
        
        return {
            'emoji': emoji,
            'id': playlist_id,
            'time': tracks['time'],
            'name': playlist_data['name'],
            'tracks': tracks['tracks'],
            'perms': playlist_data['perms'],
            'type': playlist_data['type']
        }
    
    # Handle shared playlist
    if playlist_type == 'share':
        shared_playlist, error = await check_playlist_perms(
            ctx.author.id, 
            playlist_data['user'], 
            playlist_data['referId']
        )
        
        if not shared_playlist:
            if error == "not_found":
                await MongoDBHandler.update_user(ctx.author.id, {"$unset": {f"playlist.{playlist_id}": 1}})
            return None
        
        if shared_playlist['type'] == 'link':
            tracks = await search_playlist(shared_playlist['uri'], requester=ctx.author)
            if not tracks:
                return None
            
            return {
                'emoji': emoji,
                'id': playlist_id,
                'time': tracks['time'],
                'name': playlist_data['name'],
                'tracks': tracks['tracks'],
                'perms': shared_playlist['perms'],
                'owner': playlist_data['user'],
                'type': 'share'
            }
        
        decoded_tracks = []
        total_time = 0
        for track in shared_playlist['tracks']:
            decoded_track = voicelink.Track.decode(track)
            total_time += decoded_track.get("length", 0)
            decoded_tracks.append(decoded_track)
        
        return {
            'emoji': emoji,
            'id': playlist_id,
            'time': format_ms(total_time),
            'name': playlist_data['name'],
            'tracks': decoded_tracks,
            'perms': shared_playlist['perms'],
            'owner': playlist_data['user'],
            'type': 'share'
        }
    
    decoded_tracks = []
    total_time = 0
    for track in playlist_data['tracks']:
        decoded_track = voicelink.Track.decode(track)
        total_time += decoded_track.get("length", 0)
        decoded_tracks.append(decoded_track)
    
    return {
        'emoji': emoji,
        'id': playlist_id,
        'time': format_ms(total_time),
        'name': playlist_data['name'],
        'tracks': decoded_tracks,
        'perms': playlist_data['perms'],
        'owner': playlist_data.get('owner', ctx.author.id),
        'type': playlist_data['type']
    }

class Playlists(commands.Cog, name="playlist"):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.description = "This is the Vocard playlist system. You can save your favorites and use Vocard to play on any server."

    async def playlist_autocomplete(self, interaction: discord.Interaction, current: str) -> list:
        playlists_raw: dict[str, dict] = await MongoDBHandler.get_user(interaction.user.id, d_type='playlist')
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
        view.response = dispatch_message(ctx, embed, view=view)

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
            return await send_localized_message(ctx, 'playlist.errors.notFound', name, ephemeral=True)
        max_p, max_t, _ = Config().get_playlist_config()
        if result['position'] > max_p:
            return await send_localized_message(ctx, 'playlist.errors.noAccess', ephemeral=True)

        player: voicelink.Player = ctx.guild.voice_client
        if not player:
            player = await voicelink.connect_channel(ctx)

        if result['playlist']['type'] == 'link':
            tracks = await search_playlist(result['playlist']['uri'], ctx.author, time_needed=False)
        else:
            if not result['playlist']['tracks']:
                return await send_localized_message(ctx, 'playlist.errors.noTrack', result['playlist']['name'], ephemeral=True)

            _tracks = []
            for track in result['playlist']['tracks'][:max_t]:
                _tracks.append(voicelink.Track(track_id=track, info=voicelink.Track.decode(track), requester=ctx.author))
                    
            tracks = {"name": result['playlist']['name'], "tracks": _tracks}

        if not tracks:
            return await send_localized_message(ctx, 'playlist.errors.noTrack', result['playlist']['name'], ephemeral=True)

        if value and 0 < value <= (len(tracks['tracks'])):
            tracks['tracks'] = [tracks['tracks'][value - 1]]
        await player.add_track(tracks['tracks'])
        await send_localized_message(ctx, 'playlist.actions.play', result['playlist']['name'], len(tracks['tracks'][:max_t]))

        if not player.is_playing:
            await player.do_next()

    @playlist.command(name="view", aliases=get_aliases("view"))
    @commands.dynamic_cooldown(cooldown_check, commands.BucketType.guild)
    async def view(self, ctx: commands.Context) -> None:
        """List all your playlists and all songs in your favourite playlist."""
        user_playlists = await check_playlist(ctx, full=True)
        max_p, _, _ = Config().get_playlist_config()
        
        playlist_results = []
        
        for index, playlist_id in enumerate(user_playlists, start=1):
            playlist_data = user_playlists[playlist_id]
            is_locked = max_p < index
            
            try:
                result = await _process_playlist(ctx, playlist_data, playlist_id, is_locked)
                if result:
                    playlist_results.append(result)
            except Exception:
                playlist_results.append({
                    'emoji': '⛔',
                    'id': playlist_id,
                    'time': '--:--',
                    'name': 'Error',
                    'tracks': [],
                    'type': 'error'
                })
                
        view = PlaylistViewManager(ctx, playlist_results)
        view.response = await dispatch_message(ctx, content=view.build_embed(), view=view, ephemeral=True)

    @playlist.command(name="create", aliases=get_aliases("create"))
    @app_commands.describe(
        name="Give a name to your playlist.",
        link="Provide a playlist link if you are creating link playlist."
    )
    @commands.dynamic_cooldown(cooldown_check, commands.BucketType.guild)
    async def create(self, ctx: commands.Context, name: str, link: str = None):
        "Create your custom playlist."
        if len(name) > 10:
            return await send_localized_message(ctx, 'playlist.errors.nameOverLimit', ephemeral=True)
        
        max_p, _, _ = Config().get_playlist_config()
        user = await check_playlist(ctx, full=True)

        if len(user) >= max_p:
            return await send_localized_message(ctx, 'playlist.errors.limitReached', max_p, ephemeral=True)
        
        for data in user:
            if user[data]['name'].lower() == name.lower():
                return await send_localized_message(ctx, 'playlist.errors.exists', name, ephemeral=True)
        if link:
            tracks = await voicelink.NodePool.get_node().get_tracks(link, requester=ctx.author)
            if not isinstance(tracks, voicelink.Playlist):
                return await send_localized_message(ctx, "playlist.errors.invalidUrl", ephemeral=True)

        data = {'uri': link, 'perms': {'read': []}, 'name': name, 'type': 'link'} if link else {'tracks': [], 'perms': {'read': [], 'write': [], 'remove': []}, 'name': name, 'type': 'playlist'}
        await MongoDBHandler.update_user(ctx.author.id, {"$set": {f"playlist.{assign_playlist_id([data for data in user])}": data}})
        await send_localized_message(ctx, "playlist.actions.create", name)

    @playlist.command(name="delete", aliases=get_aliases("delete"))
    @app_commands.describe(name="The name of the playlist.")
    @app_commands.autocomplete(name=playlist_autocomplete)
    @commands.dynamic_cooldown(cooldown_check, commands.BucketType.guild)
    async def delete(self, ctx: commands.Context, name: str):
        "Delete your custom playlist."
        result = await check_playlist(ctx, name.lower(), share=False)
        if not result['playlist']:
            return await send_localized_message(ctx, "playlist.errors.notFound", name, ephemeral=True)
        if result['id'] == "200":
            return await send_localized_message(ctx, "playlist.errors.deleteDefault", ephemeral=True)

        if result['playlist']['type'] == 'share':
            await MongoDBHandler.update_user(result['playlist']['user'], {"$pull": {f"playlist.{result['playlist']['referId']}.perms.read": ctx.author.id}})

        await MongoDBHandler.update_user(ctx.author.id, {"$unset": {f"playlist.{result['id']}": 1}})
        return await send_localized_message(ctx, "playlist.actions.removed", result["playlist"]["name"])

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
            return await send_localized_message(ctx, 'playlist.sharing.sendErrorPlayer', ephemeral=True)
        if member.bot:
            return await send_localized_message(ctx, 'playlist.sharing.sendErrorBot', ephemeral=True)
        result = await check_playlist(ctx, name.lower(), share=False)
        if not result['playlist']:
            return await send_localized_message(ctx, 'playlist.errors.notFound', name, ephemeral=True)

        if result['playlist']['type'] == 'share':
            return await send_localized_message(ctx, 'playlist.sharing.belongs', result['playlist']['user'], ephemeral=True)
        if member.id in result['playlist']['perms']['read']:
            return await send_localized_message(ctx, 'playlist.sharing.alreadyShared', member, ephemeral=True)

        receiver = await MongoDBHandler.get_user(member.id)
        if not receiver:
            return await send_localized_message(ctx, 'playlist.sharing.noAccount', member)
        for mail in receiver['inbox']:
            if mail['sender'] == ctx.author.id and mail['referId'] == result['id']:
                return await send_localized_message(ctx, 'playlist.sharing.alreadySent', ephemeral=True)
        if len(receiver['inbox']) >= 10:
            return await send_localized_message(ctx, 'playlist.inbox.full', member, ephemeral=True)

        await MongoDBHandler.update_user(
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
        return await send_localized_message(ctx, "playlist.sharing.invitationSent", member)

    @playlist.command(name="permission", aliases=get_aliases("permission"))
    @app_commands.describe(
        name="The name of the playlist.",
        member="The user to grant or revoke permissions for.",
        permission="The permission type: read, write, or remove.",
        action="Whether to grant or revoke the permission."
    )
    @app_commands.choices(permission=[
        app_commands.Choice(name="read", value="read"),
        app_commands.Choice(name="write", value="write"),
        app_commands.Choice(name="remove", value="remove")
    ])
    @app_commands.choices(action=[
        app_commands.Choice(name="grant", value="grant"),
        app_commands.Choice(name="revoke", value="revoke")
    ])
    @app_commands.autocomplete(name=playlist_autocomplete)
    @commands.dynamic_cooldown(cooldown_check, commands.BucketType.guild)
    async def permission(self, ctx: commands.Context, member: discord.Member, name: str, permission: str, action: str):
        "Grant or revoke permissions for a playlist."
        if member.id == ctx.author.id:
            return await send_localized_message(ctx, 'playlist.permissions.cannotModifySelf', ephemeral=True)
        if member.bot:
            return await send_localized_message(ctx, 'playlist.sharing.sendErrorBot', ephemeral=True)
        
        result = await check_playlist(ctx, name.lower(), share=False)
        if not result['playlist']:
            return await send_localized_message(ctx, 'playlist.errors.notFound', name, ephemeral=True)
        
        if result['playlist']['type'] in ['share', 'link']:
            return await send_localized_message(ctx, 'playlist.errors.notAllowed', ephemeral=True)
        
        perm_type = result['playlist'].get('perms', {})
        if permission not in perm_type:
            return await send_localized_message(ctx, 'playlist.permissions.invalidPermission', ephemeral=True)
        
        perm_list = perm_type.get(permission, [])
        if action == "grant":
            if member.id in perm_list:
                return await send_localized_message(ctx, 'playlist.permissions.alreadyGranted', member, permission, ephemeral=True)
            
            # Ensure user has read access first
            if permission != 'read' and member.id not in perm_type.get('read', []):
                return await send_localized_message(ctx, f'You haven\'t shared your playlist to {member.mention}', member, ephemeral=True)
            
            await MongoDBHandler.update_user(ctx.author.id, {"$push": {f"playlist.{result['id']}.perms.{permission}": member.id}})
            return await send_localized_message(ctx, 'playlist.permissions.granted', member, permission, result['playlist']['name'])
        
        elif action == "revoke":
            if member.id not in perm_list:
                return await send_localized_message(ctx, 'playlist.permissions.notGranted', member, permission, ephemeral=True)
            
            await MongoDBHandler.update_user(ctx.author.id, {"$pull": {f"playlist.{result['id']}.perms.{permission}": member.id}})
            
            # If revoking read, also revoke write and remove
            if permission == 'read':
                await MongoDBHandler.update_user(ctx.author.id, {"$pull": {f"playlist.{result['id']}.perms.write": member.id}})
                await MongoDBHandler.update_user(ctx.author.id, {"$pull": {f"playlist.{result['id']}.perms.remove": member.id}})
            
            return await send_localized_message(ctx, 'playlist.permissions.revoked', member, permission, result['playlist']['name'])
        
        else:
            return await send_localized_message(ctx, 'playlist.permissions.invalidAction', ephemeral=True)

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
            return await send_localized_message(ctx, 'playlist.errors.nameOverLimit', ephemeral=True)
        if name.lower() == newname.lower():
            return await send_localized_message(ctx, 'playlist.errors.sameName', ephemeral=True)
        user = await check_playlist(ctx, full=True)
        found, id = False, 0
        for data in user:
            if user[data]['name'].lower() == name.lower():
                found, id = True, data
            if user[data]['name'].lower() == newname.lower():
                return await send_localized_message(ctx, 'playlist.errors.exists', ephemeral=True)

        if not found:
            return await send_localized_message(ctx, 'playlist.errors.notFound', name, ephemeral=True)

        await MongoDBHandler.update_user(ctx.author.id, {"$set": {f'playlist.{id}.name': newname}})
        await send_localized_message(ctx, 'playlist.actions.renamed', name, newname)

    @playlist.command(name="inbox", aliases=get_aliases("inbox"))
    @commands.dynamic_cooldown(cooldown_check, commands.BucketType.guild)
    async def inbox(self, ctx: commands.Context) -> None:
        "Show your playlist invitation."
        user = await MongoDBHandler.get_user(ctx.author.id)
        max_p, _, _ = Config().get_playlist_config()

        if not user['inbox']:
            return await send_localized_message(ctx, "playlist.inbox.noMessages", ephemeral=True)

        inbox = user['inbox'].copy()
        view = InboxView(ctx.author, user['inbox'])
        view.response = await dispatch_message(ctx, view.build_embed(), view=view, ephemeral=True)
        await view.wait()

        if inbox == user['inbox']:
            return
        
        update_data, dId = {}, {dId for dId in user["playlist"]}
        for data in view.new_playlist[:(max_p - len(user['playlist']))]:
            addId = assign_playlist_id(dId)
            await MongoDBHandler.update_user(data['sender'], {"$push": {f"playlist.{data['referId']}.perms.read": ctx.author.id}})
            update_data[f'playlist.{addId}'] = {
                'user': data['sender'], 'referId': data['referId'],
                'name': f"Share{time.strftime('%M%S', time.gmtime(int(data['time'])))}",
                'type': 'share'
            }
            update_data["inbox"] = view.inbox
            dId.add(addId)

        if update_data:
            await MongoDBHandler.update_user(ctx.author.id, {"$set": update_data})

    @playlist.command(name="add", aliases=get_aliases("add"))
    @commands.dynamic_cooldown(cooldown_check, commands.BucketType.guild)
    @app_commands.describe(
        name="The name of the playlist.",
        query="Input a query or a searchable link."
    )
    @app_commands.autocomplete(name=playlist_autocomplete)
    async def add(self, ctx: commands.Context, name: str, query: str) -> None:
        "Add tracks in to your custom playlist."
        result = await check_playlist(ctx, name.lower(), share=True, share_perm='write')
        if not result['playlist']:
            if result.get('error') == 'permission':
                return await send_localized_message(ctx, 'playlist.errors.noAccess', ephemeral=True)
            return await send_localized_message(ctx, 'playlist.errors.notFound', name, ephemeral=True)
        if result['playlist']['type'] == 'link':
            return await send_localized_message(ctx, 'playlist.errors.notAllowed', ephemeral=True)
        
        _, max_t, _ = Config().get_playlist_config()
        if len(result['playlist']['tracks']) >= max_t:
            return await send_localized_message(ctx, 'playlist.errors.trackLimitReached', max_t, ephemeral=True)

        results = await voicelink.NodePool.get_node().get_tracks(query, requester=ctx.author)
        if not results:
            return await send_localized_message(ctx, 'player.errors.noTrackFound')
        
        if isinstance(results, voicelink.Playlist):
            return await send_localized_message(ctx, 'playlist.errors.playlistLinkNotAllowed', ephemeral=True)
        
        if results[0].is_stream:
            return await send_localized_message(ctx, 'playlist.errors.streamNotAllowed', ephemeral=True)

        owner_id = result.get('owner_id', ctx.author.id)
        owner_playlist_id = result.get('owner_playlist_id', result['id'])
        await MongoDBHandler.update_user(owner_id, {"$push": {f'playlist.{owner_playlist_id}.tracks': results[0].track_id}})
        owner_display = resolve_owner_display(ctx, owner_id)
        await send_localized_message(ctx, 'playlist.actions.trackAdded', results[0].title, owner_display, result['playlist']['name'])

    @playlist.command(name="remove", aliases=get_aliases("remove"))
    @commands.dynamic_cooldown(cooldown_check, commands.BucketType.guild)
    @app_commands.describe(
        name="The name of the playlist.",
        position="Input a position from the playlist to be removed."
    )
    @app_commands.autocomplete(name=playlist_autocomplete)
    async def remove(self, ctx: commands.Context, name: str, position: int):
        "Remove song from your favorite playlist."
        result = await check_playlist(ctx, name.lower(), share=True, share_perm='remove')
        if not result['playlist']:
            if result.get('error') == 'permission':
                return await send_localized_message(ctx, 'playlist.errors.noAccess', ephemeral=True)
            return await send_localized_message(ctx, 'playlist.errors.notFound', name, ephemeral=True)
        if result['playlist']['type'] == 'link':
            return await send_localized_message(ctx, 'playlist.errors.notAllowed', ephemeral=True)
        if not 0 < position <= len(result['playlist']['tracks']):
            return await send_localized_message(ctx, 'playlist.errors.positionNotFound', position, name)

        owner_id = result.get('owner_id', ctx.author.id)
        owner_playlist_id = result.get('owner_playlist_id', result['id'])
        await MongoDBHandler.update_user(owner_id, {"$pull": {f'playlist.{owner_playlist_id}.tracks': result['playlist']['tracks'][position - 1]}})
        
        track = voicelink.Track.decode(result['playlist']['tracks'][position - 1])
        owner_display = resolve_owner_display(ctx, owner_id)
        await send_localized_message(ctx, 'playlist.actions.trackRemoved', track.get("title"), owner_display, name)

    @playlist.command(name="clear", aliases=get_aliases("clear"))
    @commands.dynamic_cooldown(cooldown_check, commands.BucketType.guild)
    @app_commands.autocomplete(name=playlist_autocomplete)
    async def clear(self, ctx: commands.Context, name: str) -> None:
        "Remove all songs from your favorite playlist."
        result = await check_playlist(ctx, name.lower(), share=True, share_perm='remove')
        if not result['playlist']:
            if result.get('error') == 'permission':
                return await send_localized_message(ctx, 'playlist.errors.noAccess', ephemeral=True)
            return await send_localized_message(ctx, 'playlist.errors.notFound', name, ephemeral=True)

        if result['playlist']['type'] == 'link':
            return await send_localized_message(ctx, 'playlist.errors.notAllowed', ephemeral=True)

        owner_id = result.get('owner_id', ctx.author.id)
        owner_playlist_id = result.get('owner_playlist_id', result['id'])
        await MongoDBHandler.update_user(owner_id, {"$set": {f'playlist.{owner_playlist_id}.tracks': []}})
        await send_localized_message(ctx, 'playlist.actions.cleared', name)

    @playlist.command(name="export", aliases=get_aliases("export"))
    @commands.dynamic_cooldown(cooldown_check, commands.BucketType.guild)
    @app_commands.autocomplete(name=playlist_autocomplete)
    async def export(self, ctx: commands.Context, name: str) -> None:
        "Exports the entire playlist to a text file"
        result = await check_playlist(ctx, name.lower())
        if not result['playlist']:
            return await send_localized_message(ctx, 'playlist.errors.notFound', name, ephemeral=True)
        
        if result['playlist']['type'] == 'link':
            tracks = await search_playlist(result['playlist']['uri'], ctx.author, time_needed=False)
        else:
            if not result['playlist']['tracks']:
                return await send_localized_message(ctx, 'playlist.errors.noTrack', result['playlist']['name'], ephemeral=True)

            _tracks = []
            for track in result['playlist']['tracks']:
                _tracks.append(voicelink.Track(track_id=track, info=voicelink.Track.decode(track), requester=ctx.author))
                    
            tracks = {"name": result['playlist']['name'], "tracks": _tracks}

        if not tracks:
            return await send_localized_message(ctx, 'playlist.errors.noTrack', result['playlist']['name'], ephemeral=True)

        temp = ""
        raw = "----------->Raw Info<-----------\n"

        total_length = 0
        for index, track in enumerate(tracks['tracks'], start=1):
            temp += f"{index}. {track.title} [{format_ms(track.length)}]\n"
            raw += track.track_id
            if index != len(tracks['tracks']):
                raw += ","
            total_length += track.length

        temp = "!Remember do not change this file!\n------------->Info<-------------\nPlaylist: {} ({})\nRequester: {} ({})\nTracks: {} - {}\n------------>Tracks<------------\n".format(
            tracks['name'], result['playlist']['type'],
            ctx.author.display_name, ctx.author.id,
            len(tracks['tracks']), format_ms(total_length)
        ) + temp
        temp += raw

        await ctx.send(content="", file=discord.File(StringIO(temp), filename=f"{tracks['name']}_playlist.txt"))

    @playlist.command(name="import", aliases=get_aliases("import"))
    @app_commands.describe(name="Give a name to your playlist.")
    @commands.dynamic_cooldown(cooldown_check, commands.BucketType.guild)
    async def _import(self, ctx: commands.Context, name: str, attachment: discord.Attachment):
        "Create your custom playlist."
        if len(name) > 10:
            return await send_localized_message(ctx, 'playlist.errors.nameOverLimit', ephemeral=True)
        
        max_p, _, _ = Config().get_playlist_config()
        user = await check_playlist(ctx, full=True)

        if len(user) >= max_p:
            return await send_localized_message(ctx, 'playlist.errors.limitReached', max_p, ephemeral=True)
        
        for data in user:
            if user[data]['name'].lower() == name.lower():
                return await send_localized_message(ctx, 'playlist.errors.exists', name, ephemeral=True)

        try:
            bytes = await attachment.read()
            track_ids = bytes.split(b"\n")[-1]
            track_ids = track_ids.decode().split(",")

            data = {'tracks': track_ids, 'perms': {'read': [], 'write': [], 'remove': []}, 'name': name, 'type': 'playlist'}
            await MongoDBHandler.update_user(ctx.author.id, {"$set": {f"playlist.{assign_playlist_id([data for data in user])}": data}})
            await send_localized_message(ctx, 'playlist.actions.create', name)

        except Exception as e:
            logger.error("Decode Error", exc_info=e)
            raise e

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Playlists(bot))