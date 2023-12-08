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
import function as func

from math import ceil
from tldextract import extract
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from voicelink import Track

class Select_playlist(discord.ui.Select):
    def __init__(self, results):
        self.view: PlaylistView

        super().__init__(
            placeholder="Select a playlist to view ..",
            options=[discord.SelectOption(emoji='🌎', label='All Playlist')] + 
                [
                    discord.SelectOption(emoji=playlist['emoji'], label=f'{index}. {playlist["name"]}', description=f"{playlist['time']} · {playlist['type']}") 
                    for index, playlist in enumerate(results, start=1) if playlist['type'] != 'error'
                ]
        )
    
    async def callback(self, interaction: discord.Interaction) -> None:
        if self.values[0] == 'All Playlist':
            self.view.current = None
            return await interaction.response.edit_message(embed=self.view.viewEmbed)
        
        self.view.current = self.view.results[int(self.values[0].split(". ")[0]) - 1]
        self.view.page = ceil(len(self.view.current['tracks']) / 7)
        self.view.current_page = 1
        await interaction.response.edit_message(embed=self.view.build_embed())

class agree(discord.ui.Button):
    def __init__(self) -> None:
        self.view: CreateView
        super().__init__(label="Agree", style=discord.ButtonStyle.green)
    
    async def callback(self, interaction: discord.Interaction) -> None:
        self.label = "Created"
        self.disabled = True
        self.style=discord.ButtonStyle.primary
        embed = discord.Embed(description="Your account has been successfully created", color=0x55e27f)
        await interaction.response.edit_message(embed=embed, view=self.view)
        self.view.value = True
        self.view.stop()

class PlaylistView(discord.ui.View):
    def __init__(
            self,
            viewEmbed: discord.Embed,
            results: list[dict[str, Any]],
            author: discord.Message
    ) -> None:
        super().__init__(timeout=60)

        self.viewEmbed: discord.Embed = viewEmbed
        self.results: list[dict[str, Any]] = results
        self.author: discord.Member = author
        self.response: discord.Message = None

        self.current: dict[str, Any] = None
        self.page: int = 0
        self.current_page: int = 1

        self.add_item(Select_playlist(results))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user == self.author
    
    async def on_error(self, error, item, interaction) -> None:
        return

    def build_embed(self) -> discord.Embed:
        offset: int = self.current_page * 7
        tracks: list[Track] = self.current['tracks'][(offset-7):offset]
        guild_id = self.author.id

        embed = discord.Embed(title=func.get_lang(guild_id, 'playlistView'), color=func.settings.embed_color)

        embed.description= func.get_lang(guild_id, 'playlistViewDesc').format(self.current['name'], self.current['id'], len(self.current['tracks']), owner if (owner := self.current.get('owner')) else f"{self.author.id} (You)", self.current['type'])
        
        perms = self.current['perms']
        permsStr = func.get_lang(guild_id, 'settingsPermTitle')
        if self.current['type'] == 'share':
            embed.add_field(name=permsStr, value=func.get_lang(guild_id, 'playlistViewPermsValue').format('✓' if 'write' in perms and self.author.id in perms['write'] else '✘', '✓' if 'remove' in perms and self.author.id in perms['remove'] else '✘'))
        else:
            embed.add_field(name=permsStr, value=func.get_lang(guild_id, 'playlistViewPermsValue2').format(', '.join(f'<@{user}>' for user in perms['read'])))

        trackStr = func.get_lang(guild_id, 'playlistViewTrack')
        if tracks:
            if self.current.get("type") == "playlist":    
                embed.add_field(name=trackStr, value="\n".join(f"{func.emoji_source(track['sourceName'])} `{index}.` `[{func.time(track['length'])}]` **{track['title'][:30]}**" for index, track in enumerate(tracks, start=offset - 6)), inline=False)
            else:
                embed.add_field(name=trackStr, value='\n'.join(f"{func.emoji_source(extract(track.info['uri']).domain)} `{index}.` `[{func.time(track.length)}]` **{track.title[:30]}** " for index, track in enumerate(tracks, start=offset - 6)), inline=False)
        else:
            embed.add_field(name=trackStr, value=func.get_lang(guild_id, 'playlistNoTrack').format(self.current['name']), inline=False)

        embed.set_footer(text=func.get_lang(guild_id, 'playlistViewPage').format(self.current_page, self.page, self.current['time']))

        return embed

    async def on_timeout(self) -> None:
        for child in self.children:
            child.disabled = True
        try:
            await self.response.edit(view=self)
        except:
            pass

    @discord.ui.button(label='<<', style=discord.ButtonStyle.grey)
    async def fast_back_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not self.current:
            return 
        if self.current_page != 1:
            self.current_page = 1
            return await interaction.response.edit_message(embed=self.build_embed())
        await interaction.response.defer()

    @discord.ui.button(label='Back', style=discord.ButtonStyle.blurple)
    async def back_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not self.current:
            return 
        if self.current_page > 1:
            self.current_page -= 1
            return await interaction.response.edit_message(embed=self.build_embed())
        await interaction.response.defer()

    @discord.ui.button(label='Next', style=discord.ButtonStyle.blurple)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not self.current:
            return 
        if self.current_page < self.page:
            self.current_page += 1
            return await interaction.response.edit_message(embed=self.build_embed())
        await interaction.response.defer()

    @discord.ui.button(label='>>', style=discord.ButtonStyle.grey)
    async def fast_next_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not self.current:
            return 
        if self.current_page != self.page:
            self.current_page = self.page
            return await interaction.response.edit_message(embed=self.build_embed())
        await interaction.response.defer()

    @discord.ui.button(emoji='🗑️', style=discord.ButtonStyle.red)
    async def stop_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self.response.delete()
        self.stop()

class CreateView(discord.ui.View):
    def __init__(self) -> None:
        super().__init__(timeout=20)
        self.value: bool = None
        self.response: discord.Message = None

        self.add_item(agree())
        self.add_item(discord.ui.Button(label='Support', emoji=':support:915152950471581696', url=func.settings.invite_link))

    async def on_timeout(self) -> None:
        for child in self.children:
            child.disabled = True
        try:
            await self.response.edit(view=self)
        except:
            pass