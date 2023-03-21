import json
import voicelink

from discord import Member
from discord.ext import commands

def missingPermission(user_id:int):
    payload = {"op": "missingPermission", "msg": "Only the DJ or admins may use this funciton!"}
    payload["user_id"] = user_id
    return payload

async def initPlayer(player, member: Member, data: dict):
    return {
        "op": "initPlayer",
        "guild_id": player.guild.id,
        "user_id": data.get("user_id"),
        "users": [{
            "user_id": member.id,
            "avatar_url": member.avatar.url,
            "name": member.name
        } for member in player.channel.members ],
        "tracks": [ track.toDict() for track in player.queue._queue ],
        "current_queue_position": player.queue._position if player.is_playing else player.queue._position + 1,
        "current_position": 0 or player.position if player.is_playing else 0,
        "is_playing": player.is_playing,
        "is_paused": player.is_paused
    }

async def skipTo(player, member: Member, data: dict):
    if not player.is_privileged(member):
        return missingPermission(member.id)
    
    index = data.get("index", 1)
    if index > 1:
        player.queue.skipto(index)

    if player.queue._repeat == 1:
        await player.set_repeat("off")
    await player.stop()

async def backTo(player, member: Member, data: dict):
    if not player.is_privileged(member):
        return missingPermission(member.id)
    
    index = data.get("index", 1)
    if not player.is_playing:
        player.queue.backto(index)
        await player.do_next()
    else:
        player.queue.backto(index + 1)
        await player.stop()

async def moveTrack(player, member: Member, data: dict):
    if not player.is_privileged(member):
        return missingPermission(member.id)

    c = player.queue._position - 1
    position = data.get("position")
    new_position = data.get("newPosition")

    moveItem = player.queue._queue[position]
    player.queue._queue.remove(moveItem)
    player.queue._queue.insert(new_position, moveItem)
    return {
        "op": "moveTrack",
        "position": {
            "index": position - c,
            "track_id": moveItem.track_id
        },
        "newPosition": {
            "index": new_position - c
        },
        "guild_id": player.guild.id,
        "requester_id": member.id,
        "skip_users": [member.id]
    }

async def addTracks(player, member: Member, data: dict): 
    raw_tracks = data.get("tracks", [])
    tracks = [voicelink.Track(
                track_id=track["track_id"], 
                info=track["info"],
                requester=member
            ) for track in raw_tracks]

    await player.add_track(tracks)

    if not player.is_playing:
        await player.do_next()

async def getTracks(player, member: Member, data: dict):
    query = data.get("query", None)
    if query:
        payload = {"op": "getTracks", "user_id": member.id}
        tracks = await player.get_tracks(query, requester=member)
        if not tracks:
            return payload
        
        payload["tracks"] = [ track.toDict() for track in tracks ]
        return payload
    
async def shuffleTrack(player, member: Member, data: dict):
    if not player.is_privileged(member):
        return missingPermission(member.id)
    
    await player.shuffle(data.get("type", "queue"), member)

async def repeatTrack(player, member: Member, data: dict):
    if not player.is_privileged(member):
        return missingPermission(member.id)
    
    await player.set_repeat()

async def updatePause(player, member: Member, data: dict):
    if not player.is_privileged(member):
        return missingPermission(member.id)
    
    pause = data.get("pause", True)
    if pause:
        player.pause_votes.clear()
    else:
        player.resume_votes.clear()
    await player.set_pause(pause, member)

async def updatePosition(player, member: Member, data: dict):
    if not player.is_privileged(member):
        return missingPermission(member.id)
    
    position = data.get("position");
    await player.seek(position, member);

methods = {
    "initPlayer": initPlayer,
    "skipTo": skipTo,
    "backTo": backTo,
    "moveTrack": moveTrack,
    "addTracks": addTracks,
    "getTracks": getTracks,
    "shuffleTrack": shuffleTrack,
    "repeatTrack": repeatTrack,
    "updatePause": updatePause,
    "updatePosition": updatePosition,
}

async def process_methods(websocket, bot: commands.Bot, data: dict) -> None:
    method = methods.get(data.get("op", ""), None)
    if not method:
        return

    guild = None
    member = None
    guild_id = data.get("guild_id", None)
    user_id = data.get("user_id", None)
    if guild_id is None:
        user = bot.get_user(user_id)
        if not user:
            return
        
        for g in user.mutual_guilds:
            m = g.get_member(user.id)
            if m.voice and m.voice.channel:
                guild = g
                member = m

    else:
        guild = bot.get_guild(guild_id)
        member = guild.get_member(user_id)
    
    if not guild:
        return
    
    player = guild.voice_client
    if not player or not Member:
        return
    try:
        resp: dict = await method(player, member, data)
        if resp:
            await websocket.send(json.dumps(resp))
    except:
        return