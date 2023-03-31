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
import function as func

from math import ceil

class ListView(discord.ui.View):
    def __init__(self, player, author, isQueue = True):
        super().__init__(timeout=60)
        self.player = player

        self.name = player.get_msg('queueTitle') if isQueue else player.get_msg('historyTitle')
        self.tracks = player.queue.tracks() if isQueue else player.queue.history()
        if not isQueue:
            self.tracks.reverse()
        self.author = author

        self.page = ceil(len(self.tracks) / 7)
        self.current_page = 1
        try:
            self.time = func.time(sum([track.length for track in self.tracks]))
        except:
            self.time = "∞"
    
    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
        try:
            await self.response.edit(view=self)
        except:
            pass 

    async def on_error(self, error, item, interaction):
        return
    
    async def interaction_check(self, interaction):
        if interaction.user == self.author:
            return True
        return False

    def build_embed(self):
        offset = self.current_page * 7
        tracks = self.tracks[(offset-7):offset]

        embed = discord.Embed(title=self.player.get_msg('viewTitle'), color=func.settings.embed_color)
        embed.description=self.player.get_msg('viewDesc').format(self.player.current.uri, f"```{self.player.current.title}```") if self.player.current else self.player.get_msg('nowplayingDesc').format("None")
        queueText = ""
        for index, track in enumerate(tracks, start=offset - 6):
            queueText += f"{track.emoji} `{index}.` `[" + (self.player.get_msg("live") if track.is_stream else func.time(track.length)) + f'`] **{track.title[:30]}** ' + (track.requester.mention if track.requester else self.player.client.id) + "\n"
        
        embed.add_field(name=self.name, value=queueText) 
        embed.set_footer(text=self.player.get_msg('viewFooter').format(self.current_page, self.page, self.time))

        return embed

    @discord.ui.button(label='<<', style=discord.ButtonStyle.grey)
    async def fast_back_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page != 1:
            self.current_page = 1
            await interaction.response.edit_message(embed=self.build_embed())
    
    @discord.ui.button(label='Back', style=discord.ButtonStyle.blurple)
    async def back_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page > 1:
            self.current_page -= 1
            await interaction.response.edit_message(embed=self.build_embed())
    
    @discord.ui.button(label='Next', style=discord.ButtonStyle.blurple)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page < self.page:
            self.current_page += 1
            await interaction.response.edit_message(embed=self.build_embed())

    @discord.ui.button(label='>>', style=discord.ButtonStyle.grey)
    async def fast_next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page != self.page:
            self.current_page = self.page
            await interaction.response.edit_message(embed=self.build_embed())

    @discord.ui.button(emoji='🗑️', style=discord.ButtonStyle.red)
    async def stop_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.response.delete()
        self.stop()