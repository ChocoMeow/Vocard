import time, traceback
import function as func

from typing import List, Dict, Union, Optional

from discord import User, Member, VoiceChannel
from discord.ext import commands
from voicelink import Player, Track, Playlist, NodePool, decode, LoopType

RATELIMIT_COUNTER: Dict[int, Dict[str, float]] = {}

class TempCtx():
    def __init__(self, author: Member, channel: VoiceChannel) -> None:
        self.author = author
        self.channel = channel
        self.guild = channel.guild

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
        
def missingPermission(user_id: int):
    payload = {"op": "errorMsg", "level": "info", "msg": "Only the DJ or admins may use this funciton!"}
    payload["user_id"] = str(user_id)
    return payload

def error_msg(msg: str, *, user_id: int = None, guild_id: int = None, level: str = "info"):
    payload = {"op": "errorMsg", "level": level, "msg": msg}
    if user_id:
        payload["user_id"] = str(user_id)
    if guild_id:
        payload["guild_id"] = str(guild_id)

    return payload

async def connect_channel(member: Member, bot: commands.Bot) -> Player:
    if not member.voice:
        return

    channel = member.voice.channel
    try:
        settings = await func.get_settings(channel.guild.id)
        player: Player = await channel.connect(cls=Player(bot, channel, TempCtx(member, channel), settings))
        await player.send_ws({"op": "createPlayer", "member_ids": [str(member.id) for member in channel.members]})
        return player
    except:
        return

async def initBot(bot: commands.Bot, data: Dict) -> Dict:
    user_id = int(data.get("user_id"))
    user = bot.get_user(user_id)
    if not user:
        user = await bot.fetch_user(user_id)

    if user:
        return {
            "op": "initBot",
            "user_id": str(user_id),
            "bot_name": bot.user.display_name,
            "bot_avatar": bot.user.display_avatar.url,
            "bot_id": str(bot.user.id)
        }
    
async def initUser(bot: commands.Bot, data: Dict) -> Dict:
    user_id = int(data.get("user_id"))
    data = await func.get_user(user_id)
    
    return {
        "op": "initUser",
        "user_id": str(user_id),
        "data": data
    }
    
async def initPlayer(player: Player, member: Member, data: Dict) -> Dict:
    player._ipc_connection = True
    return {
        "op": "initPlayer",
        "guild_id": str(player.guild.id),
        "user_id": str(data.get("user_id")),
        "users": [{
            "user_id": str(member.id),
            "avatar_url": member.display_avatar.url,
            "name": member.name
        } for member in player.channel.members ],
        "tracks": [ track.track_id for track in player.queue._queue ],
        "repeat_mode": player.queue.repeat.lower(),
        "channel_name": player.channel.name,
        "current_queue_position": player.queue._position + (0 if player.is_playing else 1),
        "current_position": 0 or player.position if player.is_playing else 0,
        "is_playing": player.is_playing,
        "is_paused": player.is_paused,
        "is_dj": player.is_privileged(member, check_user_join=False),
        "autoplay": player.settings.get("autoplay", False)
    }

async def closeConnection(player: Player, member: Member, data: Dict) -> None:
    player._ipc_connection = False

async def getRecommendation(bot: commands.Bot, data: Dict) -> None: 
    node = NodePool.get_node()
    if not node:
        return
    
    track_data = decode(track_id := data.get("track_id"))
    track = Track(track_id=track_id, info=track_data, requester=bot.user)
    tracks: List[Track] = await node.get_recommendations(track, limit=60)

    return {
        "op": "getRecommendation",
        "user_id": str(data.get("user_id")),
        "region": data.get("region"),
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
            if len(player.skip_votes) >= (required := player.required()):
                pass
            else:
                return error_msg(player.get_msg('skipVote').format(member, len(player.skip_votes), required), guild_id=player.guild.id)

    index = data.get("index", 1)
    if index > 1:
        player.queue.skipto(index)

    if player.queue._repeat.mode == LoopType.track:
        await player.set_repeat(LoopType.off.name)
    await player.stop()

async def backTo(player: Player, member: Member, data: Dict) -> None:
    if not player.is_privileged(member):
        if player.current and member == player.current.requester:
            pass

        elif member in player.skip_votes:
            return error_msg(player.get_msg('voted'), user_id=member.id)
        else:
            player.skip_votes.add(member)
            if len(player.skip_votes) >= (required := player.required()):
                pass
            else:
                return error_msg(player.get_msg('backVote').format(member, len(player.skip_votes), required), guild_id=player.guild.id)
    
    index = data.get("index", 1)
    if not player.is_playing:
        player.queue.backto(index)
        await player.do_next()
    else:
        player.queue.backto(index + 1)
        await player.stop()

async def moveTrack(player: Player, member: Member, data: Dict) -> None:
    if not player.is_privileged(member):
        return missingPermission(member.id)

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
        await player.add_track(tracks, at_font=True)
        if player.is_playing:
            return await player.stop()
    
    elif _type == "addNext":
        await player.add_track(tracks, at_font=True)

    if not player.is_playing:
        await player.do_next()

async def getTracks(player: Player, member: Member, data: Dict) -> Dict:
    query = data.get("query", None)

    if query:
        payload = {"op": "getTracks", "user_id": str(member.id)}
        tracks = await player.get_tracks(query, requester=member)
        if not tracks:
            return payload
        
        if isinstance(tracks, Playlist):
            tracks = [ track for track in tracks.tracks[:50] ]

        payload["tracks"] = [ track.track_id for track in tracks ]
        return payload
    
async def shuffleTrack(player: Player, member: Member, data: Dict) -> None:
    if not player.is_privileged(member):

        if member in player.shuffle_votes:
            return error_msg(player.get_msg('voted'), user_id=member.id) 
        else:
            player.shuffle_votes.add(member)
            if len(player.shuffle_votes) >= (required := player.required()):
                pass
            else:
                return error_msg(player.get_msg('shuffleVote').format(member, len(player.skip_votes), required), guild_id=player.guild.id)
    
    await player.shuffle(data.get("type", "queue"), member)

async def repeatTrack(player: Player, member: Member, data: Dict) -> None:
    if not player.is_privileged(member):
        return missingPermission(member.id)
    
    await player.set_repeat(requester=member)

async def removeTrack(player: Player, member: Member, data: Dict) -> None:
    if not player.is_privileged(member):
        return missingPermission(member.id)
    
    index, index2 = data.get("index"), data.get("index2")
    await player.remove_track(index, index2, requester=member)
        
async def updatePause(player: Player, member: Member, data: Dict) -> None:
    pause = data.get("pause", True)
    if not player.is_privileged(member):
        if pause:
            if member in player.pause_votes:
                return error_msg(player.get_msg('voted'), user_id=member.id)
            else:
                player.pause_votes.add(member)
                if len(player.pause_votes) >= (required := player.required()):
                    pass
                else:
                    return error_msg(player.get_msg('pauseVote').format(member, len(player.pause_votes), required), guild_id=player.guild.id)
        else:
            if member in player.resume_votes:
                return error_msg(player.get_msg('voted'), user_id=member.id)
            else:
                player.resume_votes.add(member)
                if len(player.resume_votes) >= (required := player.required()):
                    pass
                else:
                    return error_msg(player.get_msg('resumeVote').format(member, len(player.resume_votes), required), guild_id=player.guild.id)

    player.pause_votes.clear() if pause else player.resume_votes.clear()
    await player.set_pause(pause, member)

async def updatePosition(player: Player, member: Member, data: Dict) -> None:
    if not player.is_privileged(member):
        return missingPermission(member.id)
    
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
        "guild_id": player.guild.id,
        "requester_id": member.id
    }

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

async def getPlaylist(bot: commands.Bot, data: Dict) -> None:
    user_id = int(data.get("user_id"))
    playlist_id = str(data.get("playlist_id"))

    payload = {"op": "loadPlaylist", "playlist_id": playlist_id, "user_id": str(user_id)}
    playlist = await _getPlaylist(user_id, playlist_id)
    payload["tracks"] = playlist["tracks"] if playlist else []
    
    return payload
    
async def updatePlaylist(bot: commands.Bot, data: Dict) -> None:
    user_id = int(data.get("user_id"))
    playlist_id = str(data.get("playlist_id"))
    _type = data.get("type")
    
    rank, max_p, max_t = func.check_roles()
    if _type == "createPlaylist":
        name, playlist_url = data.get("name"), data.get("playlist_url")
        if not name:
            return {
                "op": "updatePlaylist",
                "status": "error",
                "msg": f"You must enter name for this field!",
                "field": "create-playlist-name",
                "user_id": str(user_id)
            }
        
        playlist = await func.get_user(user_id, "playlist")
        if len(list(playlist.keys())) >= max_p:
            return {
                "op": "updatePlaylist",
                "status": "error",
                "msg": f"You cannot create more than '{max_p}' playlists!",
                "field": "create-playlist-name",
                "user_id": str(user_id)
            }

        for playlist_data in playlist.values():
            if playlist_data['name'].lower() == name.lower():
                return {
                    "op": "updatePlaylist",
                    "status": "error",
                    "msg": f"Playlist '{name}' already exists.",
                    "field": "create-playlist-name",
                    "user_id": str(user_id)
                }
        
        if playlist_url:
            tracks = await NodePool.get_node().get_tracks(playlist_url, requester=None)
            if not isinstance(tracks, Playlist):
                return {
                    "op": "updatePlaylist",
                    "status": "error",
                    "msg": f"Please enter a valid link or public spotify or youtube playlist link.",
                    "field": "create-playlist-url",
                    "user_id": str(user_id)
                }

        assgined_playlist_id = _assign_playlist_id([data for data in playlist])
        data = {'uri': playlist_url, 'perms': {'read': []}, 'name': name, 'type': 'link'} if playlist_url else {'tracks': [], 'perms': {'read': [], 'write': [], 'remove': []}, 'name': name, 'type': 'playlist'}
        await func.update_user(user_id, {"$set": {f"playlist.{assgined_playlist_id}": data}})
        return {
            "op": "updatePlaylist",
            "status": "created",
            "playlist_id": assgined_playlist_id,
            "msg": f"You have created '{name}' playlist.",
            "user_id": str(user_id),
            "data": data
        }
        
    elif _type == "removePlaylist":
        playlist = await _getPlaylist(user_id, playlist_id)
        if playlist['type'] == 'share':
            await func.update_user(playlist['user'], {"$pull": {f"playlist.{playlist['referId']}.perms.read": user_id}})

        await func.update_user(user_id, {"$unset": {f"playlist.{playlist_id}": 1}})

        return {
            "op": "updatePlaylist",
            "status": "deleted",
            "playlist_id": playlist_id,
            "msg": f"You have removed playlist '{playlist['name']}'",
            "user_id": str(user_id)
        }
    
    elif _type == "renamePlaylist":
        name = data.get("name")
        if not name:
            return {
                "op": "updatePlaylist",
                "status": "error",
                "msg": f"You must enter name for this field!",
                "field": "rename-playlist-name",
                "user_id": str(user_id)
            }
        
        playlist = await func.get_user(user_id, "playlist")
        for data in playlist.values():
            if data['name'].lower() == name.lower():
                return {
                    "op": "updatePlaylist",
                    "status": "error",
                    "msg": f"Playlist '{data['name']}' already exists.",
                    "field": "rename-playlist-name",
                    "user_id": str(user_id)
                }

        await func.update_user(user_id, {"$set": {f'playlist.{playlist_id}.name': name}})
        return {
            "op": "updatePlaylist",
            "status": "renamed",
            "name": name,
            "playlist_id": playlist_id,
            "msg": f"You have renamed the playlist to '{name}'.",
            "field": "rename-playlist-name",
            "user_id": str(user_id)
        }
    
    elif _type == "addTrack":
        track_id = data.get("track_id")
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
            "playlist_id": playlist_id,
            "track_id": track_id,
            "msg": f"Added {decoded_track.title} into '{playlist['name']}' playlist.",
            "user_id": str(user_id)
        }
        
    elif _type == "removeTrack":
        track_id, track_position = data.get("track_id"), data.get("track_position", 0)
        if not track_id:
            return error_msg("No track ID could be located.", user_id=user_id, level='error')
        
        playlist = await _getPlaylist(user_id, playlist_id)
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
            "playlist_id": playlist_id,
            "track_position": track_position,
            "track_id": track_id,
            "msg": f"Removed '{decoded_track['title']}' from '{playlist['name']}' playlist.",
            "user_id": str(user_id)
        }

methods: Dict[str, Union[SystemMethod, PlayerMethod]] = {
    "initBot": SystemMethod(initBot, credit=0),
    "initUser": SystemMethod(initUser, credit=0),
    "getRecommendation": SystemMethod(getRecommendation, credit=4),
    "closeConnection": PlayerMethod(closeConnection, credit=0),
    "initPlayer": PlayerMethod(initPlayer),
    "skipTo": PlayerMethod(skipTo),
    "backTo": PlayerMethod(backTo),
    "moveTrack": PlayerMethod(moveTrack),
    "addTracks": PlayerMethod(addTracks, auto_connect=True),
    "getTracks": PlayerMethod(getTracks, auto_connect=True),
    "shuffleTrack": PlayerMethod(shuffleTrack),
    "repeatTrack": PlayerMethod(repeatTrack),
    "removeTrack": PlayerMethod(removeTrack),
    "updatePause": PlayerMethod(updatePause),
    "updatePosition": PlayerMethod(updatePosition),
    "toggleAutoplay": PlayerMethod(toggleAutoplay),
    "getPlaylist": SystemMethod(getPlaylist),
    "updatePlaylist": SystemMethod(updatePlaylist)
}

async def process_methods(ipc_client, bot: commands.Bot, data: Dict) -> None:
    op: str = data.get("op", "")
    method = methods.get(op)
    if not method or not (user_id := data.get("user_id")):
        return

    user_id = int(user_id)
    if user_id not in RATELIMIT_COUNTER or (time.time() - RATELIMIT_COUNTER[user_id]["time"]) >= 300:
        RATELIMIT_COUNTER[user_id] = {"time": time.time(), "count": 0}
    
    else:
        if RATELIMIT_COUNTER[user_id]["count"] >= 200:
            return await ipc_client.send({"op": "rateLimited", "user_id": str(user_id)})
        RATELIMIT_COUNTER[user_id]["count"] += method.credit

    try:
        env: Dict = {"bot": bot, "data": data}
        args: List = []
        
        params = method.params
        if not (type(method) == SystemMethod):
            if guild_id := data.get("guild_id"):
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

                if player.channel.id != member.voice.channel.id:
                    return
                
                env["player"] = player
        
        for param in params:
            args.append(env.get(param))
            
        if resp := await method.function(*args):
            await ipc_client.send(resp)

    except Exception as e:
        print(traceback.print_exc())
        payload = {
            "op": "errorMsg",
            "level": "error",
            "msg": str(e),
            "user_id": str(user_id)
        }
        await ipc_client.send(payload)