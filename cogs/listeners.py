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

import voicelink
import asyncio
import discord
import function as func

from discord.ext import commands

class Listeners(commands.Cog):
    """Music Cog."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.voicelink = voicelink.NodePool()

        bot.loop.create_task(self.start_nodes())
        
    async def start_nodes(self) -> None:
        """Connect and intiate nodes."""
        await self.bot.wait_until_ready()
        for n in func.settings.nodes.values():
            try:
                await self.voicelink.create_node(
                    bot=self.bot, 
                    spotify_client_id=func.tokens.spotify_client_id, 
                    spotify_client_secret=func.tokens.spotify_client_secret,
                    **n
                )
            except Exception as e:
                print(f'Node {n["identifier"]} is not able to connect! - Reason: {e}')

    @commands.Cog.listener()
    async def on_voicelink_track_end(self, player: voicelink.Player, track, _):
        await player.do_next()

    @commands.Cog.listener()
    async def on_voicelink_track_stuck(self, player: voicelink.Player, track, _):
        await asyncio.sleep(10)
        await player.do_next()

    @commands.Cog.listener()
    async def on_voicelink_track_exception(self, player: voicelink.Player, track, error: dict):
        try:
            player._track_is_stuck = True
            await player.context.send(f"{error['message']}! The next song will begin in the next 5 seconds.", delete_after=10)
        except:
            pass

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        if member.bot:
            return
        
        if before.channel == after.channel:
            return

        player: voicelink.Player = member.guild.voice_client
        if not player:
            return
        
        guild = member.guild.id
        is_joined = True
        
        if not before.channel and after.channel:
            if after.channel.id != player.channel.id:
                return

        elif before.channel and not after.channel:
            is_joined = False
        
        elif before.channel and after.channel:
            if after.channel.id != player.channel.id:
                is_joined = False
                
        if player.is_ipc_connected:
            await self.bot.ipc.send({
                "op": "updateGuild",
                "user": {
                    "user_id": member.id,
                    "avatar_url": member.display_avatar.url,
                    "name": member.name,
                },
                "channel_name": member.voice.channel.name if is_joined else "",
                "guild_id": guild,
                "is_joined": is_joined
            })

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Listeners(bot))
