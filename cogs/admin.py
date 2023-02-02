import discord
import voicelink
import io
import contextlib
import textwrap
import traceback

from discord import app_commands
from discord.ext import commands
from function import (
    langs, 
    lang_guilds, 
    update_settings, 
    get_settings, 
    get_lang,
    embed_color,
    time as ctime
)
from view import DebugModal

class Admin(commands.GroupCog, name="settings"):
    def __init__(self, bot) -> None:
        self.bot = bot
        self.description = "This category is only available to admin permissions on the server."

    def get_settings(self, interaction: discord.Interaction) -> dict:
        player: voicelink.Player = interaction.guild.voice_client
        if not player:
            settings = get_settings(interaction.guild_id)
        else:
            settings = player.settings
        
        return player, settings

    @app_commands.command(
        name = "language",
        description = "You can choose your preferred language, the bot message will change to the language you set."
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.checks.cooldown(2, 60.0, key=lambda i: (i.guild_id))
    @app_commands.guild_only()
    async def language(self, interaction: discord.Interaction, language: str):
        language = language.upper()
        if language not in langs:
            return await interaction.response.send_message(get_lang(interaction.guild_id, "languageNotFound"))

        player, settings = self.get_settings(interaction)
        if player:
            player.lang = language
        lang_guilds[interaction.guild_id] = language
        update_settings(interaction.guild_id, {'lang': language})

        await interaction.response.send_message(get_lang(interaction.guild_id, 'changedLanguage').format(language))
    
    @language.autocomplete('language')
    async def autocomplete_callback(self, interaction: discord.Interaction, current: str) -> list:
        if current:
            return [ app_commands.Choice(name=lang, value=lang) for lang in langs.keys() if current.upper() in lang ]
        return [ app_commands.Choice(name=lang, value=lang) for lang in langs.keys() ]

    @app_commands.command(
        name = "dj",
        description = "Set a DJ role or remove DJ role."
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.guild_only()
    async def dj(self, interaction: discord.Interaction, role: discord.Role = None):
        player: voicelink.Player = interaction.guild.voice_client

        if not role:
            if player:
                player.settings.pop('dj', None)
            update_settings(interaction.guild_id, {'dj':''}, mode="Unset")        
        else:
            if player:
                player.settings['dj'] = role.id
            update_settings(interaction.guild_id, {'dj': role.id })

        await interaction.response.send_message(get_lang(interaction.guild_id, 'setDJ').format(f"<@&{role.id}>" if role else "None"), allowed_mentions=discord.AllowedMentions.none())

    @app_commands.command(
        name = "queue",
        description = "Change to another type of queue mode."
    )
    @app_commands.choices(mode= [
        app_commands.Choice(name="FairQueue", value="FairQueue"),
        app_commands.Choice(name="Queue", value="Queue")
    ])
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.guild_only()
    async def queue(self, interaction: discord.Interaction, mode: str):
        player, settings = self.get_settings(interaction)
        settings["queueType"] = mode
        update_settings(interaction.guild_id, {"queueType": mode})
        await interaction.response.send_message(get_lang(interaction.guild_id, "setqueue").format(mode))

    @app_commands.command(
        name = "247",
        description = "Toggles 24/7 mode, which disables automatic inactivity-based disconnects."
    )
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_guild=True)
    async def playforever(self, interaction: discord.Interaction):
        player, settings = self.get_settings(interaction)
        toggle = settings.get('24/7', False)
        settings['24/7'] = not toggle
        update_settings(interaction.guild_id, {'24/7':not toggle})
        toggle = get_lang(interaction.guild_id, "enabled" if not toggle else "disabled")
        await interaction.response.send_message(get_lang(interaction.guild_id, '247').format(toggle))

    @app_commands.command(
        name = "bypassvote",
        description = "Toggles voting system.")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def bypassvote(self, interaction: discord.Interaction):
        player, settings = self.get_settings(interaction)     
        toggle = settings.get('votedisable', True)
        settings['votedisable'] = not toggle
        update_settings(interaction.guild_id, {'votedisable': not toggle})
        toggle = get_lang(interaction.guild_id, "enabled" if not toggle else "disabled")
        await interaction.response.send_message(get_lang(interaction.guild_id, 'bypassVote').format(toggle))
        
    @app_commands.command(
        name = "view",
        description = "Show all the bot settings in your server."
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.guild_only()
    async def view(self, interaction: discord.Interaction):
        player, settings = self.get_settings(interaction)
        embed=discord.Embed(color=embed_color)
        embed.set_author(name=get_lang(interaction.guild_id, 'settingsMenu').format(interaction.guild.name), icon_url=self.bot.user.display_avatar.url)
        if interaction.guild.icon:
            embed.set_thumbnail(url=interaction.guild.icon.url)

        embed.add_field(name=get_lang(interaction.guild_id, 'settingsTitle'), value=get_lang(interaction.guild_id, 'settingsValue').format(
                                                                                        settings.get('lang', 'EN'),
                                                                                        settings.get('controller', True),
                                                                                        f"<@&{settings['dj']}>" if 'dj' in settings else '`None`',
                                                                                        settings.get('votedisable', False),
                                                                                        settings.get('24/7', False),
                                                                                        settings.get('volume', 100),
                                                                                        ctime(settings.get('playTime', 0) * 60 * 1000),
                                                                                        inline=True)
                                                                                    )
        embed.add_field(name=get_lang(interaction.guild_id, 'settingsTitle2'), value=get_lang(interaction.guild_id, 'settingsValue2').format(
                                                                                        settings.get("queueType", "Queue"),
                                                                                        "200",
                                                                                        settings.get("duplicateTrack", True)
                                                                                        )
                                                                                    )

        perms = interaction.guild.me.guild_permissions
        embed.add_field(name=get_lang(interaction.guild_id, 'settingsPermTitle'), value=get_lang(interaction.guild_id, 'settingsPermValue').format(
                                                                                          '<a:Check:941206936651706378>' if perms.administrator else '<a:Cross:941206918255497237>',
                                                                                          '<a:Check:941206936651706378>' if perms.manage_guild else '<a:Cross:941206918255497237>',
                                                                                          '<a:Check:941206936651706378>' if perms.manage_channels else '<a:Cross:941206918255497237>',
                                                                                          '<a:Check:941206936651706378>' if perms.manage_messages else '<a:Cross:941206918255497237>'), inline=False
                                                                                        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(
        name = "volume",
        description = "Set the player's volume."
    )
    @app_commands.describe(
        value = "Input a integer."
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.guild_only()
    async def volume(self, interaction: discord.Interaction, value: app_commands.Range[int, 1, 150]):
        player: voicelink.Player = interaction.guild.voice_client

        if player:
            player.settings['volume'] = value
            await player.set_volume(value)
        
        update_settings(interaction.guild_id, {'volume':value})
        await interaction.response.send_message(get_lang(interaction.guild_id, 'setVolume').format(value))

    @app_commands.command(
        name = "togglecontroller",
        description = "Toggles the music controller."
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.guild_only()
    async def togglecontroller(self, interaction: discord.Interaction):
        player, settings = self.get_settings(interaction)
        toggle = settings.get('controller', True)
        settings['controller'] = not toggle
        if player and settings['controller'] is False:
            if player.controller:
                try:
                    await player.controller.delete()
                except:
                    discord.ui.View.from_message(player.controller).stop()

        update_settings(interaction.guild_id, {'controller': not toggle})
        toggle = get_lang(interaction.guild_id, "enabled" if not toggle else "disabled")
        await interaction.response.send_message(get_lang(interaction.guild_id, 'togglecontroller').format(toggle))

    @app_commands.command(
        name = "duplicatetrack",
        description = "Toggle Vocard to prevent duplicate songs from queuing."
    )
    @app_commands.choices(toggle = [
        app_commands.Choice(name="Enable", value="enabled"),
        app_commands.Choice(name="Disable", value="disabled")
    ])
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.guild_only()
    async def duplicatetrack(self, interaction: discord.Interaction, toggle: str):
        player, settings = self.get_settings(interaction)
        if player:
            player.queue._duplicateTrack = False if toggle == 'enabled' else True

        update_settings(interaction.guild_id, {'duplicateTrack': False if toggle == 'enabled' else True})
        return await interaction.response.send_message(get_lang(interaction.guild_id, "toggleDuplicateTrack").format(get_lang(interaction.guild_id, toggle)))
    
    @app_commands.command(
        name = "debug",
    )
    @app_commands.guild_only()
    async def debug(self, interaction: discord.Interaction):
        if interaction.user.id not in [358819659581227011, 705783356767338648]:
            return await interaction.response.send_message("You are not able to use this command!")
        
        def clear_code(content):
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
        str_obj = io.StringIO() #Retrieves a stream of data
        try:
            with contextlib.redirect_stdout(str_obj):
                exec(f"async def func():\n{textwrap.indent(code, '              ')}", local_variables)
                obj = await local_variables["func"]()
                result = f"{str_obj.getvalue()}\n-- {obj}\n"
        except Exception as e:
            errormsg = ''.join(traceback.format_exception(e, e, e.__traceback__))
            return await interaction.followup.send(f"```py\n{errormsg}```")

        string = result.split("\n")
        text = ""
        for index, i in enumerate(string, start=1):
            text += f"{'%03d' % index} | {i}\n"
        return await interaction.followup.send(f"```{text}```")

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Admin(bot))