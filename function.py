import discord, json, os, copy, logging

from discord.ext import commands
from time import strptime
from addons import Settings

from typing import (
    Optional,
    Union,
    Dict,
    Any
)

from motor.motor_asyncio import (
    AsyncIOMotorClient,
    AsyncIOMotorCollection,
)

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))

if not os.path.exists(os.path.join(ROOT_DIR, "settings.json")):
    raise Exception("Settings file not set!")

#--------------- Cache Var ---------------
settings: Settings
logger: logging.Logger = logging.getLogger("vocard")

MONGO_DB: AsyncIOMotorClient
SETTINGS_DB: AsyncIOMotorCollection
USERS_DB: AsyncIOMotorCollection

LANGS: dict[str, dict[str, str]] = {} #Stores all the languages in ./langs
LOCAL_LANGS: dict[str, dict[str, str]] = {} #Stores all the localization languages in ./local_langs
SETTINGS_BUFFER: dict[int, dict[str, Any]] = {} #Cache guild language
USERS_BUFFER: dict[str, dict] = {}

USER_BASE: dict[str, Any] = {
    'playlist': {
        '200': {
            'tracks':[],
            'perms': {'read': [], 'write':[], 'remove': []},
            'name':'Favourite',
            'type':'playlist'
        }
    },
    'history': [],
    'inbox':[]
}

ALLOWED_MENTIONS = discord.AllowedMentions().none()

#-------------- Vocard Functions --------------
def open_json(path: str) -> dict:
    try:
        with open(os.path.join(ROOT_DIR, path), encoding="utf8") as json_file:
            return json.load(json_file)
    except:
        return {}

def update_json(path: str, new_data: dict) -> None:
    data = open_json(path)
    if not data:
        return
    
    data.update(new_data)

    with open(os.path.join(ROOT_DIR, path), "w") as json_file:
        json.dump(data, json_file, indent=4)

def langs_setup() -> None:
    for language in os.listdir(os.path.join(ROOT_DIR, "langs")):
        if language.endswith('.json'):
            LANGS[language[:-5]] = {}
    
    for language in os.listdir(os.path.join(ROOT_DIR, "local_langs")):
        if language.endswith('.json'):
            LOCAL_LANGS[language[:-5]] = open_json(os.path.join("local_langs", language))

    return

def time(millis: int) -> str:
    seconds = (millis // 1000) % 60
    minutes = (millis // (1000 * 60)) % 60
    hours = (millis // (1000 * 60 * 60)) % 24
    days = millis // (1000 * 60 * 60 * 24)

    if days > 0:
        return "%d days, %02d:%02d:%02d" % (days, hours, minutes, seconds)
    elif hours > 0:
        return "%d:%02d:%02d" % (hours, minutes, seconds)
    else:
        return "%02d:%02d" % (minutes, seconds)

def format_time(number:str) -> int:
    try:
        try:
            num = strptime(number, '%M:%S')
        except ValueError:
            try:
                num = strptime(number, '%S')
            except ValueError:
                num = strptime(number, '%H:%M:%S')
    except:
        return 0
    
    return (int(num.tm_hour) * 3600 + int(num.tm_min) * 60 + int(num.tm_sec)) * 1000

def get_source(source: str, type: str) -> str:
    source_settings: dict = settings.sources_settings.get(source.lower(), {})
    return source_settings.get(type, ("🔗" if type == "emoji" else settings.embed_color))

def cooldown_check(ctx: commands.Context) -> Optional[commands.Cooldown]:
    if ctx.author.id in settings.bot_access_user:
        return None
    cooldown = settings.cooldowns_settings.get(f"{ctx.command.parent.qualified_name} {ctx.command.name}" if ctx.command.parent else ctx.command.name)
    if not cooldown:
        return None
    return commands.Cooldown(cooldown[0], cooldown[1])

def get_aliases(name: str) -> list:
    return settings.aliases_settings.get(name, [])

def check_roles() -> tuple[str, int, int]:
    return 'Normal', 5, 500

def truncate_string(text: str, length: int = 40) -> str:
    return text[:length - 3] + "..." if len(text) > length else text
    
def get_lang_non_async(guild_id: int, *keys) -> Union[list[str], str]:
    settings = SETTINGS_BUFFER.get(guild_id, {})
    lang = settings.get("lang", "EN")
    if lang in LANGS and not LANGS[lang]:
        LANGS[lang] = open_json(os.path.join("langs", f"{lang}.json"))

    if len(keys) == 1:
        return LANGS.get(lang, {}).get(keys[0], "Language pack not found!")
    return [LANGS.get(lang, {}).get(key, "Language pack not found!") for key in keys]

def format_bytes(bytes: int, unit: bool = False):
    if bytes <= 1_000_000_000:
        return f"{bytes / (1024 ** 2):.1f}" + ("MB" if unit else "")
    
    else:
        return f"{bytes / (1024 ** 3):.1f}" + ("GB" if unit else "")
    
async def get_lang(guild_id:int, *keys) -> Union[list[str], str]:
    settings = await get_settings(guild_id)
    lang = settings.get("lang", "EN")
    if lang in LANGS and not LANGS[lang]:
        LANGS[lang] = open_json(os.path.join("langs", f"{lang}.json"))

    if len(keys) == 1:
        return LANGS.get(lang, {}).get(keys[0], "Language pack not found!")
    return [LANGS.get(lang, {}).get(key, "Language pack not found!") for key in keys]

async def send(ctx: Union[commands.Context, discord.Interaction], key: str, *params, delete_after: float = None, ephemeral: bool = False) -> Optional[discord.Message]:
    text = await get_lang(ctx.guild.id, key)
    text = text.format(*params)

    if isinstance(ctx, commands.Context):
        send_func = ctx.send
    else:
        if not ctx.response.is_done():
            send_func = ctx.response.send_message
            
        else:
            return await ctx.followup.send(text, ephemeral=ephemeral, allowed_mentions=ALLOWED_MENTIONS)
        
    return await send_func(text, delete_after=delete_after, ephemeral=ephemeral, allowed_mentions=ALLOWED_MENTIONS)

async def update_db(db: AsyncIOMotorCollection, tempStore: dict, filter: dict, data: dict) -> bool:
    for mode, action in data.items():
        for key, value in action.items():
            cursors = key.split(".")

            nested_data = tempStore
            for c in cursors[:-1]:
                nested_data = nested_data.setdefault(c, {})

            if mode == "$set":
                try:
                    nested_data[cursors[-1]] = value
                except TypeError:
                    nested_data[int(cursors[-1])] = value

            elif mode == "$unset":
                nested_data.pop(cursors[-1], None)

            elif mode == "$inc":
                nested_data[cursors[-1]] = nested_data.get(cursors[-1], 0) + value

            elif mode == "$push":
                if isinstance(value, dict) and "$each" in value:
                    nested_data.setdefault(cursors[-1], []).extend(value["$each"][value.get("$slice", len(value["$each"])):])
                else:
                    nested_data.setdefault(cursors[-1], []).extend([value])
                    
            elif mode == "$push":
                if isinstance(value, dict) and "$each" in value:
                    nested_data.setdefault(cursors[-1], []).extend(value["$each"])
                    nested_data[cursors[-1]] = nested_data[cursors[-1]][value.get("$slice", len(value["$each"])):]
                else:
                    nested_data.setdefault(cursors[-1], []).extend([value])

            elif mode == "$pull":
                if cursors[-1] in nested_data:
                    value = value.get("$in", []) if isinstance(value, dict) else [value]
                    nested_data[cursors[-1]] = [item for item in nested_data[cursors[-1]] if item not in value]
                    
            else:
                return False

    result = await db.update_one(filter, data)
    return result.modified_count > 0

async def get_settings(guild_id:int) -> dict[str, Any]:
    settings = SETTINGS_BUFFER.get(guild_id, None)
    if not settings:
        settings = await SETTINGS_DB.find_one({"_id": guild_id})
        if not settings:
            await SETTINGS_DB.insert_one({"_id": guild_id})
            
        settings = SETTINGS_BUFFER[guild_id] = settings or {}
    return settings

async def update_settings(guild_id: int, data: dict[str, dict[str, Any]]) -> bool:
    settings = await get_settings(guild_id)
    return await update_db(SETTINGS_DB, settings, {"_id": guild_id}, data)
            
async def get_user(user_id: int, d_type: Optional[str] = None, need_copy: bool = True) -> Dict[str, Any]:
    user = USERS_BUFFER.get(user_id)
    if not user:
        user = await USERS_DB.find_one({"_id": user_id})
        if not user:
            user = {"_id": user_id, **USER_BASE}
            await USERS_DB.insert_one(user)
    
        USERS_BUFFER[user_id] = user
        
    if d_type:
        user = user.setdefault(d_type, copy.deepcopy(USER_BASE.get(d_type)))
            
    return copy.deepcopy(user) if need_copy else user

async def update_user(user_id:int, data:dict) -> bool:
    playlist = await get_user(user_id, need_copy=False)
    return await update_db(USERS_DB, playlist, {"_id": user_id}, data)