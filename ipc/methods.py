import time, re
import function as func

from typing import List, Dict, Union, Optional

from discord import User, Member, VoiceChannel
from discord.ext import commands
from voicelink import Player, Track, Playlist, NodePool, decode, LoopType, Filters
from addons import LYRICS_PLATFORMS

RATELIMIT_COUNTER: Dict[int, Dict[str, float]] = {}
SCOPES = {
    "prefix": str,
    "lang": str,
    "queueType": str,
    "dj": int,
    "controller": bool,
    "24/7": bool,
    "votedisable": bool,
    "duplicateTrack": bool,
    "default_controller": dict,
    "stage_announce_template": str
}

class SystemMethod:
    def __init__(self, function: callable, *, credit: int = 1):
        self.function: callable = function
        self.params: List[str] = ["bot", "data"]
        self.credit: int = credit

class PlayerMethod(SystemMethod):
    def __init__(self, function, *, credit: int = 1, auto_connect: bool = False):
        super().__init__(function, credit=credit)
        self.params: List[str] = ["player", "member", "data"]
        self.auto_connect: bool = auto_connect

def require_permission(only_admin: bool = False):
    def decorator(func) -> callable:
        async def wrapper(player: Player, member: Member, dict: Dict) -> Optional[Dict]:
            if only_admin and not member.guild_permissions.manage_guild:
                return error_msg("Only the admins may use this function!", user_id=member.id)
            if not player.is_privileged(member):
                return error_msg("Only the DJ or admins may use this function!", user_id=member.id)
            return await func(player, member, dict)
        return wrapper
    return decorator

def error_msg(msg: str, *, user_id: int = None, guild_id: int = None, level: str = "info") -> Dict:
    payload = {"op": "errorMsg", "level": level, "msg": msg}
    if user_id:
        payload["userId"] = str(user_id)
    if guild_id:
        payload["guildId"] = str(guild_id)

    return payload

async def connect_channel(member: Member, bot: commands.Bot) -> Player:
    if not member.voice:
        return

    channel = member.voice.channel
    try:
        settings = await func.get_settings(channel.guild.id)
        player: Player = await channel.connect(cls=Player(bot, channel, func.TempCtx(member, channel), settings))
        await player.send_ws({"op": "createPlayer", "memberIds": [str(member.id) for member in channel.members]})
        return player
    except:
        return

async def initBot(bot: commands.Bot, data: Dict) -> Dict:
    user_id = int(data.get("userId"))
    user = bot.get_user(user_id)
    if not user:
        user = await bot.fetch_user(user_id)

    if user:
        return {
            "op": "initBot",
            "userId": str(user_id),
            "botName": bot.user.display_name,
            "botAvatar": bot.user.display_avatar.url,
            "botId": str(bot.user.id)
        }
    
async def initUser(bot: commands.Bot, data: Dict) -> Dict:
    user_id = int(data.get("userId"))
    data = await func.get_user(user_id)

    for mail in data.get("inbox"):
        sender = bot.get_user(mail.get("sender"))
        if not sender:
            sender = await bot.fetch_user(mail.get("sender"))

        if not sender:
            data.get("inbox").remove(mail)

        mail["sender"] = {"avatarUrl": sender.display_avatar.url, "name": sender.display_name, "id": str(sender.id)}

    return {
        "op": "initUser",
        "userId": str(user_id),
        "data": data
    }
    
async def initPlayer(player: Player, member: Member, data: Dict) -> Dict:
    player._ipc_connection = True
    available_filters = []
    for name, filter_cls in Filters.get_available_filters().items():
        filter = filter_cls()
        available_filters.append({"tag": name, "scope": filter.scope, "payload": filter.payload})

    return {
        "op": "initPlayer",
        "guildId": str(player.guild.id),
        "userId": str(data.get("userId")),
        "users": [{
            "userId": str(member.id),
            "avatarUrl": member.display_avatar.url,
            "name": member.name
        } for member in player.channel.members ],
        "tracks": [ {"trackId": track.track_id, "requesterId": str(track.requester.id)} for track in player.queue._queue ],
        "repeatMode": player.queue.repeat.lower(),
        "channelName": player.channel.name,
        "currentQueuePosition": player.queue._position + (0 if player.is_playing else 1),
        "currentPosition": 0 or player.position if player.is_playing else 0,
        "isPlaying": player.is_playing,
        "isPaused": player.is_paused,
        "isDj": player.is_privileged(member, check_user_join=False),
        "autoplay": player.settings.get("autoplay", False),
        "volume": player.volume,
        "filters": [{"tag": filter.tag, "scope": filter.scope, "payload": filter.payload} for filter in player.filters.get_filters()],
        "availableFilters": available_filters
    }

async def closeConnection(bot: commands.Bot, data: Dict) -> None:
    guild_id = int(data.get("guildId"))
    guild = bot.get_guild(guild_id)
    player: Player = guild.voice_client
    if player:
        player._ipc_connection = False

async def getRecommendation(bot: commands.Bot, data: Dict) -> None: 
    node = NodePool.get_node()
    if not node:
        return
    
    track_data = decode(track_id := data.get("trackId"))
    track = Track(track_id=track_id, info=track_data, requester=bot.user)
    tracks: List[Track] = await node.get_recommendations(track, limit=60)

    return {
        "op": "getRecommendation",
        "userId": str(data.get("userId")),
        "callback": data.get("callback"),
        "tracks": [track.track_id for track in tracks] if tracks else []
    }

async def skipTo(player: Player, member: Member, data: Dict) -> None:
    if not player.is_privileged(member):
        if player.current and member == player.current.requester:
            pass

        elif member in player.skip_votes:
            return error_msg(player.get_msg('voted'), user_id=member.id)
        
        else:
            player.skip_votes.add(member)
            if len(player.skip_votes) < (required := player.required()):
                return error_msg(player.get_msg('skipVote').format(member, len(player.skip_votes), required), guild_id=player.guild.id)

    index = data.get("index", 1)
    if index > 1:
        player.queue.skipto(index)

    if player.queue._repeat.mode == LoopType.TRACK:
        await player.set_repeat(LoopType.OFF)
    await player.stop()

async def backTo(player: Player, member: Member, data: Dict) -> None:
    if not player.is_privileged(member):
        if player.current and member == player.current.requester:
            pass

        elif member in player.skip_votes:
            return error_msg(player.get_msg('voted'), user_id=member.id)
        
        else:
            player.skip_votes.add(member)
            if len(player.skip_votes) < (required := player.required()):
                return error_msg(player.get_msg('backVote').format(member, len(player.skip_votes), required), guild_id=player.guild.id)
    
    index = data.get("index", 1)
    if not player.is_playing:
        player.queue.backto(index)
        await player.do_next()
    else:
        player.queue.backto(index + 1)
        await player.stop()

@require_permission()
async def moveTrack(player: Player, member: Member, data: Dict) -> None:
    index = data.get("index")
    new_index = data.get("newIndex")
    if index == new_index:
        return
    
    await player.move_track(index, new_index, member)

async def addTracks(player: Player, member: Member, data: Dict) -> None:
    _type = data.get("type", "addToQueue")
    tracks = [Track(
        track_id=track_id, 
        info=decode(track_id),
        requester=member
    ) for track_id in data.get("tracks", [])]

    if _type == "addToQueue":
        await player.add_track(tracks)

    elif _type == "forcePlay":
        await player.add_track(tracks, at_front=True)
        if player.is_playing:
            return await player.stop()
    
    elif _type == "addNext":
        await player.add_track(tracks, at_front=True)

    if not player.is_playing:
        await player.do_next()

async def getTracks(bot: commands.Bot, data: Dict) -> Dict:
    query = data.get("query", None)

    if query:
        payload = {"op": "getTracks", "userId": data.get("userId"), "callback": data.get("callback")}
        tracks = await NodePool.get_node().get_tracks(query=query, requester=None)
        if not tracks:
            return payload

        payload["tracks"] = [ track.track_id for track in (tracks.tracks if isinstance(tracks, Playlist) else tracks ) ]
        return payload

async def searchAndPlay(player: Player, member: Member, data: Dict) -> None:
    payload = await getTracks(player.bot, data)
    await addTracks(player, member, payload)

async def shuffleTrack(player: Player, member: Member, data: Dict) -> None:
    if not player.is_privileged(member):
        if member in player.shuffle_votes:
            return error_msg(player.get_msg('voted'), user_id=member.id) 

        player.shuffle_votes.add(member)
        if len(player.shuffle_votes) < (required := player.required()):
            return error_msg(player.get_msg('shuffleVote').format(member, len(player.skip_votes), required), guild_id=player.guild.id)
    
    await player.shuffle(data.get("type", "queue"), member)

@require_permission()
async def repeatTrack(player: Player, member: Member, data: Dict) -> None:
    await player.set_repeat(requester=member)

@require_permission()
async def removeTrack(player: Player, member: Member, data: Dict) -> None:
    index, index2 = data.get("index"), data.get("index2")
    await player.remove_track(index, index2, requester=member)

@require_permission()
async def clearQueue(player: Player, member: Member, data: Dict) -> None:
    queue_type = data.get("queueType", "").lower()
    await player.clear_queue(queue_type, member)

@require_permission(only_admin=True)
async def updateVolume(player: Player, member: Member, data: Dict) -> None:
    volume = data.get("volume", 100)
    await func.update_settings(player.guild.id, {"$set": {"volume": volume}})
    await player.set_volume(volume=volume, requester=member)

async def updatePause(player: Player, member: Member, data: Dict) -> None:
    pause = data.get("pause", True)
    if not player.is_privileged(member):
        if pause:
            if member in player.pause_votes:
                return error_msg(player.get_msg('voted'), user_id=member.id)

            player.pause_votes.add(member)
            if len(player.pause_votes) < (required := player.required()):
                return error_msg(player.get_msg('pauseVote').format(member, len(player.pause_votes), required), guild_id=player.guild.id)

        else:
            if member in player.resume_votes:
                return error_msg(player.get_msg('voted'), user_id=member.id)
            
            player.resume_votes.add(member)
            if len(player.resume_votes) < (required := player.required()):
                return error_msg(player.get_msg('resumeVote').format(member, len(player.resume_votes), required), guild_id=player.guild.id)

    await player.set_pause(pause, member)

@require_permission()
async def updatePosition(player: Player, member: Member, data: Dict) -> None:
    position = data.get("position");
    await player.seek(position, member);

async def toggleAutoplay(player: Player, member: Member, data: Dict) -> Dict:
    if not player.is_privileged(member):
        return error_msg(player.get_msg('missingPerms_autoplay'))

    check = data.get("status", False)
    player.settings['autoplay'] = check

    if not player.is_playing:
        await player.do_next()

    return {
        "op": "toggleAutoplay",
        "status": check,
        "guildId": player.guild.id,
        "requesterId": str(member.id)
    }

@require_permission()
async def updateFilter(player: Player, member: Member, data: Dict) -> None:
    updateType = data.get("type", "add")
    filter_tag = data.get("tag")

    if updateType == "add":
        available_filters = Filters.get_available_filters()
        filter_cls = available_filters.get(filter_tag)
        if not filter_cls:
            return
        
        payload = {}
        if "payload" in data:
            payload = data.get("payload").get(list(data.get("payload").keys()[0]), {})
        if player.filters.has_filter(filter_tag=filter_tag):
            player.filters.remove_filter(filter_tag=filter_tag)
        await player.add_filter(filter=filter_cls(**payload), requester=member)

    elif updateType == "remove":
        await player.remove_filter(filter_tag=filter_tag, requester=member)

    else:
        await player.reset_filter(requester=member)

async def _loadPlaylist(playlist: Dict) -> Optional[List[Track]]:
    if playlist.get("type") == "link":
        tracks: List[Track]= await NodePool.get_node().get_tracks(playlist.get("uri"), requester=None)
        if tracks:
            return [track.track_id for track in (tracks.tracks if isinstance(tracks, Playlist) else tracks)]
    else:
        return playlist.get("tracks", [])

def _assign_playlist_id(existed: list) -> str:
    for i in range(200, 210):
        if str(i) not in existed:
            return str(i)
        
async def _getPlaylist(user_id: int, playlist_id: str) -> Dict:
    playlists = await func.get_user(user_id, "playlist")
    playlist = playlists.get(playlist_id)
    if not playlist:
        return
    
    if playlist["type"] == "share":
        target_user = await func.get_user(playlist["user"], "playlist")
        target_playlist = target_user.get(playlist["referId"])
        if target_playlist and user_id in target_playlist.get("perms", {}).get("read", []):
            playlist["tracks"] = await _loadPlaylist(target_playlist)
    else:
        playlist["tracks"] = await _loadPlaylist(playlist)

    return playlist

async def getPlaylist(bot: commands.Bot, data: Dict) -> Dict:
    user_id = int(data.get("userId"))
    playlist_id = str(data.get("playlistId"))

    payload = {"op": "loadPlaylist", "playlistId": playlist_id, "userId": str(user_id)}
    playlist = await _getPlaylist(user_id, playlist_id)
    payload["tracks"] = playlist["tracks"] if playlist else []
    
    return payload
    
async def updatePlaylist(bot: commands.Bot, data: Dict) -> Dict:
    user_id = int(data.get("userId"))
    playlist_id = str(data.get("playlistId"))
    _type = data.get("type")
    
    if not playlist_id and not _type == "createPlaylist":
        return error_msg("Unable to process this request without a playlist ID.", user_id=user_id, level="error")
    
    rank, max_p, max_t = func.check_roles()
    if _type == "createPlaylist":
        name, playlist_url = data.get("playlistName"), data.get("playlistUrl")
        if not name:
            return {
                "op": "updatePlaylist",
                "status": "error",
                "msg": f"You must enter name for this field!",
                "field": "playlistName",
                "userId": str(user_id)
            }
        
        playlist = await func.get_user(user_id, "playlist")
        if len(list(playlist.keys())) >= max_p:
            return {
                "op": "updatePlaylist",
                "status": "error",
                "msg": f"You cannot create more than '{max_p}' playlists!",
                "field": "playlistName",
                "userId": str(user_id)
            }

        for playlist_data in playlist.values():
            if playlist_data['name'].lower() == name.lower():
                return {
                    "op": "updatePlaylist",
                    "status": "error",
                    "msg": f"Playlist '{name}' already exists.",
                    "field": "playlistName",
                    "userId": str(user_id)
                }
        
        if playlist_url:
            tracks = await NodePool.get_node().get_tracks(playlist_url, requester=None)
            if not isinstance(tracks, Playlist):
                return {
                    "op": "updatePlaylist",
                    "status": "error",
                    "msg": f"Please enter a valid link or public spotify or youtube playlist link.",
                    "field": "playlistUrl",
                    "userId": str(user_id)
                }

        assigned_playlist_id = _assign_playlist_id(list(playlist.keys()))
        data = {'uri': playlist_url, 'perms': {'read': []}, 'name': name, 'type': 'link'} if playlist_url else {'tracks': [], 'perms': {'read': [], 'write': [], 'remove': []}, 'name': name, 'type': 'playlist'}
        await func.update_user(user_id, {"$set": {f"playlist.{assigned_playlist_id}": data}})
        return {
            "op": "updatePlaylist",
            "status": "created",
            "playlistId": assigned_playlist_id,
            "msg": f"You have created '{name}' playlist.",
            "userId": str(user_id),
            "data": data
        }
        
    elif _type == "removePlaylist":
        playlist = await _getPlaylist(user_id, playlist_id)
        if playlist:
            if playlist['type'] == 'share':
                await func.update_user(playlist['user'], {"$pull": {f"playlist.{playlist['referId']}.perms.read": user_id}})

            await func.update_user(user_id, {"$unset": {f"playlist.{playlist_id}": 1}})

        return {
            "op": "updatePlaylist",
            "status": "deleted",
            "playlistId": playlist_id,
            "msg": f"You have removed playlist '{playlist['name']}'",
            "userId": str(user_id)
        }
    
    elif _type == "renamePlaylist":
        name = data.get("name")
        if not name:
            return {
                "op": "updatePlaylist",
                "status": "error",
                "msg": f"You must enter name for this field!",
                "field": "playlistName",
                "userId": str(user_id)
            }
        
        playlist = await func.get_user(user_id, "playlist")
        for data in playlist.values():
            if data['name'].lower() == name.lower():
                return {
                    "op": "updatePlaylist",
                    "status": "error",
                    "msg": f"Playlist '{data['name']}' already exists.",
                    "field": "playlistName",
                    "userId": str(user_id)
                }

        await func.update_user(user_id, {"$set": {f'playlist.{playlist_id}.name': name}})
        return {
            "op": "updatePlaylist",
            "status": "renamed",
            "name": name,
            "playlistId": playlist_id,
            "msg": f"You have renamed the playlist to '{name}'.",
            "field": "playlistName",
            "userId": str(user_id)
        }
    
    elif _type == "addTrack":
        track_id = data.get("trackId")
        if not track_id:
            return error_msg("No track ID could be located.", user_id=user_id, level='error')
        
        playlist = await _getPlaylist(user_id, playlist_id)
        if playlist['type'] in ['share', 'link']:
            return error_msg("You cannot add songs to a linked playlist through Vocard.", user_id=user_id, level='error')
        
        rank, max_p, max_t = func.check_roles()
        if len(playlist['tracks']) >= max_t:
            return error_msg(f"You have reached the limit! You can only add {max_t} songs to your playlist.", user_id=user_id)

        decoded_track = Track(track_id=track_id, info=decode(track_id), requester=None)
        if decoded_track.is_stream:
            return error_msg("You are not allowed to add streaming videos to your playlist.", user_id=user_id)
        
        await func.update_user(user_id, {"$push": {f'playlist.{playlist_id}.tracks': track_id}})
        return {
            "op": "updatePlaylist",
            "status": "addTrack",
            "playlistId": playlist_id,
            "trackId": track_id,
            "msg": f"Added {decoded_track.title} into '{playlist['name']}' playlist.",
            "userId": str(user_id)
        }
        
    elif _type == "removeTrack":
        track_id, track_position = data.get("trackId"), data.get("trackPosition", 0)
        if not track_id:
            return error_msg("No track ID could be located.", user_id=user_id, level='error')
        
        playlist = await _getPlaylist(user_id, playlist_id)
        if not playlist:
            return error_msg("Playlist not found!", user_id=user_id, level='error')
        
        if playlist['type'] in ['share', 'link']:
            return error_msg("You cannot remove songs from a linked playlist through Vocard.", user_id=user_id, level='error')
        
        if not 0 <= track_position < len(playlist['tracks']):
            return error_msg("Cannot find the position from your playlist.", user_id=user_id, level="error")

        if playlist['tracks'][track_position] != track_id:
            return error_msg("Something wrong while removing the track from your playlist.", user_id=user_id, level='error')
        
        await func.update_user(user_id, {"$pull": {f'playlist.{playlist_id}.tracks': playlist['tracks'][track_position]}})
        
        decoded_track = decode(playlist['tracks'][track_position])
        return {
            "op": "updatePlaylist",
            "status": "removeTrack",
            "playlistId": playlist_id,
            "trackPosition": track_position,
            "trackId": track_id,
            "msg": f"Removed '{decoded_track['title']}' from '{playlist['name']}' playlist.",
            "userId": str(user_id)
        }

    elif _type == "updateInbox":
        user = await func.get_user(user_id)
        is_accept = data.get("accept", False)

        if is_accept and len(list(user.get("playlist").keys())) >= max_p:
            return error_msg(f"You cannot create more than '{max_p}' playlists!", user_id=user_id, level = "error")

        info = data.get("referId", "").split("-")
        sender_id, refer_id = info[0], info[1]
        inbox = user.get("inbox")

        payload = {"op": "updatePlaylist", "status": "updateInbox", "userId": str(user_id), "accept": is_accept, "senderId": sender_id, "referId": refer_id}
        for index, mail in enumerate(inbox.copy()):
            if not (str(mail.get("sender")) == sender_id and mail.get("referId") == refer_id):
                continue
            
            del inbox[index]
            if is_accept:
                share_playlists = await func.get_user(mail["sender"], "playlist")
                if refer_id not in share_playlists:
                    return error_msg("The shared playlist couldn’t be found. It’s possible that the user has already deleted it.", user_id=user_id)
                
                assigned_playlist_id = _assign_playlist_id(list(user.get("playlist", []).keys()))
                playlist_name = f"Share{time.strftime('%M%S', time.gmtime(int(mail['time'])))}"
                share_playlist = share_playlists.get(refer_id)
                share_playlist.update({
                    "name": playlist_name,
                    "type": "share"
                })
                await func.update_user(mail['sender'], {"$push": {f"playlist.{mail['referId']}.perms.read": user_id}})
                await func.update_user(user_id, {"$set": {
                    f'playlist.{assigned_playlist_id}': {
                        'user': mail['sender'], 'referId': mail['referId'],
                        'name': playlist_name,
                        'type': 'share'
                    },
                    "inbox": inbox
                }})

                payload.update({
                    "playlistId": assigned_playlist_id,
                    "msg": f"You have created '{playlist_name}' playlist.",
                    "data": share_playlist,
                })

            await func.update_user(user_id, {"$set": {"inbox": inbox}})
            return payload

async def getMutualGuilds(bot: commands.Bot, data: Dict) -> Dict:
    user_id = int(data.get("userId"))

    payload = {"op": "getMutualGuilds", "mutualGuilds": {}, "inviteGuilds": {}, "userId": str(user_id)}
    for guild_id, guild_info in data.get("guilds", {}).items():
        if guild := bot.get_guild(int(guild_id)):
            payload["mutualGuilds"][guild_id] = {
                **guild_info,
                "memberCount": guild.member_count
            }
        else:
            payload["inviteGuilds"][guild_id] = {**guild_info}

    return payload

async def getSettings(bot: commands.Bot, data: Dict) -> Dict:
    user_id = int(data.get("userId"))
    guild_id  = int(data.get("guildId"))

    guild = bot.get_guild(guild_id)
    if not guild:
        return error_msg("Vocard don't have access to requested guild.", user_id=user_id, level="error")

    member = guild.get_member(user_id)
    if not member:
        return error_msg("You are not in the requested guild.", user_id=user_id, level="error")
    
    if not member.guild_permissions.manage_guild:
        return error_msg("You don't have permission to access the settings.", user_id=user_id, level='error')
    
    settings = await func.get_settings(guild_id)
    if "dj" in settings:
        role = guild.get_role(settings["dj"])
        if role:
            settings["dj"] = role.name

    return {
        "op": "getSettings",
        "settings": settings,
        "options": {
            "languages": list(func.LANGS.keys()),
            "queueModes": ["Queue", "FairQueue"],
            "roles": [role.name for role in guild.roles]
        },
        "guild": {
            "avatar": guild.icon.url if guild.icon else None,
            "name": guild.name,
            "id": str(guild_id)
        },
        "userId": str(user_id)
    }

async def getLyrics(bot: commands.Bot, data: Dict) -> Dict:
    title, artist, platform = data.get("title", ""), data.get("artist", ""), data.get("platform", "")
    if not platform or platform not in LYRICS_PLATFORMS:
        platform = func.settings.lyrics_platform
    
    lyrics_platform = LYRICS_PLATFORMS.get(platform)
    if lyrics_platform:
        lyrics: dict[str, str] = await lyrics_platform().get_lyrics(title, artist)
        return {
            "op": "getLyrics",
            "userId": data.get("userId"),
            "title": title,
            "artist": artist,
            "platform": platform,
            "lyrics": {_: re.findall(r'.*\n(?:.*\n){,22}', v or "") for _, v in lyrics.items()} if lyrics else {},
            "callback": data.get("callback")
        }

async def updateSettings(bot: commands.Bot, data: Dict) -> None:
    user_id = int(data.get("userId"))
    guild_id  = int(data.get("guildId"))

    guild = bot.get_guild(guild_id)
    if not guild:
        return error_msg("Vocard don't have access to required guild.", user_id=user_id, level="error")

    member = guild.get_member(user_id)
    if not member:
        return error_msg("You are not in the required guild.", user_id=user_id, level="error")
    
    if not member.guild_permissions.manage_guild:
        return error_msg("You don't have permission to change the settings.", user_id=user_id, level='error')
    
    data = data.get("settings", {})
    if "dj" in data:
        for role in guild.roles:
            if role.name.lower() == data["dj"]:
                data["dj"] = role.id
                break

    for key, value in data.copy().items():
        if key not in SCOPES or not isinstance(value, SCOPES[key]):
            del data[key]

    await func.update_settings(guild.id, {"$set": data})

METHODS: Dict[str, Union[SystemMethod, PlayerMethod]] = {
    "initBot": SystemMethod(initBot, credit=0),
    "initUser": SystemMethod(initUser, credit=2),
    "getPlaylist": SystemMethod(getPlaylist),
    "updatePlaylist": SystemMethod(updatePlaylist, credit=2),
    "getMutualGuilds": SystemMethod(getMutualGuilds),
    "getSettings": SystemMethod(getSettings),
    "getLyrics": SystemMethod(getLyrics),
    "updateSettings": SystemMethod(updateSettings),
    "getRecommendation": SystemMethod(getRecommendation, credit=5),
    "closeConnection": SystemMethod(closeConnection, credit=0),
    "getTracks": SystemMethod(getTracks, credit=5),
    "initPlayer": PlayerMethod(initPlayer),
    "skipTo": PlayerMethod(skipTo),
    "backTo": PlayerMethod(backTo),
    "moveTrack": PlayerMethod(moveTrack),
    "addTracks": PlayerMethod(addTracks, auto_connect=True),
    "shuffleTrack": PlayerMethod(shuffleTrack, credit=3),
    "repeatTrack": PlayerMethod(repeatTrack),
    "removeTrack": PlayerMethod(removeTrack),
    "clearQueue": PlayerMethod(clearQueue),
    "updateVolume": PlayerMethod(updateVolume, credit=2),
    "updatePause": PlayerMethod(updatePause),
    "updatePosition": PlayerMethod(updatePosition),
    "toggleAutoplay": PlayerMethod(toggleAutoplay),
    "updateFilter": PlayerMethod(updateFilter),
    "searchAndPlay": PlayerMethod(searchAndPlay, credit=5, auto_connect=True)
}

async def process_methods(ipc_client, bot: commands.Bot, data: Dict) -> None:
    op: str = data.get("op", "")
    method = METHODS.get(op)
    if not method or not (user_id := data.get("userId")):
        return

    user_id = int(user_id)
    if user_id not in RATELIMIT_COUNTER or (time.time() - RATELIMIT_COUNTER[user_id]["time"]) >= 300:
        RATELIMIT_COUNTER[user_id] = {"time": time.time(), "count": 0}
    
    else:
        if RATELIMIT_COUNTER[user_id]["count"] >= 100:
            return await ipc_client.send({"op": "rateLimited", "userId": str(user_id)})
        RATELIMIT_COUNTER[user_id]["count"] += method.credit

    try:
        env: Dict = {"bot": bot, "data": data}
        args: List = []
        
        params = method.params
        if not (type(method) == SystemMethod):
            if guild_id := data.get("guildId"):
                if (guild := bot.get_guild(int(guild_id))):
                    env["guild"] = guild

            else:
                user: User = bot.get_user(user_id)
                if not user:
                    return
                
                for guild in user.mutual_guilds:
                    member = guild.get_member(user_id)
                    if member.voice and member.voice.channel:
                        env["guild"] = guild
                        env["member"] = member
                        break

            if "member" in params and "member" not in env:
                if not (guild := env.get("guild")) or not (member := guild.get_member(user_id)):
                    return
                env["member"] = member
                
            if "player" in params:
                if not (guild := env.get("guild")) or not (player := guild.voice_client):
                    if not method.auto_connect or not (member := env.get("member")):
                        return
                    player = await connect_channel(member, bot)

                if not player or player.channel.id != member.voice.channel.id:
                    return
                
                env["player"] = player
        
        for param in params:
            args.append(env.get(param))
            
        if resp := await method.function(*args):
            await ipc_client.send(resp)

    except Exception as e:
        import traceback
        traceback.print_exc()
        payload = {
            "op": "errorMsg",
            "level": "error",
            "msg": str(e),
            "userId": str(user_id)
        }
        await ipc_client.send(payload)