import discord
import voicelink

from function import (
    get_lang,
)
from discord import app_commands
from discord.ext import commands

async def check_access(interaction: discord.Interaction):
    player: voicelink.Player = interaction.guild.voice_client
    if not player:
        raise voicelink.VoicelinkException(get_lang(interaction.guild_id, 'noPlayer'))
    
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
            return [ app_commands.Choice(name=effect.tag, value=effect.tag) for effect in player.filters.get_filters() if current in effect.tag]
        return [ app_commands.Choice(name=effect.tag, value=effect.tag) for effect in player.filters.get_filters() ]

    @app_commands.command(
        name = "speed",
        description= "Sets the player's playback speed."
    )
    @app_commands.describe(
        value = "The value to set the speed to. Default is `1.0`"
    )
    @app_commands.guild_only()
    async def speed(self, interaction: discord.Interaction, value: app_commands.Range[float, 0, 2]):
        player = await check_access(interaction)

        if interaction.user not in player.channel.members:
            if not interaction.user.guild_permissions.manage_guild:
                return await interaction.response.send_message(player.get_msg('notInChannel').format(interaction.user.mention, player.channel.mention), ephemeral=True)       
        
        if player.filters.has_filter(filter_tag="speed"):
            player.filters.remove_filter(filter_tag="speed")
        await player.add_filter(voicelink.Timescale(tag="speed", speed= value))
        await interaction.response.send_message(f"You set the speed to **{value}**.")

    @app_commands.command(
        name = "karaoke",
        description= "Uses equalization to eliminate part of a band, usually targeting vocals."
    )
    @app_commands.describe(
        level = "The level of the karaoke. Default is `1.0`",
        monolevel = "The monolevel of the karaoke. Default is `1.0`",
        filterband = "The filter band of the karaoke. Default is `220.0`",
        filterwidth = "The filter band of the karaoke. Default is `100.0`"
    )
    @app_commands.guild_only()
    async def karaoke(self, interaction: discord.Interaction, level: app_commands.Range[float, 0, 2] = 1.0, monolevel: app_commands.Range[float, 0, 2] = 1.0, filterband: app_commands.Range[float, 100, 300] = 220.0, filterwidth: app_commands.Range[float, 50, 150] = 100.0) -> None:
        player = await check_access(interaction)

        if interaction.user not in player.channel.members:
            if not interaction.user.guild_permissions.manage_guild:
                return await interaction.response.send_message(player.get_msg('notInChannel').format(interaction.user.mention, player.channel.mention), ephemeral=True)       
        
        if player.filters.has_filter(filter_tag="karaoke"):
            player.filters.remove_filter(filter_tag="karaoke")
        await player.add_filter(voicelink.Karaoke(tag="karaoke", level=level, mono_level=monolevel, filter_band=filterband, filter_width=filterwidth))
        await interaction.response.send_message(player.get_msg('karaoke').format(level, monolevel, filterband, filterwidth))
        
    @app_commands.command(
        name = "tremolo",
        description= "Uses amplification to create a shuddering effect, where the volume quickly oscillates."
    )
    @app_commands.describe(
        frequency = "The frequency of the tremolo. Default is `2.0`",
        depth = "The depth of the tremolo. Default is `0.5`"
    )
    @app_commands.guild_only()
    async def tremolo(self, interaction: discord.Interaction, frequency: app_commands.Range[float, 0, 10] = 2.0, depth: app_commands.Range[float, 0, 1] = 0.5) -> None:
        player = await check_access(interaction)

        if interaction.user not in player.channel.members:
            if not interaction.user.guild_permissions.manage_guild:
                return await interaction.response.send_message(player.get_msg('notInChannel').format(interaction.user.mention, player.channel.mention), ephemeral=True)       
        
        if player.filters.has_filter(filter_tag="tremolo"):
            player.filters.remove_filter(filter_tag="tremolo")
        await player.add_filter(voicelink.Tremolo(tag="tremolo", frequency=frequency, depth=depth))
        await interaction.response.send_message(player.get_msg('tremolo&vibrato').format(frequency, depth))

    @app_commands.command(
        name = "vibrato",
        description= "Similar to tremolo. While tremolo oscillates the volume, vibrato oscillates the pitch."
    )
    @app_commands.describe(
        frequency = "The frequency of the vibrato. Default is `2.0`",
        depth = "The Depth of the vibrato. Default is `0.5`"
    )
    @app_commands.guild_only()
    async def vibrato(self, interaction: discord.Interaction, frequency: app_commands.Range[float, 0, 14] = 2.0, depth: app_commands.Range[float, 0, 1] = 0.5) -> None:
        player = await check_access(interaction)

        if interaction.user not in player.channel.members:
            if not interaction.user.guild_permissions.manage_guild:
                return await interaction.response.send_message(player.get_msg('notInChannel').format(interaction.user.mention, player.channel.mention), ephemeral=True)       
        
        if player.filters.has_filter(filter_tag="vibrato"):
            player.filters.remove_filter(filter_tag="vibrato")
        await player.add_filter(voicelink.Vibrato(tag="vibrato", frequency=frequency, depth=depth))
        await interaction.response.send_message(player.get_msg('tremolo&vibrato').format(frequency, depth))  

    @app_commands.command(
        name = "rotation",
        description= "Rotates the sound around the stereo channels/user headphones aka Audio Panning."
    )
    @app_commands.describe(
        hertz = "The hertz of the rotation. Default is `0.2`"
    )
    @app_commands.guild_only()
    async def rotation(self, interaction: discord.Interaction, hertz: app_commands.Range[float, 0, 2] = 0.2) -> None:
        player = await check_access(interaction)

        if interaction.user not in player.channel.members:
            if not interaction.user.guild_permissions.manage_guild:
                return await interaction.response.send_message(player.get_msg('notInChannel').format(interaction.user.mention, player.channel.mention), ephemeral=True)       
        
        if player.filters.has_filter(filter_tag="rotation"):
            player.filters.remove_filter(filter_tag="rotation")
        await player.add_filter(voicelink.Rotation(tag="rotation", rotation_hertz=hertz))
        await interaction.response.send_message(player.get_msg('rotation').format(hertz))

    @app_commands.command(
        name = "distortion",
        description= "Distortion effect. It can generate some pretty unique audio effects."
    )
    @app_commands.guild_only()
    async def distortion(self, interaction: discord.Interaction) -> None:
        player = await check_access(interaction)

        if interaction.user not in player.channel.members:
            if not interaction.user.guild_permissions.manage_guild:
                return await interaction.response.send_message(player.get_msg('notInChannel').format(interaction.user.mention, player.channel.mention), ephemeral=True)       
        
        if player.filters.has_filter(filter_tag="distortion"):
            player.filters.remove_filter(filter_tag="distortion")
        await player.add_filter(voicelink.Distortion(tag="distortion", sin_offset= 0.0, sin_scale= 1.0, cos_offset= 0.0, cos_scale=1.0, tan_offset= 0.0, tan_scale=1.0, offset=0.0, scale=1.0))
        await interaction.response.send_message(player.get_msg('distortion'))

    @app_commands.command(
        name = "lowpass",
        description= "Filter which supresses higher frequencies and allows lower frequencies to pass."
    )
    @app_commands.describe(
        smoothing = "The level of the lowPass. Default is `20.0`"
    )
    @app_commands.guild_only()
    async def lowpass(self, interaction: discord.Interaction, smoothing: app_commands.Range[float, 10, 30] = 20.0) -> None:
        player = await check_access(interaction)

        if interaction.user not in player.channel.members:
            if not interaction.user.guild_permissions.manage_guild:
                return await interaction.response.send_message(player.get_msg('notInChannel').format(interaction.user.mention, player.channel.mention), ephemeral=True)       
        
        if player.filters.has_filter(filter_tag="lowpass"):
            player.filters.remove_filter(filter_tag="lowpass")
        await player.add_filter(voicelink.LowPass(tag="lowpass", smoothing= smoothing))
        await interaction.response.send_message(player.get_msg('lowpass').format(smoothing))

    @app_commands.command(
        name = "channelmix",
        description= "Filter which manually adjusts the panning of the audio."
    )
    @app_commands.describe(
        left_to_left = "Sounds from left to left. Default is `1.0`",
        right_to_right = "Sounds from right to right. Default is `1.0`",
        left_to_right = "Sounds from left to right. Default is `0.0`",
        right_to_left = "Sounds from right to left. Default is `0.0`"
    )
    @app_commands.guild_only()
    async def channelmix(self, interaction: discord.Interaction, left_to_left: app_commands.Range[float, 0, 1] = 1.0, right_to_right: app_commands.Range[float, 0, 1] = 1.0, left_to_right: app_commands.Range[float, 0, 1] = 0.0, right_to_left: app_commands.Range[float, 0, 1] = 0.0) -> None:
        player = await check_access(interaction)
        
        if interaction.user not in player.channel.members:
            if not interaction.user.guild_permissions.manage_guild:
                return await interaction.response.send_message(player.get_msg('notInChannel').format(interaction.user.mention, player.channel.mention), ephemeral=True)       
        
        if player.filters.has_filter(filter_tag="channelmix"):
            player.filters.remove_filter(filter_tag="channelmix")
        await player.add_filter(voicelink.ChannelMix(tag="channelmix", left_to_left=left_to_left, right_to_right=right_to_right, left_to_right=left_to_right, right_to_left=right_to_left))
        await interaction.response.send_message(player.get_msg('channelmix').format(left_to_left, right_to_right, left_to_right, right_to_left))

    @app_commands.command(
        name = "nightcore",
        description= "Add nightcore filter into your player."
    )
    @app_commands.guild_only()
    async def nightcore(self, interaction: discord.Interaction) -> None:
        player = await check_access(interaction)

        if interaction.user not in player.channel.members:
            if not interaction.user.guild_permissions.manage_guild:
                return await interaction.response.send_message(player.get_msg('notInChannel').format(interaction.user.mention, player.channel.mention), ephemeral=True)       
        
        await player.add_filter(voicelink.Timescale.nightcore())
        await interaction.response.send_message(player.get_msg('nightcore'))

    @app_commands.command(
        name = "8d",
        description= "Add 8D filter into your player."
    )
    @app_commands.guild_only()
    async def eightD(self, interaction: discord.Interaction) -> None:
        player = await check_access(interaction)

        if interaction.user not in player.channel.members:
            if not interaction.user.guild_permissions.manage_guild:
                return await interaction.response.send_message(player.get_msg('notInChannel').format(interaction.user.mention, player.channel.mention), ephemeral=True)       
         
        await player.add_filter(voicelink.Rotation.nightD())
        await interaction.response.send_message(player.get_msg('8d'))

    @app_commands.command(
        name = "vaporwave",
        description= "Add vaporwave filter into your player."
    )
    @app_commands.guild_only()
    async def vaporwave(self, interaction: discord.Interaction) -> None:
        player = await check_access(interaction)
        
        if interaction.user not in player.channel.members:
            if not interaction.user.guild_permissions.manage_guild:
                return await interaction.response.send_message(player.get_msg('notInChannel').format(interaction.user.mention, player.channel.mention), ephemeral=True)       
         
        await player.add_filter(voicelink.Timescale.vaporwave())
        await interaction.response.send_message(player.get_msg('vaporwave'))

    @app_commands.command(
        name = "cleareffect",
        description= "Clear all or specific sound effects."
    )
    @app_commands.describe(
        effect = "Remove a specific sound effects."
    )
    @app_commands.guild_only()
    @app_commands.autocomplete(effect=effect_autocomplete)
    async def cleareffect(self, interaction: discord.Interaction, effect: str = None) -> None:
        player: voicelink.Player = interaction.guild.voice_client
        if not player:
            return await interaction.response.send_message(get_lang(interaction.guild_id, "noPlayer"), ephemeral=True)

        if interaction.user not in player.channel.members:
            if not interaction.user.guild_permissions.manage_guild:
                return await interaction.response.send_message(player.get_msg('notInChannel').format(interaction.user.mention, player.channel.mention), ephemeral=True)       
        if effect:
            await player.remove_filter(effect)
        else:
            await player.reset_filter()
        await interaction.response.send_message(player.get_msg('cleareffect'))

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Effect(bot))