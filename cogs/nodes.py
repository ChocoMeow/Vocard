import voicelink
import asyncio
import function as func

from os import getenv
from discord.ext import commands

class Nodes(commands.Cog):
    """Music Cog."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.voicelink = voicelink.NodePool()

        bot.loop.create_task(self.start_nodes())
        
    async def start_nodes(self) -> None:
        """Connect and intiate nodes."""
        await self.bot.wait_until_ready()
        for n in func.nodes.values():
            try:
                await self.voicelink.create_node(bot=self.bot, 
                                                 spotify_client_id=getenv('SPOTIFY_CLIENT_ID'), 
                                                 spotify_client_secret=getenv('SPOTIFY_CLIENT_SECRET'),
                                                 **n)
            except:
                print(f'Node {n["identifier"]} is not able to connect!')

    @commands.Cog.listener()
    async def on_voicelink_track_end(self, player: voicelink.Player, track, _):
        await player.do_next()

    @commands.Cog.listener()
    async def on_voicelink_track_stuck(self, player: voicelink.Player, track, _):
        await asyncio.sleep(5)
        await player.do_next()

    @commands.Cog.listener()
    async def on_voicelink_track_exception(self, player: voicelink.Player, track, _):
        try:
            await player.context.send(f"{_} Please wait for 5 seconds.", delete_after=5)
        except:
            pass
        await asyncio.sleep(5)
        await player.do_next()

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Nodes(bot))
