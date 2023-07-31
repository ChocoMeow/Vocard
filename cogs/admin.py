import discord
import voicelink
import io
import contextlib
import textwrap
import traceback
import function as func

from typing import Tuple
from discord import app_commands
from discord.ext import commands
from function import (
    langs,
    update_settings,
    get_settings,
    get_lang,
    settings as sett,
    time as ctime,
    get_aliases,
    cooldown_check
)
from views import DebugModal, HelpView, EmbedBuilderView

class Admin(commands.Cog, name="settings"):
    def __init__(self, bot) -> None:
        self.bot = bot
        self.description = "This category is only available to admin permissions on the server."

    def get_settings(self, ctx: commands.Context) -> Tuple[voicelink.Player, dict]:
        player: voicelink.Player = ctx.guild.voice_client
        if not player:
            settings = get_settings(ctx.guild.id)
        else:
            settings = player.settings

        return player, settings
    
    @commands.hybrid_group(
        name="settings",
        aliases=get_aliases("settings"),
        invoke_without_command=True
    )
    async def settings(self, ctx: commands.Context):
        view = HelpView(self.bot, ctx.author)
        embed = view.build_embed(self.qualified_name)
        message = await ctx.send(embed=embed, view=view)
        view.response = message
    
    @settings.command(name="prefix", aliases=get_aliases("prefix"))
    @commands.has_permissions(manage_guild=True)
    @commands.dynamic_cooldown(cooldown_check, commands.BucketType.guild)
    async def prefix(self, ctx: commands.Context, prefix: str):
        "Change the default prefix for message commands."
        update_settings(ctx.guild.id, {"prefix": prefix})
        await ctx.send(get_lang(ctx.guild.id, "setPrefix").format(ctx.prefix, prefix))

    @settings.command(name="language", aliases=get_aliases("language"))
    @commands.has_permissions(manage_guild=True)
    @commands.dynamic_cooldown(cooldown_check, commands.BucketType.guild)
    async def language(self, ctx: commands.Context, language: str):
        "You can choose your preferred language, the bot message will change to the language you set."
        language = language.upper()
        if language not in langs:
            return await ctx.send(get_lang(ctx.guild.id, "languageNotFound"))

        player, settings = self.get_settings(ctx)
        if player:
            player.lang = language

        update_settings(ctx.guild.id, {'lang': language})
        await ctx.send(get_lang(ctx.guild.id, 'changedLanguage').format(language))

    @language.autocomplete('language')
    async def autocomplete_callback(self, interaction: discord.Interaction, current: str) -> list:
        if current:
            return [app_commands.Choice(name=lang, value=lang) for lang in langs.keys() if current.upper() in lang]
        return [app_commands.Choice(name=lang, value=lang) for lang in langs.keys()]

    @settings.command(name="dj", aliases=get_aliases("dj"))
    @commands.has_permissions(manage_guild=True)
    @commands.dynamic_cooldown(cooldown_check, commands.BucketType.guild)
    async def dj(self, ctx: commands.Context, role: discord.Role = None):
        "Set a DJ role or remove DJ role."
        player: voicelink.Player = ctx.guild.voice_client

        if not role:
            if player:
                player.settings.pop('dj', None)
            update_settings(ctx.guild.id, {'dj': ''}, mode="Unset")
        else:
            if player:
                player.settings['dj'] = role.id
            update_settings(ctx.guild.id, {'dj': role.id})

        await ctx.send(get_lang(ctx.guild.id, 'setDJ').format(f"<@&{role.id}>" if role else "None"), allowed_mentions=discord.AllowedMentions.none())

    @settings.command(name="queue", aliases=get_aliases("queue"))
    @app_commands.choices(mode=[
        app_commands.Choice(name="FairQueue", value="FairQueue"),
        app_commands.Choice(name="Queue", value="Queue")
    ])
    @commands.has_permissions(manage_guild=True)
    @commands.dynamic_cooldown(cooldown_check, commands.BucketType.guild)
    async def queue(self, ctx: commands.Context, mode: str):
        "Change to another type of queue mode."
        player, settings = self.get_settings(ctx)

        mode = "FairQueue" if mode.lower() == "fairqueue" else "Queue"
        settings["queueType"] = mode
        update_settings(ctx.guild.id, {"queueType": mode})
        await ctx.send(get_lang(ctx.guild.id, "setqueue").format(mode))

    @settings.command(name="247", aliases=get_aliases("247"))
    @commands.has_permissions(manage_guild=True)
    @commands.dynamic_cooldown(cooldown_check, commands.BucketType.guild)
    async def playforever(self, ctx: commands.Context):
        "Toggles 24/7 mode, which disables automatic inactivity-based disconnects."
        player, settings = self.get_settings(ctx)
        toggle = settings.get('24/7', False)
        settings['24/7'] = not toggle
        update_settings(ctx.guild.id, {'24/7': not toggle})
        toggle = get_lang(ctx.guild.id, "enabled" if not toggle else "disabled")
        await ctx.send(get_lang(ctx.guild.id, '247').format(toggle))

    @settings.command(name="bypassvote", aliases=get_aliases("bypassvote"))
    @commands.has_permissions(manage_guild=True)
    @commands.dynamic_cooldown(cooldown_check, commands.BucketType.guild)
    async def bypassvote(self, ctx: commands.Context):
        "Toggles voting system."
        player, settings = self.get_settings(ctx)
        toggle = settings.get('votedisable', True)
        settings['votedisable'] = not toggle
        update_settings(ctx.guild.id, {'votedisable': not toggle})
        toggle = get_lang(ctx.guild.id,
                          "enabled" if not toggle else "disabled")
        await ctx.send(get_lang(ctx.guild.id, 'bypassVote').format(toggle))

    @settings.command(name="view", aliases=get_aliases("view"))
    @commands.has_permissions(manage_guild=True)
    @commands.dynamic_cooldown(cooldown_check, commands.BucketType.guild)
    async def view(self, ctx: commands.Context):
        "Show all the bot settings in your server."
        player, settings = self.get_settings(ctx)
        embed = discord.Embed(color=sett.embed_color)
        embed.set_author(name=get_lang(ctx.guild.id, 'settingsMenu').format(ctx.guild.name), icon_url=self.bot.user.display_avatar.url)
        if ctx.guild.icon:
            embed.set_thumbnail(url=ctx.guild.icon.url)

        embed.add_field(name=get_lang(ctx.guild.id, 'settingsTitle'), value=get_lang(ctx.guild.id, 'settingsValue').format(
            settings.get('prefix', func.settings.bot_prefix) or "None",
            settings.get('lang', 'EN'),
            settings.get('controller', True),
            f"<@&{settings['dj']}>" if 'dj' in settings else '`None`',
            settings.get('votedisable', False),
            settings.get('24/7', False),
            settings.get('volume', 100),
            ctime(settings.get('playTime', 0) * 60 * 1000),
            inline=True)
        )
        embed.add_field(name=get_lang(ctx.guild.id, 'settingsTitle2'), value=get_lang(ctx.guild.id, 'settingsValue2').format(
            settings.get("queueType", "Queue"),
            func.settings.max_queue,
            settings.get("duplicateTrack", True)
        )
        )

        perms = ctx.guild.me.guild_permissions
        embed.add_field(name=get_lang(ctx.guild.id, 'settingsPermTitle'), value=get_lang(ctx.guild.id, 'settingsPermValue').format(
            '<a:Check:941206936651706378>' if perms.administrator else '<a:Cross:941206918255497237>',
            '<a:Check:941206936651706378>' if perms.manage_guild else '<a:Cross:941206918255497237>',
            '<a:Check:941206936651706378>' if perms.manage_channels else '<a:Cross:941206918255497237>',
            '<a:Check:941206936651706378>' if perms.manage_messages else '<a:Cross:941206918255497237>'), inline=False
        )
        await ctx.send(embed=embed)

    @settings.command(name="volume", aliases=get_aliases("volume"))
    @app_commands.describe(value="Input a integer.")
    @commands.has_permissions(manage_guild=True)
    @commands.dynamic_cooldown(cooldown_check, commands.BucketType.guild)
    async def volume(self, ctx: commands.Context, value: commands.Range[int, 1, 150]):
        "Set the player's volume."
        player: voicelink.Player = ctx.guild.voice_client
        if player:
            player.settings['volume'] = value
            await player.set_volume(value, ctx.author)

        update_settings(ctx.guild.id, {'volume': value})
        await ctx.send(get_lang(ctx.guild.id, 'setVolume').format(value))

    @settings.command(name="togglecontroller", aliases=get_aliases("togglecontroller"))
    @commands.has_permissions(manage_guild=True)
    @commands.dynamic_cooldown(cooldown_check, commands.BucketType.guild)
    async def togglecontroller(self, ctx: commands.Context):
        "Toggles the music controller."
        player, settings = self.get_settings(ctx)
        toggle = settings.get('controller', True)
        settings['controller'] = not toggle
        if player and settings['controller'] is False:
            if player.controller:
                try:
                    await player.controller.delete()
                except:
                    discord.ui.View.from_message(player.controller).stop()

        update_settings(ctx.guild.id, {'controller': not toggle})
        toggle = get_lang(ctx.guild.id, "enabled" if not toggle else "disabled")
        await ctx.send(get_lang(ctx.guild.id, 'togglecontroller').format(toggle))

    @settings.command(name="duplicatetrack", aliases=get_aliases("duplicatetrack"))
    @commands.has_permissions(manage_guild=True)
    @commands.dynamic_cooldown(cooldown_check, commands.BucketType.guild)
    async def duplicatetrack(self, ctx: commands.Context):
        "Toggle Vocard to prevent duplicate songs from queuing."
        player, settings = self.get_settings(ctx)
        toggle = settings.get('duplicateTrack', False)
        if player:
            player.queue._allow_duplicate = not toggle

        update_settings(ctx.guild.id, {'duplicateTrack': not toggle})
        toggle = get_lang(ctx.guild.id, "enabled" if toggle else "disabled")
        return await ctx.send(get_lang(ctx.guild.id, "toggleDuplicateTrack").format(toggle))
    
    @settings.command(name="customcontroller", aliases=get_aliases("customcontroller"))
    @commands.has_permissions(manage_guild=True)
    @commands.dynamic_cooldown(cooldown_check, commands.BucketType.guild)
    async def customcontroller(self, ctx: commands.Context):
        "Customizes music controller embeds."
        player, settings = self.get_settings(ctx)
        controller_settings = settings.get("default_controller", func.settings.controller)

        view = EmbedBuilderView(ctx.author, controller_settings.get("embeds").copy())
        message = await ctx.send(embed=view.build_embed(), view=view)
        view.response = message

    @settings.command(name="controllermsg", aliases=get_aliases("controllermsg"))
    @commands.has_permissions(manage_guild=True)
    @commands.dynamic_cooldown(cooldown_check, commands.BucketType.guild)
    async def controllermsg(self, ctx: commands.Context):
        "Toggles to send a message when clicking the button in the music controller."
        player, settings = self.get_settings(ctx)
        toggle = settings.get('controller_msg', True)

        settings['controller_msg'] = not toggle
        update_settings(ctx.guild.id, {'controller_msg': not toggle})
        toggle = get_lang(ctx.guild.id, "enabled" if not toggle else "disabled")
        await ctx.send(get_lang(ctx.guild.id, 'toggleControllerMsg').format(toggle))

    @app_commands.command(name="debug")
    async def debug(self, interaction: discord.Interaction):
        if interaction.user.id not in func.settings.bot_access_user:
            return await interaction.response.send_message("You are not able to use this command!")

        def clear_code(content: str):
            if content.startswith("```") and content.endswith("```"):
                return "\n".join(content.split("\n")[1:])[:-3]
            else:
                return content

        modal = DebugModal(title="Debug Panel")
        await interaction.response.send_modal(modal)
        await modal.wait()

        if modal.values is None:
            return

        e = None

        local_variables = {
            "discord": discord,
            "commands": commands,
            "voicelink": voicelink,
            "bot": self.bot,
            "interaction": interaction,
            "channel": interaction.channel,
            "author": interaction.user,
            "guild": interaction.guild,
            "message": interaction.message,
            "input": None
        }

        code = clear_code(modal.values)
        str_obj = io.StringIO()  # Retrieves a stream of data
        try:
            with contextlib.redirect_stdout(str_obj):
                exec(
                    f"async def func():\n{textwrap.indent(code, '              ')}", local_variables)
                obj = await local_variables["func"]()
                result = f"{str_obj.getvalue()}\n-- {obj}\n"
        except Exception as e:
            errormsg = ''.join(
                traceback.format_exception(e, e, e.__traceback__))
            return await interaction.followup.send(f"```py\n{errormsg}```")

        string = result.split("\n")
        text = ""
        for index, i in enumerate(string, start=1):
            text += f"{'%03d' % index} | {i}\n"
        return await interaction.followup.send(f"```{text}```")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Admin(bot))
