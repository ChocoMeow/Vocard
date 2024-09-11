import discord
import sys
import os
import aiohttp
import update
import logging
import function as func

from discord.ext import commands
from ipc import IPCClient
from motor.motor_asyncio import AsyncIOMotorClient
from logging.handlers import TimedRotatingFileHandler
from voicelink import VoicelinkException
from addons import Settings

class Translator(discord.app_commands.Translator):
    async def load(self):
        func.logger.info("Loaded Translator")

    async def unload(self):
        func.logger.info("Unload Translator")

    async def translate(self, string: discord.app_commands.locale_str, locale: discord.Locale, context: discord.app_commands.TranslationContext):
        if str(locale) in func.LOCAL_LANGS:
            return func.LOCAL_LANGS[str(locale)].get(string.message, None)
        return None

class Vocard(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.ipc: IPCClient

    async def on_message(self, message: discord.Message, /) -> None:
        if message.author.bot or not message.guild:
            return False

        if self.user.id in message.raw_mentions and not message.mention_everyone:
            prefix = await self.command_prefix(self, message)
            if not prefix:
                return await message.channel.send("I don't have a bot prefix set.")
            await message.channel.send(f"My prefix is `{prefix}`")

        await self.process_commands(message)

    async def connect_db(self) -> None:
        if not ((db_name := func.settings.mongodb_name) and (db_url := func.settings.mongodb_url)):
            raise Exception("MONGODB_NAME and MONGODB_URL can't not be empty in settings.json")

        try:
            func.MONGO_DB = AsyncIOMotorClient(host=db_url)
            await func.MONGO_DB.server_info()
            func.logger.info(f"Successfully connected to [{db_name}] MongoDB!")

        except Exception as e:
            func.logger.error("Not able to connect MongoDB! Reason:", exc_info=e)
            exit()
        
        func.SETTINGS_DB = func.MONGO_DB[db_name]["Settings"]
        func.USERS_DB = func.MONGO_DB[db_name]["Users"]

    async def setup_hook(self) -> None:
        func.langs_setup()
        
        # Connecting to MongoDB
        await self.connect_db()

        # Loading all the module in `cogs` folder
        for module in os.listdir(func.ROOT_DIR + '/cogs'):
            if module.endswith('.py'):
                try:
                    await self.load_extension(f"cogs.{module[:-3]}")
                    func.logger.info(f"Loaded {module[:-3]}")
                except Exception as e:
                    func.logger.error(f"Something went wrong while loading {module[:-3]} cog.", exc_info=e)

        self.ipc = IPCClient(self, **func.settings.ipc_client)
        if func.settings.ipc_client.get("enable", False):
            try:
                await self.ipc.connect()
            except Exception as e:
                func.logger.error(f"Cannot connected to dashboard! - Reason: {e}")

        if not func.settings.version or func.settings.version != update.__version__:
            func.update_json("settings.json", new_data={"version": update.__version__})

            await self.tree.set_translator(Translator())
            await self.tree.sync()

    async def on_ready(self):
        func.logger.info("------------------")
        func.logger.info(f"Logging As {self.user}")
        func.logger.info(f"Bot ID: {self.user.id}")
        func.logger.info("------------------")
        func.logger.info(f"Discord Version: {discord.__version__}")
        func.logger.info(f"Python Version: {sys.version}")
        func.logger.info("------------------")

        func.settings.client_id = self.user.id
        func.LOCAL_LANGS.clear()

    async def on_command_error(self, ctx: commands.Context, exception, /) -> None:
        error = getattr(exception, 'original', exception)
        if ctx.interaction:
            error = getattr(error, 'original', error)
            
        if isinstance(error, (commands.CommandNotFound, aiohttp.client_exceptions.ClientOSError, discord.errors.NotFound)):
            return

        elif isinstance(error, (commands.CommandOnCooldown, commands.MissingPermissions, commands.RangeError, commands.BadArgument)):
            pass

        elif isinstance(error, (commands.MissingRequiredArgument, commands.MissingRequiredAttachment)):
            command = f"{ctx.prefix}" + (f"{ctx.command.parent.qualified_name} " if ctx.command.parent else "") + f"{ctx.command.name} {ctx.command.signature}"
            position = command.find(f"<{ctx.current_parameter.name}>") + 1
            description = f"**Correct Usage:**\n```{command}\n" + " " * position + "^" * len(ctx.current_parameter.name) + "```\n"
            if ctx.command.aliases:
                description += f"**Aliases:**\n`{', '.join([f'{ctx.prefix}{alias}' for alias in ctx.command.aliases])}`\n\n"
            description += f"**Description:**\n{ctx.command.help}\n\u200b"

            embed = discord.Embed(description=description, color=func.settings.embed_color)
            embed.set_footer(icon_url=ctx.me.display_avatar.url, text=f"More Help: {func.settings.invite_link}")
            return await ctx.reply(embed=embed)

        elif not issubclass(error.__class__, VoicelinkException):
            error = await func.get_lang(ctx.guild.id, "unknownException") + func.settings.invite_link
            func.logger.error(f"An unexpected error occurred in the {ctx.command.name} command on the {ctx.guild.name}({ctx.guild.id}).", exc_info=exception)
            
        try:
            return await ctx.reply(error, ephemeral=True)
        except:
            pass

class CommandCheck(discord.app_commands.CommandTree):
    async def interaction_check(self, interaction: discord.Interaction, /) -> bool:
        if not interaction.guild:
            await interaction.response.send_message("This command can only be used in guilds!")
            return False

        return True

async def get_prefix(bot, message: discord.Message):
    settings = await func.get_settings(message.guild.id)
    return settings.get("prefix", func.settings.bot_prefix)

# Loading settings and logger
func.settings = Settings(func.open_json("settings.json"))

LOG_SETTINGS = func.settings.logging
if (LOG_FILE := LOG_SETTINGS.get("file", {})).get("enable", True):
    log_path = os.path.abspath(LOG_FILE.get("path", "./logs"))
    if not os.path.exists(log_path):
        os.makedirs(log_path)

    file_handler = TimedRotatingFileHandler(filename=f'{log_path}/vocard.log', encoding="utf-8", backupCount=LOG_SETTINGS.get("max-history", 30), when="d")
    file_handler.namer = lambda name: name.replace(".log", "") + ".log"
    file_handler.setFormatter(logging.Formatter('{asctime} [{levelname:<8}] {name}: {message}', '%Y-%m-%d %H:%M:%S', style='{'))

    for log_name, log_level in LOG_SETTINGS.get("level", {}).items():
        _logger = logging.getLogger(log_name)
        _logger.setLevel(log_level)
        
    logging.getLogger().addHandler(file_handler)

# Setup the bot object
intents = discord.Intents.default()
intents.message_content = True if func.settings.bot_prefix else False
intents.members = func.settings.ipc_client.get("enable", False)
intents.voice_states = True

bot = Vocard(
    command_prefix=get_prefix,
    help_command=None,
    tree_cls=CommandCheck,
    chunk_guilds_at_startup=False,
    activity=discord.Activity(type=discord.ActivityType.listening, name="Starting..."),
    case_insensitive=True,
    intents=intents
)

if __name__ == "__main__":
    update.check_version(with_msg=True)
    bot.run(func.settings.token, root_logger=True)