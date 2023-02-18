import discord
import json
import aiohttp
import os

from dotenv import load_dotenv
from random import choice
from time import strptime
from pymongo import MongoClient

if not os.path.exists("./settings.json"):
    print("Error: Settings file not set!")
    exit()

#-------------- API Clients --------------
load_dotenv() #Load .env settings
MONGODB_NAME = os.getenv('MONGODB_NAME')
MONGODB_URL = os.getenv('MONGODB_URL')
if not (MONGODB_NAME and MONGODB_URL):
    print("MONGODB_NAME and MONGODB_URL can't not be empty in .env")
    exit()

youtube_api_key = os.getenv('YOUTUBE_API_KEY')
mongodb = MongoClient(MONGODB_URL)
collection = mongodb[MONGODB_NAME]['Settings']
Playlist = mongodb[MONGODB_NAME]['Playlist']

#--------------- Cache Var ---------------
invite_link = "https://discord.gg/wRCgB7vBQv" #Template of invite link
embed_color = None
report_channel_id = int(channel_id) if (channel_id := os.getenv("BUG_REPORT_CHANNEL_ID")) else 0
emoji_source_raw = {} #Stores all source emoji for track
error_log = {} #Stores error that not a Voicelink Exception
bot_access_user = [] #Stores bot access user id
langs = {} #Stores all the languages in ./langs
lang_guilds = {} #Cache guild language
local_langs = {} #Stores all the localization languages in ./local_langs 
playlist_name = {} #Cache the user's playlist name

bot_prefix = "?" #The default bot prefix
#----------------- Nodes -----------------
nodes = {}

#-------------- Vocard Functions --------------
def get_settings(guildid:int):
    settings = collection.find_one({"_id":guildid})
    if not settings:
        collection.insert_one({"_id":guildid})
        return {}
    return settings

def update_settings(guildid:int, data, mode="Set"):
    if mode == "Set":
        collection.update_one({"_id":guildid}, {"$set":data})
    elif mode == "Delete":
        collection.update_one({"_id":guildid}, {"$unset":data})
    elif mode == "Add":
        collection.update_one({"_id":guildid}, {"$push":data})
    elif mode == "Remove":
        collection.update_one({"_id":guildid}, {"$pull":data})
    return 

def langs_setup():
    for language in os.listdir('./langs'):
        if language.endswith('.json'):
            with open(f'./langs/{language}', encoding="utf8") as json_file:
                lang = json.load(json_file)

            langs[language[:-5]] = lang
    
    for language in os.listdir('./local_langs'):
        if language.endswith('.json'):
            with open(f'./local_langs/{language}', encoding="utf8") as json_file:
                lang = json.load(json_file)
        
            local_langs[language[:-5]] = lang
    return

def settings_setup():
    with open('./settings.json', encoding="utf8") as json_file:
        rawSettings = json.load(json_file)

    global nodes, embed_color, bot_access_user, emoji_source_raw
    nodes = rawSettings.get("nodes", {})
    embed_color = int(rawSettings.get("embed_color", "0xb3b3b3"), 16)
    bot_access_user = rawSettings.get("bot_access_user", [])
    emoji_source_raw = rawSettings.get("emoji_source_raw", {})

def get_lang(guildid:int, key:str):
    lang = lang_guilds.get(guildid)
    if not lang:
        settings = get_settings(guildid)
        lang = lang_guilds[guildid] = settings.get('lang', 'EN')
    
    return langs.get(lang, langs["EN"])[key]
    
async def requests_api(url: str):
    async with aiohttp.ClientSession() as session:
        resp = await session.get(url)
        if resp.status != 200:
            return False

        return await resp.json(encoding="utf-8")

async def create_account(interaction):
    if not interaction.user:
        return 
    from view import CreateView
    view = CreateView()
    embed=discord.Embed(title="Do you want to create an account on Vocard?", color=embed_color)
    embed.description = f"> Plan: `Default` | `1` Playlist | `20` tracks in each playlist\n> You are able to upgrade the plan by Type `-shop` on [Vocard support discord]({invite_link})."
    embed.add_field(name="Terms of Service:", value="‌    ➥ We assure you that all your data on Vocard will not be disclosed to any third party\n"
                                                    "‌    ➥ We will not perform any data analysis on your data\n"
                                                    "‌    ➥ You have the right to immediately stop the services we offer to you\n"
                                                    "‌    ➥ Please do not abuse our services, such as affecting other users\n"
                                                    "‌    ➥ Join our support server to get free extra custom playlist and extra 20 tracks per playlist\n", inline=False)
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    view.response = await interaction.original_response()
    await view.wait()
    if view.value:
        try:
            Playlist.insert_one({'_id':interaction.user.id, 'playlist': {'200':{'tracks':[],'perms':{ 'read': [], 'write':[], 'remove': []},'name':'Favourite', 'type':'playlist' }},'inbox':[] })
        except:
            pass
            
async def get_playlist(userid:int, dType:str=None, dId:str=None):
    user = Playlist.find_one({"_id":userid}, {"_id": 0})
    if not user:
        return None
    if dType:
        if dId and dType == "playlist":
            return user[dType][dId] if dId in user[dType] else None
        return user[dType]
    return user

async def update_playlist(userid:int, data:dict=None, push=False, pull=False, mode=True):
    if mode is True:
        if push:
            return Playlist.update_one({"_id":userid}, {"$push": data})
        Playlist.update_one({"_id":userid}, {"$set": data})
    else:
        if pull:
            return Playlist.update_one({"_id":userid}, {"$pull": data})
        Playlist.update_one({"_id":userid}, {"$unset": data})
    return

async def update_inbox(userid:int, data:dict):
    return Playlist.update_one({"_id":userid}, {"$push":{'inbox':data}})

async def checkroles(userid:int):
    rank, max_p, max_t = 'Normal', 5, 500

    return rank, max_p, max_t

async def similar_track(player):
    trackids = [ track.identifier for track in player.queue.history(incTrack=True) if track.source == 'youtube' ]
    randomTrack = choice(player.queue.history(incTrack=True)[-10:])
    tracks = []

    if randomTrack.spotify:
        tracks = await player.spotifyRelatedTrack(seed_artists=randomTrack.artistId[0], seed_tracks=randomTrack.track_id)
    else:
        if randomTrack.source != 'youtube':
            return False

        if not youtube_api_key:
            return False
        
        request_url = "https://youtube.googleapis.com/youtube/v3/search?part={part}&relatedToVideoId={videoId}&type={type}&videoCategoryId={videoCategoryId}&key={key}".format(
            part="snippet",
            videoId=randomTrack.identifier,
            type="video",
            videoCategoryId="10",
            key=youtube_api_key
        )

        try:
            data = await requests_api(request_url)
            if not data:
                return False

            for item in data['items']:
                if 'snippet' not in item:
                    continue
                if item['id']['videoId'] not in trackids:
                    tracks = await player.get_tracks(f"https://www.youtube.com/watch?v={item['id']['videoId']}", requester=player._bot.user)
                    break
        except:
            return False

    if tracks:
        for track in tracks:
            await player.queue.put(track)
        return True

    return False

def time(millis:int):
    seconds=(millis/1000)%60
    minutes=(millis/(1000*60))%60
    hours=(millis/(1000*60*60))%24
    if hours > 1:
        return "%02d:%02d:%02d" % (hours, minutes, seconds)
    else:
        return "%02d:%02d" % (minutes, seconds)

def formatTime(number:str):
    try:
        try:
            num = strptime(number, '%M:%S')
        except ValueError:
            try:
                num = strptime(number, '%S')
            except ValueError:
                num = strptime(number, '%H:%M:%S')
    except:
        return None
    
    return (int(num.tm_hour) * 3600 + int(num.tm_min) * 60 + int(num.tm_sec)) * 1000

def emoji_source(emoji:str):
    return emoji_source_raw.get(emoji.lower(), "🔗");

