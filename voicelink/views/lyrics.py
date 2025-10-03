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

from .utils import Pagination
from .pagination import PaginationView
from ..config import Config
from ..language import LangHandler

# class LyricsDropdown(discord.ui.Select):
#     def __init__(self, langs: list[str]) -> None:
#         self.view: LyricsView

#         super().__init__(
#             placeholder="Select A Lyrics Translation",
#             min_values=1, max_values=1,
#             options=[discord.SelectOption(label=lang) for lang in langs], 
#             custom_id="selectLyricsLangs"
#         )

#     async def callback(self, interaction: discord.Interaction) -> None:
#         self.view.lang = self.values[0]
#         self.view.current_page = 1
#         self.view.pages = len(self.view.source.get(self.values[0]))
#         await interaction.response.edit_message(embed=self.view.build_embed())

class LyricsView(PaginationView):
    def __init__(self, name: str, source: dict, author: discord.Member) -> None:
        self.name: str = name
        self.author: discord.Member = author
        self.response: discord.Message = None
        
        super().__init__(
            Pagination[str](source.get("default"), page_size=1),
            author
        )

    async def on_timeout(self) -> None:
        for child in self.children:
            child.disabled = True
        try:
            await self.response.edit(view=self)
        except:
            pass

    async def build_embed(self) -> discord.Embed:
        page = self.pagination.get_current_page_items()
        text = await LangHandler.get_lang(self.author.guild.id, "search.title")
        embed=discord.Embed(description=page[0], color=Config().embed_color)
        embed.set_author(name=text.format(self.name), icon_url=self.author.display_avatar.url)
        return embed
    
    async def update_message(self, interaction: discord.Interaction) -> None:
        """Update the view and edit the message."""
        self.update_view()

        if interaction.response.is_done():
            await interaction.followup.edit_message(self.response.id, embed=await self.build_embed(), view=self)
        else:
            await interaction.response.edit_message(embed=await self.build_embed(), view=self)