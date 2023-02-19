"""MIT License

Copyright (c) 2023 Vocard Development

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
from discord.ext import commands

from os import getenv
import function

class HelpDropdown(discord.ui.Select):
    def __init__(self, category:list):
        options = [
            discord.SelectOption(emoji="🆕", label="News", description="View new updates of Vocard."),
            discord.SelectOption(emoji="🕹️", label="Tutorial", description="How to use Vocard."),
        ]
        cog_emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣"]
        for category, emoji in zip(category, cog_emojis):
            options.append(discord.SelectOption(emoji=emoji, 
                                                label=f"{category} Commands",
                                                description=f"This is {category} Category."))
    
        super().__init__(
            placeholder="Select Category!",
            min_values=1, max_values=1,
            options=options, custom_id="select"
        )
    
    async def callback(self, interaction: discord.Interaction):
        embed = self.view.build_embed(self.values[0].split(" ")[0])
        await interaction.response.edit_message(embed=embed)

class HelpView(discord.ui.View):
    def __init__(self, bot: commands.Bot, author: discord.Member):
        super().__init__(timeout=60)

        self.author = author
        self.bot = bot
        self.response = None
        self.categorys = [ category.capitalize() for category in bot.cogs if category not in ["Task", "Nodes"] ]

        self.add_item(discord.ui.Button(label='Support', emoji=':support:915152950471581696', url=function.invite_link))
        self.add_item(discord.ui.Button(label='Invite', emoji=':invite:915152589056790589', url='https://discord.com/oauth2/authorize?client_id={}&permissions=2184260928&scope=bot%20applications.commands'.format(getenv('CLIENT_ID'))))
        self.add_item(discord.ui.Button(label='Github', url='https://github.com/ChocoMeow/Vocard'))
        self.add_item(discord.ui.Button(label='Donate', emoji=':patreon:913397909024800878', url='https://www.patreon.com/Vocard'))
        self.add_item(HelpDropdown(self.categorys))
    
    async def on_error(self, error, item, interaction):
        return

    async def on_timeout(self):
        for child in self.children:
            if child.custom_id == "select":
                child.disabled = True
        try:
            await self.response.edit(view=self)
        except:
            pass

    async def interaction_check(self, interaction):
        if interaction.user == self.author:
            return True
        return False

    def build_embed(self, category: str):
        category = category.lower()
        if category == "news":
            embed = discord.Embed(title="Vocard Help Menu", url="https://discord.com/channels/811542332678996008/811909963718459392/1069971173116481636", color=function.embed_color)

            embed.add_field(name=f"Available Categories: [{2 + len(self.categorys)}]",
                            value="```py\n👉 News\n2. Tutorial\n{}```".format("".join(f"{i}. {c}\n" for i, c in enumerate(self.categorys, start=3))),
                            inline=True)

            update = "> Update Contents\n" \
                     "➥ More text support for other languages\n" \
                     "➥ Add author name in playing track msg\n" \
                     "➥ Fixed some commands\n\n" \
                     "[Click Me For More Info](https://discord.com/channels/811542332678996008/811909963718459392/1063728318777671741)" \

            embed.add_field(name="📰 Latest News <t:1661168201:d> (<t:1661168201:R>)", value=update, inline=True)
            embed.add_field(name="Get Started", value="```Join a voice channel and /play {Song/URL} a song. (Names, Youtube Video Links or Playlist links or Spotify links are supported on Vocard)```", inline=False)
            
            return embed

        embed = discord.Embed(title=f"Category: {category}", color=function.embed_color)
        embed.add_field(name=f"Categories: [{2 + len(self.categorys)}]", value="```py\n" + "\n".join(f"👉 {c}" if c == category else f"{i}. {c}" for i, c in enumerate(['News', 'Tutorial'] + self.categorys, start=1)) + "```", inline=True)

        if category == 'tutorial':
            embed.description = "How can use Vocard? Some simple commands you should know now after watching this video."
            embed.set_image(url="https://cdn.discordapp.com/attachments/674788144931012638/917656288899514388/final_61aef3aa7836890135c6010c_669380.gif")
        else:
            cog = [c for _, c in self.bot.cogs.items() if _ == category][0]

            commands = [command for command in cog.walk_commands()]
            embed.description = cog.description
            embed.add_field(name=f"{category} Commands: [{len(commands)}]",
                            value="```{}```".format("".join(f"/{command.qualified_name}\n" for command in commands if not command.qualified_name == cog.qualified_name)))

        return embed