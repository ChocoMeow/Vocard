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

from voicelink.config import Config
from discord.ext import commands, tasks

class Task(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.activity_update.start()
        self.cache_cleaner.start()

        self.current_act = 0
        self.placeholder = voicelink.BotPlaceholder(bot)

    def cog_unload(self):
        self.activity_update.cancel()
        self.cache_cleaner.cancel()
    
    @tasks.loop(seconds=Config().timer_settings.get("bot_activity_update", 600))
    async def activity_update(self):
        await self.bot.wait_until_ready()

        try:
            act_data = Config().activity[(self.current_act + 1) % len(Config().activity) - 1]
            act_original = self.bot.activity
            act_type = getattr(discord.ActivityType, act_data.get("type", "").lower(), discord.ActivityType.playing)
            act_name = self.placeholder.replace(act_data.get("name", ""))

            status_type = getattr(discord.Status, act_data.get("status", "").lower(), None)

            if act_original.type != act_type or act_original.name != act_name:
                self.bot.activity = discord.Activity(type=act_type, name=act_name)
                await self.bot.change_presence(activity=self.bot.activity, status=status_type)
                self.current_act = (self.current_act + 1) % len(Config().activity)

                func.logger.info(f"Changed the bot status to {act_name}")

        except Exception as e:
            func.logger.error("Error occurred while changing the bot status!", exc_info=e)

    @tasks.loop(seconds=Config().timer_settings.get("cache_cleanup", 43200))
    async def cache_cleaner(self):
        await voicelink.MongoDBHandler.cleanup_cache()

async def setup(bot: commands.Bot):
    await bot.add_cog(Task(bot))