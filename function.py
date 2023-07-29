import discord
import json
import aiohttp
import os

from discord.ext import commands
from datetime import datetime
from time import strptime
from io import BytesIO
from pymongo import MongoClient
from typing import Optional, Union
from addons import Settings, TOKENS

root_dir = os.path.dirname(os.path.abspath(__file__))

if not os.path.exists(os.path.join(root_dir, "settings.json")):
    raise Exception("Settings file not set!")

#-------------- API Clients --------------
tokens: TOKENS = TOKENS();

if not (tokens.mongodb_name and tokens.mongodb_url):
    raise Exception("MONGODB_NAME and MONGODB_URL can't not be empty in .env")

try:
    mongodb = MongoClient(host=tokens.mongodb_url, serverSelectionTimeoutMS=5000)
    mongodb.server_info()
    if tokens.mongodb_name not in mongodb.list_database_names():
        raise Exception(f"{tokens.mongodb_name} does not exist in your mongoDB!")
    print("Successfully connected to MongoDB!")

except Exception as e:
    raise Exception("Not able to connect MongoDB! Reason:", e)

collection = mongodb[tokens.mongodb_name]['Settings']
Playlist = mongodb[tokens.mongodb_name]['Playlist']

#--------------- Cache Var ---------------
settings: Settings
error_log = {} #Stores error that not a Voicelink Exception
langs = {} #Stores all the languages in ./langs
guild_settings = {} #Cache guild language
local_langs = {} #Stores all the localization languages in ./local_langs 
playlist_name = {} #Cache the user's playlist name

#-------------- Vocard Functions --------------
def get_settings(guild_id:int) -> dict:
    settings = guild_settings.get(guild_id, None)
    if not settings:
        settings = collection.find_one({"_id":guild_id})
        if not settings:
            collection.insert_one({"_id":guild_id})
            settings = {}
        guild_settings[guild_id] = settings
    return settings

def update_settings(guild_id:int, data: dict, mode="Set") -> None:
    settings = get_settings(guild_id)
    if mode == "Set":
        for key, value in data.items():
            if settings.get(key) != value:
                guild_settings[guild_id][key] = value
        collection.update_one({"_id":guild_id}, {"$set":data})
    elif mode == "Delete":
        for key, value in data.items():
            if settings.get(key) != value:
                del guild_settings[guild_id][key]
        collection.update_one({"_id":guild_id}, {"$unset":data})
    return

def open_json(path: str) -> dict:
    try:
        with open(os.path.join(root_dir, path), encoding="utf8") as json_file:
            return json.load(json_file)
    except:
        return {}

def update_json(path: str, new_data: dict) -> None:
    data = open_json(path)
    if not data:
        return
    
    data.update(new_data)

    with open(os.path.join(root_dir, path), "w") as json_file:
        json.dump(data, json_file, indent=4)

def get_lang(guild_id:int, key:str) -> str:
    lang = get_settings(guild_id).get("lang", "EN")
    if lang in langs and not langs[lang]:
        langs[lang] = open_json(os.path.join("langs", f"{lang}.json"))

    return langs.get(lang, {}).get(key, "Language pack not found!")

def init() -> None:
    global settings

    json = open_json("settings.json")
    if json is not None:
        settings = Settings(json)

def langs_setup() -> None:
    for language in os.listdir(os.path.join(root_dir, "langs")):
        if language.endswith('.json'):
            langs[language[:-5]] = {}
    
    for language in os.listdir(os.path.join(root_dir, "local_langs")):
        if language.endswith('.json'):
            local_langs[language[:-5]] = open_json(os.path.join("local_langs", language))

    return

def time(millis:int) -> str:
    seconds=(millis/1000)%60
    minutes=(millis/(1000*60))%60
    hours=(millis/(1000*60*60))%24
    if hours > 1:
        return "%02d:%02d:%02d" % (hours, minutes, seconds)
    else:
        return "%02d:%02d" % (minutes, seconds)

def formatTime(number:str) -> Optional[int]:
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
    return settings.emoji_source_raw.get(emoji.lower(), "🔗")

def gen_report() -> Optional[discord.File]:
    if error_log:
        errorText = ""
        for guild_id, error in error_log.items():
            errorText += f"Guild ID: {guild_id}\n" + "-" * 30 + "\n"
            for index, (key, value) in enumerate(error.items() , start=1):
                errorText += f"Error No: {index}, Time: {datetime.fromtimestamp(key)}\n" + value + "-" * 30 + "\n\n"

        buffer = BytesIO(errorText.encode('utf-8'))
        file = discord.File(buffer, filename='report.txt')
        buffer.close()

        return file        
    return None

def cooldown_check(ctx: commands.Context) -> Optional[commands.Cooldown]:
    if ctx.author.id in settings.bot_access_user:
        return None
    cooldown = settings.cooldowns_settings.get(f"{ctx.command.parent.qualified_name} {ctx.command.name}" if ctx.command.parent else ctx.command.name)
    if not cooldown:
        return None
    return commands.Cooldown(cooldown[0], cooldown[1])

def get_aliases(name: str) -> list:
    return settings.aliases_settings.get(name, [])

async def requests_api(url: str) -> dict:
    async with aiohttp.ClientSession() as session:
        resp = await session.get(url)
        if resp.status != 200:
            return False

        return await resp.json(encoding="utf-8")

async def create_account(ctx: Union[commands.Context, discord.Interaction]) -> None:
    author = ctx.author if isinstance(ctx, commands.Context) else ctx.user
    if not author:
        return 
    from views import CreateView
    view = CreateView()
    embed=discord.Embed(title="Do you want to create an account on Vocard?", color=settings.embed_color)
    embed.description = f"> Plan: `Default` | `5` Playlist | `500` tracks in each playlist."
    embed.add_field(name="Terms of Service:", value="‌    ➥ We assure you that all your data on Vocard will not be disclosed to any third party\n"
                                                    "‌    ➥ We will not perform any data analysis on your data\n"
                                                    "‌    ➥ You have the right to immediately stop the services we offer to you\n"
                                                    "‌    ➥ Please do not abuse our services, such as affecting other users\n", inline=False)
    if isinstance(ctx, commands.Context):
        message = await ctx.reply(embed=embed, view=view, ephemeral=True)
    else:
        message = await ctx.response.send_message(embed=embed, view=view, ephemeral=True)
        
    view.response = message
    await view.wait()
    if view.value:
        try:
            Playlist.insert_one({'_id':author.id, 'playlist': {'200':{'tracks':[],'perms':{ 'read': [], 'write':[], 'remove': []},'name':'Favourite', 'type':'playlist' }},'inbox':[] })
        except:
            pass
            
async def get_playlist(userid:int, dType:str=None, dId:str=None) -> dict:
    user = Playlist.find_one({"_id":userid}, {"_id": 0})
    if not user:
        return None
    if dType:
        if dId and dType == "playlist":
            return user[dType][dId] if dId in user[dType] else None
        return user[dType]
    return user

async def update_playlist(userid:int, data:dict=None, push=False, pull=False, mode=True) -> None:
    if mode is True:
        if push:
            return Playlist.update_one({"_id":userid}, {"$push": data})
        Playlist.update_one({"_id":userid}, {"$set": data})
    else:
        if pull:
            return Playlist.update_one({"_id":userid}, {"$pull": data})
        Playlist.update_one({"_id":userid}, {"$unset": data})
    return

async def update_inbox(userid:int, data:dict) -> None:
    return Playlist.update_one({"_id":userid}, {"$push":{'inbox':data}})

async def checkroles(userid:int):
    rank, max_p, max_t = 'Normal', 5, 500

    return rank, max_p, max_t