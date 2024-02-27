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
import discord
import function as func

from discord.ext import commands, tasks
from datetime import datetime
from addons import Placeholders

class Task(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.activity_update.start()
        self.player_check.start()
        self.cache_cleaner.start()

        self.act_type = {
            "play": discord.ActivityType.playing,
            "listen": discord.ActivityType.listening,
            "watch": discord.ActivityType.watching,
            "stream": discord.ActivityType.streaming
        }
        self.current_act = 0
        self.placeholder = Placeholders(bot)

    def cog_unload(self):
        self.activity_update.cancel()
        self.player_check.cancel()
        self.cache_cleaner.cancel()
    
    @tasks.loop(minutes=10.0)
    async def activity_update(self):
        await self.bot.wait_until_ready()

        try:
            act_data = func.settings.activity[(self.current_act + 1) % len(func.settings.activity) - 1]

            act_original = self.bot.activity
            act_type = self.act_type.get(list(act_data.keys())[0].lower(), discord.ActivityType.playing)
            act_name = self.placeholder.replace(list(act_data.values())[0])

            if act_original.type != act_type or act_original.name != act_name:
                new_act = discord.Activity(type=act_type, name=act_name)
                await self.bot.change_presence(activity=new_act)
                self.current_act = (self.current_act + 1) % len(func.settings.activity)

        except:
            pass

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
        func.SETTINGS_BUFFER.clear()
        func.USERS_BUFFER.clear()

        errorFile = func.gen_report()
        if errorFile:
            report_channel = self.bot.get_channel(func.report_channel_id)
            if report_channel:
                try:
                    await report_channel.send(content=f"Report Before: <t:{round(datetime.timestamp(datetime.now()))}:F>", file=errorFile)
                except Exception as e:
                    print(f"Report could not be sent (Reason: {e})")
            func.ERROR_LOGS.clear()
        
async def setup(bot: commands.Bot):
    await bot.add_cog(Task(bot))
