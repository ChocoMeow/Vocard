import function
import voicelink
import discord

from discord.ext import commands, tasks
from datetime import datetime
from io import BytesIO

class Task(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.player_check.start()
        self.cache_cleaner.start()

    def cog_unload(self):
        self.player_check.cancel()
        self.cache_cleaner.cancel()
    
    @tasks.loop(minutes=5.0)
    async def player_check(self):
        if not self.bot.voice_clients:
            return
        
        player: voicelink.Player
        for player in self.bot.voice_clients:
            try:
                if not player.channel or not player.context or not player.guild:
                    await player.teardown()
                    continue
            except:
                await player.teardown()
                continue
            
            members = player.channel.members
            if (not player.is_playing and player.queue.is_empty) or not any(False if member.bot or member.voice.self_deaf else True for member in members):
                if not player.settings.get('24/7', False):
                    await player.teardown()
                    continue
                else:
                    if not player.is_paused:
                        await player.set_pause(True)
            else:
                if not player.guild.me:
                    await player.teardown()
                    continue
                elif not player.guild.me.voice:
                    await player.connect(timeout=0.0, reconnect=True)

            try:
                if player.dj not in members:
                    for m in members:
                        if not m.bot:
                            player.dj = m
                            break
            except:
                pass
    
    @tasks.loop(hours=12.0)
    async def cache_cleaner(self):
        function.lang_guilds.clear()
        function.playlist_name.clear()

        if function.error_log:
            report_channel = self.bot.get_channel(function.report_channel_id)
            if report_channel:
                errorText = ""
                for guildId, error in function.error_log.items():
                    errorText += f"Guild ID: {guildId}\n" + "-" * 30 + "\n"
                    for index, (key, value) in enumerate(error.items() , start=1):
                        errorText += f"Error No: {index}, Time: {datetime.fromtimestamp(key)}\n" + value + "-" * 30 + "\n\n"

                buffer = BytesIO(errorText.encode('utf-8'))
                tempFile = discord.File(buffer, filename='report.txt')
                try:
                    await report_channel.send(content=f"Report Before: <t:{round(datetime.timestamp(datetime.now()))}:F>", file=tempFile)
                except Exception as e:
                    print(f"Report could not be sent (Reason: {e})")
            function.error_log.clear()
        
async def setup(bot: commands.Bot):
    await bot.add_cog(Task(bot))
