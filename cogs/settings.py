"""MIT License

Copyright (c) 2023 - present Vocard Development

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

import discord
import voicelink
import psutil
import function as func

from typing import Tuple
from discord import app_commands
from discord.ext import commands
from function import (
    LANGS,
    update_settings,
    get_settings,
    get_lang,
    time as ctime,
    get_aliases,
    cooldown_check
)
from views import DebugView, HelpView, EmbedBuilderView

def formatBytes(bytes: int, unit: bool = False):
    if bytes <= 1_000_000_000:
        return f"{bytes / (1024 ** 2):.1f}" + ("MB" if unit else "")
    
    else:
        return f"{bytes / (1024 ** 3):.1f}" + ("GB" if unit else "")

class Settings(commands.Cog, name="settings"):
    def __init__(self, bot) -> None:
        self.bot: commands.Bot = bot
        self.description = "This category is only available to admin permissions on the server."
    
    @commands.hybrid_group(
        name="settings",
        aliases=get_aliases("settings"),
        invoke_without_command=True
    )
    async def settings(self, ctx: commands.Context):
        view = HelpView(self.bot, ctx.author)
        embed = view.build_embed(self.qualified_name)
        view.response = await ctx.send(embed=embed, view=view)
    
    @settings.command(name="prefix", aliases=get_aliases("prefix"))
    @commands.has_permissions(manage_guild=True)
    @commands.dynamic_cooldown(cooldown_check, commands.BucketType.guild)
    async def prefix(self, ctx: commands.Context, prefix: str):
        "Change the default prefix for message commands."
        await update_settings(ctx.guild.id, {"$set": {"prefix": prefix}})
        await ctx.send(get_lang(ctx.guild.id, "setPrefix").format(ctx.prefix, prefix))

    @settings.command(name="language", aliases=get_aliases("language"))
    @commands.has_permissions(manage_guild=True)
    @commands.dynamic_cooldown(cooldown_check, commands.BucketType.guild)
    async def language(self, ctx: commands.Context, language: str):
        "You can choose your preferred language, the bot message will change to the language you set."
        language = language.upper()
        if language not in LANGS:
            return await ctx.send(get_lang(ctx.guild.id, "languageNotFound"))

        await update_settings(ctx.guild.id, {"$set": {'lang': language}})
        await ctx.send(get_lang(ctx.guild.id, 'changedLanguage').format(language))

    @language.autocomplete('language')
    async def autocomplete_callback(self, interaction: discord.Interaction, current: str) -> list:
        if current:
            return [app_commands.Choice(name=lang, value=lang) for lang in LANGS.keys() if current.upper() in lang]
        return [app_commands.Choice(name=lang, value=lang) for lang in LANGS.keys()]

    @settings.command(name="dj", aliases=get_aliases("dj"))
    @commands.has_permissions(manage_guild=True)
    @commands.dynamic_cooldown(cooldown_check, commands.BucketType.guild)
    async def dj(self, ctx: commands.Context, role: discord.Role = None):
        "Set a DJ role or remove DJ role."
        await update_settings(ctx.guild.id, {"$set": {'dj': role.id}} if role else {"$unset": {'dj': None}})
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
        mode = "FairQueue" if mode.lower() == "fairqueue" else "Queue"
        await update_settings(ctx.guild.id, {"$set": {"queueType": mode}})
        await ctx.send(get_lang(ctx.guild.id, "setqueue").format(mode))

    @settings.command(name="247", aliases=get_aliases("247"))
    @commands.has_permissions(manage_guild=True)
    @commands.dynamic_cooldown(cooldown_check, commands.BucketType.guild)
    async def playforever(self, ctx: commands.Context):
        "Toggles 24/7 mode, which disables automatic inactivity-based disconnects."
        settings = await get_settings(ctx.guild.id)
        toggle = settings.get('24/7', False)
        await update_settings(ctx.guild.id, {"$set": {'24/7': not toggle}})
        await ctx.send(get_lang(ctx.guild.id, '247').format(get_lang(ctx.guild.id, "enabled" if not toggle else "disabled")))

    @settings.command(name="bypassvote", aliases=get_aliases("bypassvote"))
    @commands.has_permissions(manage_guild=True)
    @commands.dynamic_cooldown(cooldown_check, commands.BucketType.guild)
    async def bypassvote(self, ctx: commands.Context):
        "Toggles voting system."
        settings = await get_settings(ctx.guild.id)
        toggle = settings.get('votedisable', True)
        await update_settings(ctx.guild.id, {"$set": {'votedisable': not toggle}})
        await ctx.send(get_lang(ctx.guild.id, 'bypassVote').format(get_lang(ctx.guild.id, "enabled" if not toggle else "disabled")))

    @settings.command(name="view", aliases=get_aliases("view"))
    @commands.has_permissions(manage_guild=True)
    @commands.dynamic_cooldown(cooldown_check, commands.BucketType.guild)
    async def view(self, ctx: commands.Context):
        "Show all the bot settings in your server."
        settings = await get_settings(ctx.guild.id)
        embed = discord.Embed(color=func.settings.embed_color)
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
            await player.set_volume(value, ctx.author)

        await update_settings(ctx.guild.id, {"$set": {'volume': value}})
        await ctx.send(get_lang(ctx.guild.id, 'setVolume').format(value))

    @settings.command(name="togglecontroller", aliases=get_aliases("togglecontroller"))
    @commands.has_permissions(manage_guild=True)
    @commands.dynamic_cooldown(cooldown_check, commands.BucketType.guild)
    async def togglecontroller(self, ctx: commands.Context):
        "Toggles the music controller."
        settings = await get_settings(ctx.guild.id)
        toggle = not settings.get('controller', True)

        player: voicelink.Player = ctx.guild.voice_client
        if player and toggle is False and player.controller:
            try:
                await player.controller.delete()
            except:
                discord.ui.View.from_message(player.controller).stop()

        await update_settings(ctx.guild.id, {"$set": {'controller': toggle}})
        await ctx.send(get_lang(ctx.guild.id, 'togglecontroller').format(get_lang(ctx.guild.id, "enabled" if toggle else "disabled")))

    @settings.command(name="duplicatetrack", aliases=get_aliases("duplicatetrack"))
    @commands.has_permissions(manage_guild=True)
    @commands.dynamic_cooldown(cooldown_check, commands.BucketType.guild)
    async def duplicatetrack(self, ctx: commands.Context):
        "Toggle Vocard to prevent duplicate songs from queuing."
        settings = await get_settings(ctx.guild.id)
        toggle = not settings.get('duplicateTrack', False)
        player: voicelink.Player = ctx.guild.voice_client
        if player:
            player.queue._allow_duplicate = toggle

        await update_settings(ctx.guild.id, {"$set": {'duplicateTrack': toggle}})
        return await ctx.send(get_lang(ctx.guild.id, "toggleDuplicateTrack").format(get_lang(ctx.guild.id, "disabled" if toggle else "enabled")))
    
    @settings.command(name="customcontroller", aliases=get_aliases("customcontroller"))
    @commands.has_permissions(manage_guild=True)
    @commands.dynamic_cooldown(cooldown_check, commands.BucketType.guild)
    async def customcontroller(self, ctx: commands.Context):
        "Customizes music controller embeds."
        settings = await get_settings(ctx.guild.id)
        controller_settings = settings.get("default_controller", func.settings.controller)

        view = EmbedBuilderView(ctx, controller_settings.get("embeds").copy())
        view.response = await ctx.send(embed=view.build_embed(), view=view)

    @settings.command(name="controllermsg", aliases=get_aliases("controllermsg"))
    @commands.has_permissions(manage_guild=True)
    @commands.dynamic_cooldown(cooldown_check, commands.BucketType.guild)
    async def controllermsg(self, ctx: commands.Context):
        "Toggles to send a message when clicking the button in the music controller."
        settings = await get_settings(ctx.guild.id)
        toggle = not settings.get('controller_msg', True)

        await update_settings(ctx.guild.id, {"$set": {'controller_msg': toggle}})
        await ctx.send(get_lang(ctx.guild.id, 'toggleControllerMsg').format(get_lang(ctx.guild.id, "enabled" if toggle else "disabled")))

    @app_commands.command(name="debug")
    async def debug(self, interaction: discord.Interaction):
        if interaction.user.id not in func.settings.bot_access_user:
            return await interaction.response.send_message("You are not able to use this command!")

        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')

        available_memory, total_memory = memory.available, memory.total
        used_disk_space, total_disk_space = disk.used, disk.total
        embed = discord.Embed(title="📄 Debug Panel", color=func.settings.embed_color)
        embed.description = "```==    System Info    ==\n" \
                            f"• CPU:     {psutil.cpu_freq().current}Mhz ({psutil.cpu_percent()}%)\n" \
                            f"• RAM:     {formatBytes(total_memory - available_memory)}/{formatBytes(total_memory, True)} ({memory.percent}%)\n" \
                            f"• DISK:    {formatBytes(total_disk_space - used_disk_space)}/{formatBytes(total_disk_space, True)} ({disk.percent}%)```"

        embed.add_field(
            name="🤖 Bot Information",
            value=f"```• LATENCY: {self.bot.latency:.2f}ms\n" \
                  f"• GUILDS:  {len(self.bot.guilds)}\n" \
                  f"• USERS:   {sum([guild.member_count for guild in self.bot.guilds])}\n" \
                  f"• PLAYERS: {len(self.bot.voice_clients)}```",
            inline=False
        )

        node: voicelink.Node
        for name, node in voicelink.NodePool._nodes.items():
            total_memory = node.stats.used + node.stats.free
            embed.add_field(
                name=f"{name} Node - " + ("🟢 Connected" if node._available else "🔴 Disconnected"),
                value=f"```• ADDRESS:  {node._host}:{node._port}\n" \
                      f"• PLAYERS:  {len(node._players)}\n" \
                      f"• CPU:      {node.stats.cpu_process_load:.1f}%\n" \
                      f"• RAM:      {formatBytes(node.stats.free)}/{formatBytes(total_memory, True)} ({(node.stats.free/total_memory) * 100:.1f}%)\n"
                      f"• LATENCY:  {node.latency:.2f}ms\n" \
                      f"• UPTIME:   {func.time(node.stats.uptime)}```",
                inline=True
            )

        await interaction.response.send_message(embed=embed, view=DebugView(self.bot), ephemeral=True)

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Settings(bot))
