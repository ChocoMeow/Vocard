import discord
import sys, os, traceback, aiohttp
import update
import function

from discord.ext import commands
from dotenv import load_dotenv
from datetime import datetime
from voicelink import VoicelinkException

load_dotenv()
function.settings_setup()

class Translator(discord.app_commands.Translator):
    async def load(self):
        print("Loaded Translator")
    
    async def unload(self):
        print("Unload Translator")
    
    async def translate(self, string: discord.app_commands.locale_str, locale: discord.Locale, context: discord.app_commands.TranslationContext):
        if str(locale) in local_langs:
            return local_langs[str(locale)].get(string.message, None)
        return None

class Vocard(commands.Bot):

    async def on_message(self, message: discord.Message, /) -> None:
        if message.author.bot or not message.guild:
            return False
        
        if self.user.mentioned_in(message) and not message.mention_everyone:
            await message.channel.send(f"My prefix is `{self.command_prefix}`")
        
        await self.process_commands(message)
    
    async def setup_hook(self):
        function.langs_setup()
        for module in os.listdir('./cogs'):
            if module.endswith('.py'):
                try:
                    await self.load_extension(f"cogs.{module[:-3]}")
                    print(f"Loaded {module[:-3]}")
                except Exception as e:
                    print(traceback.format_exc())

        await bot.tree.set_translator(Translator())
        await bot.tree.sync()

    async def on_ready(self):
        print("------------------")
        print(f"Logging As {self.user}")
        print(f"Bot ID: {self.user.id}")
        print("------------------")
        print(f"Discord Version: {discord.__version__}")
        print(f"Python Version: {sys.version}")
        print("------------------")

        
        elif isinstance(error, (commands.CommandOnCooldown, commands.MissingPermissions, commands.RangeError, commands.BadArgument)):
            pass

        elif isinstance(error, commands.MissingRequiredArgument):
            command = f" Correct Usage: {ctx.prefix}" + (f"{ctx.command.parent.qualified_name} " if ctx.command.parent else "") + f"{ctx.command.name} {ctx.command.signature}"
            position = command.find(f"<{ctx.current_parameter.name}>") + 1
            error = f"```css\n[You are missing argument!]\n{command}\n" + " " * position + "^" * len(ctx.current_parameter.name) + "```"
        
        elif not issubclass(error.__class__, VoicelinkException):
            error = function.get_lang(ctx.guild.id, "unknownException") + function.invite_link
            if (guildId := ctx.guild.id) not in function.error_log:
                function.error_log[guildId] = {}
            function.error_log[guildId][round(datetime.timestamp(datetime.now()))] = str(traceback.format_exc())
   
        try:
            return await ctx.reply(error, ephemeral=True)
        except:
            pass

class CommandCheck(discord.app_commands.CommandTree):
    
    async def interaction_check(self, interaction: discord.Interaction, /) -> bool:
        if not interaction.guild:
            await interaction.response.send_message("This command can only be used in guilds!")
            return False
    
        return await super().interaction_check(interaction)
    
intents = discord.Intents.default()
intents.members = True
intents.message_content = True if function.bot_prefix else False
member_cache = discord.MemberCacheFlags(
    voice=True,
    joined=False
)

bot = Vocard(command_prefix=function.bot_prefix,
             help_command=None,
             tree_cls=CommandCheck,
             chunk_guilds_at_startup = False,
             member_cache_flags=member_cache,
             activity=discord.Activity(type=discord.ActivityType.listening,name="/help"),
             case_insensitive = True,
             intents=intents)

@bot.tree.error
async def app_command_error(interaction: discord.Interaction, error):
    error = getattr(error, 'original', error)
    if isinstance(error, (discord.errors.NotFound, aiohttp.client_exceptions.ClientOSError)):
        return
    elif isinstance(error, (discord.app_commands.CommandOnCooldown, discord.app_commands.errors.MissingPermissions)):
        pass
    elif not issubclass(error.__class__, VoicelinkException):
        error = function.get_lang(interaction.guild_id, "unknownException") + function.invite_link
        if (guildId := interaction.guild_id) not in function.error_log:
            function.error_log[guildId] = {}
        function.error_log[guildId][round(datetime.timestamp(datetime.now()))] = str(traceback.format_exc())
    try:
        if interaction.response.is_done():
            return await interaction.followup.send(error, ephemeral=True)

        return await interaction.response.send_message(error, ephemeral=True)
    except:
        pass

update.checkVersion(withMsg = True)
bot.run(os.getenv("TOKEN"), log_handler=None)