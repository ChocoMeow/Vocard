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
from __future__ import annotations

import discord

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from voicelink import Track

class SearchDropdown(discord.ui.Select):
    def __init__(self, tracks: list[Track], get_msg: callable) -> None:
        self.view: SearchView
        self.get_msg: callable = get_msg
        
        super().__init__(
            placeholder=get_msg('searchWait'),
            min_values=1, max_values=len(tracks),
            options=[
                discord.SelectOption(label=f"{i}. {track.title[:50]}", description=f"{track.author[:50]} · {track.formatted_length}")
                for i, track in enumerate(tracks, start=1)    
            ]
        )
        
    async def callback(self, interaction: discord.Interaction) -> None:
        self.disabled = True
        self.placeholder = self.get_msg('searchSuccess')
        await interaction.response.edit_message(view=self.view)
        self.view.values = self.values          
        self.view.stop()

class SearchView(discord.ui.View):
    def __init__(self, tracks: list[Track], lang: callable) -> None:
        super().__init__(timeout=60)

        self.response: discord.Message = None
        self.values: list[str] = None
        self.add_item(SearchDropdown(tracks, lang))

    async def on_error(self, error, item, interaction):
        return

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
        try:
            await self.response.edit(view=self)
        except:
            pass