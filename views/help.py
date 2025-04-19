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
from discord.ext import commands

import function as func

class HelpDropdown(discord.ui.Select):
    def __init__(self, categories:list):
        self.view: HelpView

        super().__init__(
            placeholder="Select Category!",
            min_values=1, max_values=1,
            options=[
                discord.SelectOption(emoji="<:March7thThumbsUp:1103668414758780979>", label="Main Page", description="The main page of help command."),
                discord.SelectOption(emoji="<a:March7thAniThumbsUp:1130036150124417104>", label="Tutorial", description="How to play music!"),
            ] + [
                discord.SelectOption(emoji=emoji, label=f"{category} Commands", description=f"This is {category.lower()} Category.")
                for category, emoji in zip(categorys, ["<:1_:1130243485480525905>", "<:2_:1130243518137372722>", "<:3_:1130243561535840356>", "<:4_:1130243603185279037>", "<:5_:1130243702770647192>", "<:6_:1130243647087058974>", "<:7_:1130243737759522857>"])
            ],
            custom_id="select"
        )
    
    async def callback(self, interaction: discord.Interaction) -> None:
        embed = self.view.build_embed(self.values[0].split(" ")[0])
        await interaction.response.edit_message(embed=embed)

class HelpView(discord.ui.View):
    def __init__(self, bot: commands.Bot, author: discord.Member) -> None:
        super().__init__(timeout=60)

        self.author: discord.Member = author
        self.bot: commands.Bot = bot
        self.response: discord.Message = None
        self.categories: list[str] = [ name.capitalize() for name, cog in bot.cogs.items() if len([c for c in cog.walk_commands()]) ]

        self.add_item(discord.ui.Button(label='Modmail Us!', emoji='<:Critter7th:1272886381395316797>', url='https://discord.com/channels/1094973844210581537/1094980390957101136/1273578324127383562'))
        self.add_item(discord.ui.Button(label='Join a music channnel!', emoji='<:March7thHeart:1115617412377755690>', url='https://discord.com/channels/1094973844210581537/1114577310851534888'))
        self.add_item(discord.ui.Button(label='Checkout Vocard', emoji='<:6969:1330398223805841438>', url='https://vocard.xyz'))
        self.add_item(HelpDropdown(self.categorys))

    
    async def on_error(self, error, item, interaction) -> None:
        return

    async def on_timeout(self) -> None:
        for child in self.children:
            if child.custom_id == "select":
                child.disabled = True
        try:
            await self.response.edit(view=self)
        except:
            pass

    async def interaction_check(self, interaction: discord.Interaction) -> None:
        return interaction.user == self.author

    def build_embed(self, category: str) -> discord.Embed:
        category = category.lower()
        if category == "news":
            update = "> A music bot made based on @vocard! Feel free to use the categories to navigate through the commands. If you have any questions, feel free to modmail us!"
            embed.add_field(name="― <:5_:1120660684087246928> How to get started?", value="> Join a voice channel and /play {Song/URL} a song. (Names, Youtube Video Links or Playlist links or Spotify links are supported on Vocard)", inline=False)
            embed.set_image(url="https://cdn.discordapp.com/attachments/1286005393155424316/1331836413221670912/Copy_of_Copy_of_March_7th4.png?ex=679310d1&is=6791bf51&hm=04f811495729772841b6e047efe963f60711f2f61cb23b7117ddc9545b85f197&")
            return embed

        embed = discord.Embed(title=f"Category: {category.capitalize()}", color=func.settings.embed_color)

        if category == 'tutorial':
            embed.description = "― <:5_:1120660684087246928> How to use the music bot?\n\n > Simply run `/play` while being in the https://discord.com/channels/1094973844210581537/1114577310851534888 channel!"
            embed.set_image(url="https://cdn.discordapp.com/attachments/1049762290183975026/1262796668546318346/3RTpoHX.png?ex=67930c4b&is=6791bacb&hm=654baeb847381eb0e9a276ab125761901db083f3e3b535701ab9e9261558b289&")

        else:
            cog = [c for _, c in self.bot.cogs.items() if _.lower() == category][0]

            commands = [command for command in cog.walk_commands()]
            embed.description = cog.description
            embed.add_field(
                name=f"{category} Commands: [{len(commands)}]",
                value="```{}```".format("".join(f"/{command.qualified_name}\n" for command in commands if not command.qualified_name == cog.qualified_name))
            )
            embed.set_image(url="https://cdn.discordapp.com/attachments/1049762290183975026/1262796668546318346/3RTpoHX.png?ex=67930c4b&is=6791bacb&hm=654baeb847381eb0e9a276ab125761901db083f3e3b535701ab9e9261558b289&")

        return embed