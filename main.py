import discord
import sys, os, traceback, aiohttp
import update

from function import (
    langs_setup,
    settings_setup,
    local_langs, 
    get_lang, 
    invite_link, 
    error_log
)
from discord.ext import commands
from dotenv import load_dotenv
from googletrans import Translator
from datetime import datetime
from voicelink import VoicelinkException

translator = Translator()

load_dotenv()

class Translator(discord.app_commands.Translator):
    async def load(self):
        print("Loaded Translator")
    
    async def unload(self):
        print("Unload Translator")
    
    async def translate(self, string: discord.app_commands.locale_str, locale: discord.Locale, context: discord.app_commands.TranslationContext):
        if str(locale) in local_langs:
            text = local_langs[str(locale)].get(string.message, None)
            if not text:
                result = translator.translate(string.message, str(locale).lower())
                print(result.origin, ' -> ', result.text)
                return result.text
            return text
        return None

class Vocard(commands.Bot):

    async def on_message(self, message):
        pass

    async def setup_hook(self):
        langs_setup()
        settings_setup()
        for module in os.listdir('./cogs'):
            if module.endswith('.py'):
                try:
                    await self.load_extension(f"cogs.{module[:-3]}")
                    print(f"Loaded {module[:-3]}")
                except Exception as e:
                    print(traceback.format_exc())

        # await bot.tree.set_translator(Translator())
        # await bot.tree.sync()

    async def on_ready(self):
        print("------------------")
        print(f"Logging As {self.user}")
        print(f"Bot ID: {self.user.id}")
        print("------------------")
        print(f"Discord Version: {discord.__version__}")
        print(f"Python Version: {sys.version}")
        print("------------------")

intents = discord.Intents.default()
intents.members = True
member_cache = discord.MemberCacheFlags(
    voice=True,
    joined=False
)

bot = Vocard(command_prefix="?",
             help_command=None,
             chunk_guilds_at_startup = False,
             member_cache_flags=member_cache,
             activity=discord.Activity(type=discord.ActivityType.listening,name="/help"), 
             intents=intents)

@bot.tree.error
async def app_command_error(interaction: discord.Interaction, error):
    error = getattr(error, 'original', error)
    if isinstance(error, (discord.errors.NotFound, aiohttp.client_exceptions.ClientOSError)):
        return
    elif isinstance(error, (discord.app_commands.CommandOnCooldown, discord.app_commands.errors.MissingPermissions)):
        pass
    elif not issubclass(error.__class__, VoicelinkException):
        error = get_lang(interaction.guild_id, "unknownException") + invite_link
        if (guildId := interaction.guild_id) not in error_log:
            error_log[guildId] = {}
        error_log[guildId][round(datetime.timestamp(datetime.now()))] = str(traceback.format_exc())
    try:
        if interaction.response.is_done():
            return await interaction.followup.send(error, ephemeral=True)

        return await interaction.response.send_message(error, ephemeral=True)
    except:
        pass

update.checkVersion(withMsg = True)
bot.run(os.getenv("TOKEN"), log_handler=None)