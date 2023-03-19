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

from function import formatTime

class Dropdown(discord.ui.Select):
    def __init__(self, player, chapters):

        self.player = player
        self.chapters = chapters
        self.current = player.current.uri
        
        options = [
            discord.SelectOption(label=f"{index}. {title[:30]}",
                                    description=time)
            for index, (time, title) in enumerate(self.chapters, start=1)
        ]
        
        super().__init__(
            placeholder=self.player.get_msg('chaptersDropdown'),
            min_values=1, max_values=1,
            options=options[:25],
        )

    async def callback(self, interaction: discord.Interaction):
        position = formatTime(self.chapters[int(self.values[0].split(". ")[0]) - 1][0])
        if position is None:
            return
        if not self.player.current or self.current != self.player.current.uri:
            return await self.view.stop_view()

        await self.player.seek(position)
        await interaction.response.send_message(self.player.get_msg('seek').format(formatTime(position)))

class ChapterView(discord.ui.View):
    def __init__(self, player, chapters, author):
        super().__init__(timeout=180)

        self.player = player
        self.chapters = chapters
        self.author = author
        self.response = None
        self.add_item(Dropdown(player, chapters))
    
    async def on_error(self, error: Exception, item, interaction) -> None:
        return 
    
    async def stop_view(self) -> None:
        for child in self.children:
            child.disabled = True
        try:
            await self.response.edit(view=self)
        except:
            pass

    async def on_timeout(self) -> None:
        await self.stop_view()
    
    async def interaction_check(self, interaction):
        if interaction.user == self.author:
            return True
        return False