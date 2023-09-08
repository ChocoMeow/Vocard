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

from function import (
    get_lang,
    get_aliases,
    cooldown_check
)
from discord import app_commands
from discord.ext import commands


async def check_access(ctx: commands.Context):
    player: voicelink.Player = ctx.guild.voice_client
    if not player:
        raise voicelink.VoicelinkException(get_lang(ctx.guild.id, 'noPlayer'))

    if ctx.author not in player.channel.members:
        if not ctx.author.guild_permissions.manage_guild:
            return await ctx.send(player.get_msg('notInChannel').format(ctx.author.mention, player.channel.mention), ephemeral=True)

    return player


class Effect(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.description = "This category is only available to DJ on this server. (You can setdj on your server by /settings setdj <DJ ROLE>)"

    async def effect_autocomplete(self, interaction: discord.Interaction, current: str) -> list:
        player: voicelink.Player = interaction.guild.voice_client
        if not player:
            return []
        if current:
            return [app_commands.Choice(name=effect.tag, value=effect.tag) for effect in player.filters.get_filters() if current in effect.tag]
        return [app_commands.Choice(name=effect.tag, value=effect.tag) for effect in player.filters.get_filters()]

    @commands.hybrid_command(name="speed", aliases=get_aliases("speed"))
    @app_commands.describe(value="The value to set the speed to. Default is `1.0`")
    @commands.dynamic_cooldown(cooldown_check, commands.BucketType.guild)
    async def speed(self, ctx: commands.Context, value: commands.Range[float, 0, 2]):
        "Sets the player's playback speed"
        player = await check_access(ctx)

        if player.filters.has_filter(filter_tag="speed"):
            player.filters.remove_filter(filter_tag="speed")
        await player.add_filter(voicelink.Timescale(tag="speed", speed=value))
        await ctx.send(f"You set the speed to **{value}**.")

    @commands.hybrid_command(name="karaoke", aliases=get_aliases("karaoke"))
    @app_commands.describe(
        level="The level of the karaoke. Default is `1.0`",
        monolevel="The monolevel of the karaoke. Default is `1.0`",
        filterband="The filter band of the karaoke. Default is `220.0`",
        filterwidth="The filter band of the karaoke. Default is `100.0`"
    )
    @commands.dynamic_cooldown(cooldown_check, commands.BucketType.guild)
    async def karaoke(self, ctx: commands.Context, level: commands.Range[float, 0, 2] = 1.0, monolevel: commands.Range[float, 0, 2] = 1.0, filterband: commands.Range[float, 100, 300] = 220.0, filterwidth: commands.Range[float, 50, 150] = 100.0) -> None:
        "Uses equalization to eliminate part of a band, usually targeting vocals."
        player = await check_access(ctx)

        if player.filters.has_filter(filter_tag="karaoke"):
            player.filters.remove_filter(filter_tag="karaoke")
        await player.add_filter(voicelink.Karaoke(tag="karaoke", level=level, mono_level=monolevel, filter_band=filterband, filter_width=filterwidth))
        await ctx.send(player.get_msg('karaoke').format(level, monolevel, filterband, filterwidth))

    @commands.hybrid_command(name="tremolo", aliases=get_aliases("tremolo"))
    @app_commands.describe(
        frequency="The frequency of the tremolo. Default is `2.0`",
        depth="The depth of the tremolo. Default is `0.5`"
    )
    @commands.dynamic_cooldown(cooldown_check, commands.BucketType.guild)
    async def tremolo(self, ctx: commands.Context, frequency: commands.Range[float, 0, 10] = 2.0, depth: commands.Range[float, 0, 1] = 0.5) -> None:
        "Uses amplification to create a shuddering effect, where the volume quickly oscillates."
        player = await check_access(ctx)

        if player.filters.has_filter(filter_tag="tremolo"):
            player.filters.remove_filter(filter_tag="tremolo")
        await player.add_filter(voicelink.Tremolo(tag="tremolo", frequency=frequency, depth=depth))
        await ctx.send(player.get_msg('tremolo&vibrato').format(frequency, depth))

    @commands.hybrid_command(name="vibrato", aliases=get_aliases("vibrato"))
    @app_commands.describe(
        frequency="The frequency of the vibrato. Default is `2.0`",
        depth="The Depth of the vibrato. Default is `0.5`"
    )
    @commands.dynamic_cooldown(cooldown_check, commands.BucketType.guild)
    async def vibrato(self, ctx: commands.Context, frequency: commands.Range[float, 0, 14] = 2.0, depth: commands.Range[float, 0, 1] = 0.5) -> None:
        "Similar to tremolo. While tremolo oscillates the volume, vibrato oscillates the pitch."
        player = await check_access(ctx)

        if player.filters.has_filter(filter_tag="vibrato"):
            player.filters.remove_filter(filter_tag="vibrato")
        await player.add_filter(voicelink.Vibrato(tag="vibrato", frequency=frequency, depth=depth))
        await ctx.send(player.get_msg('tremolo&vibrato').format(frequency, depth))

    @commands.hybrid_command(name="rotation", aliases=get_aliases("rotation"))
    @app_commands.describe(hertz="The hertz of the rotation. Default is `0.2`")
    @commands.dynamic_cooldown(cooldown_check, commands.BucketType.guild)
    async def rotation(self, ctx: commands.Context, hertz: commands.Range[float, 0, 2] = 0.2) -> None:
        "Rotates the sound around the stereo channels/user headphones aka Audio Panning."
        player = await check_access(ctx)

        if player.filters.has_filter(filter_tag="rotation"):
            player.filters.remove_filter(filter_tag="rotation")
        await player.add_filter(voicelink.Rotation(tag="rotation", rotation_hertz=hertz))
        await ctx.send(player.get_msg('rotation').format(hertz))

    @commands.hybrid_command(name="distortion", aliases=get_aliases("distortion"))
    @commands.dynamic_cooldown(cooldown_check, commands.BucketType.guild)
    async def distortion(self, ctx: commands.Context) -> None:
        "Distortion effect. It can generate some pretty unique audio effects."
        player = await check_access(ctx)

        if player.filters.has_filter(filter_tag="distortion"):
            player.filters.remove_filter(filter_tag="distortion")
        await player.add_filter(voicelink.Distortion(tag="distortion", sin_offset=0.0, sin_scale=1.0, cos_offset=0.0, cos_scale=1.0, tan_offset=0.0, tan_scale=1.0, offset=0.0, scale=1.0))
        await ctx.send(player.get_msg('distortion'))

    @commands.hybrid_command(name="lowpass", aliases=get_aliases("lowpass"))
    @app_commands.describe(smoothing="The level of the lowPass. Default is `20.0`")
    @commands.dynamic_cooldown(cooldown_check, commands.BucketType.guild)
    async def lowpass(self, ctx: commands.Context, smoothing: commands.Range[float, 10, 30] = 20.0) -> None:
        "Filter which supresses higher frequencies and allows lower frequencies to pass."
        player = await check_access(ctx)

        if player.filters.has_filter(filter_tag="lowpass"):
            player.filters.remove_filter(filter_tag="lowpass")
        await player.add_filter(voicelink.LowPass(tag="lowpass", smoothing=smoothing))
        await ctx.send(player.get_msg('lowpass').format(smoothing))

    @commands.hybrid_command(name="channelmix", aliases=get_aliases("channelmix"))
    @app_commands.describe(
        left_to_left="Sounds from left to left. Default is `1.0`",
        right_to_right="Sounds from right to right. Default is `1.0`",
        left_to_right="Sounds from left to right. Default is `0.0`",
        right_to_left="Sounds from right to left. Default is `0.0`"
    )
    @commands.dynamic_cooldown(cooldown_check, commands.BucketType.guild)
    async def channelmix(self, ctx: commands.Context, left_to_left: commands.Range[float, 0, 1] = 1.0, right_to_right: commands.Range[float, 0, 1] = 1.0, left_to_right: commands.Range[float, 0, 1] = 0.0, right_to_left: commands.Range[float, 0, 1] = 0.0) -> None:
        "Filter which manually adjusts the panning of the audio."
        player = await check_access(ctx)

        if player.filters.has_filter(filter_tag="channelmix"):
            player.filters.remove_filter(filter_tag="channelmix")
        await player.add_filter(voicelink.ChannelMix(tag="channelmix", left_to_left=left_to_left, right_to_right=right_to_right, left_to_right=left_to_right, right_to_left=right_to_left))
        await ctx.send(player.get_msg('channelmix').format(left_to_left, right_to_right, left_to_right, right_to_left))

    @commands.hybrid_command(name="nightcore", aliases=get_aliases("nightcore"))
    @commands.dynamic_cooldown(cooldown_check, commands.BucketType.guild)
    async def nightcore(self, ctx: commands.Context) -> None:
        "Add nightcore filter into your player."
        player = await check_access(ctx)

        await player.add_filter(voicelink.Timescale.nightcore())
        await ctx.send(player.get_msg('nightcore'))

    @commands.hybrid_command(name="8d", aliases=get_aliases("8d"))
    @commands.dynamic_cooldown(cooldown_check, commands.BucketType.guild)
    async def eightD(self, ctx: commands.Context) -> None:
        "Add 8D filter into your player."
        player = await check_access(ctx)

        await player.add_filter(voicelink.Rotation.nightD())
        await ctx.send(player.get_msg('8d'))

    @commands.hybrid_command(name="vaporwave", aliases=get_aliases("vaporwave"))
    @commands.dynamic_cooldown(cooldown_check, commands.BucketType.guild)
    async def vaporwave(self, ctx: commands.Context) -> None:
        "Add vaporwave filter into your player."
        player = await check_access(ctx)

        await player.add_filter(voicelink.Timescale.vaporwave())
        await ctx.send(player.get_msg('vaporwave'))

    @commands.hybrid_command(name="cleareffect", aliases=get_aliases("cleareffect"))
    @app_commands.describe(effect="Remove a specific sound effects.")
    @app_commands.autocomplete(effect=effect_autocomplete)
    @commands.dynamic_cooldown(cooldown_check, commands.BucketType.guild)
    async def cleareffect(self, ctx: commands.Context, effect: str = None) -> None:
        "Clear all or specific sound effects."
        player = await check_access(ctx)

        if effect:
            await player.remove_filter(effect)
        else:
            await player.reset_filter()
            
        await ctx.send(player.get_msg('cleareffect'))


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Effect(bot))
