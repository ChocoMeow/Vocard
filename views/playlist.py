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
from tldextract import extract

class Select_playlist(discord.ui.Select):
    def __init__(self, results):
        options = [discord.SelectOption(emoji='🌎', label='All Playlist')]
        for index, playlist in enumerate(results, start=1):
            if playlist['type'] != 'error':
                options.append(discord.SelectOption(emoji=playlist['emoji'], label=f'{index}. {playlist["name"]}', description=f"{playlist['time']} · {playlist['type']}"))

        super().__init__(
            placeholder="Select a playlist to view ..",
            options=options
        )
    
    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == 'All Playlist':
            self.view.current = None
            return await interaction.response.edit_message(embed=self.view.viewEmbed)
        self.view.current = self.view.results[int(self.values[0].split(". ")[0]) - 1]
        self.view.page = ceil(len(self.view.current['tracks']) / 7)
        self.view.current_page = 1
        await interaction.response.edit_message(embed=self.view.build_embed())

class agree(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Agree", style=discord.ButtonStyle.green)
    
    async def callback(self, interaction: discord.Interaction):
        self.label = "Created"
        self.disabled = True
        self.style=discord.ButtonStyle.primary
        embed = discord.Embed(description="Your account has been successfully created", color=0x55e27f)
        await interaction.response.edit_message(embed=embed, view=self.view)
        self.view.value = True
        self.view.stop()

class PlaylistView(discord.ui.View):
    def __init__(self, viewEmbed, results, author):
        super().__init__(timeout=60)
        self.viewEmbed = viewEmbed
        self.results = results
        self.author = author
        self.guildID = author.guild.id
        self.response = None

        self.current = None
        self.page = 0
        self.current_page = 1

        self.add_item(Select_playlist(results))

    async def interaction_check(self, interaction):
        if interaction.user == self.author:
            return True
        return False
    
    async def on_error(self, error, item, interaction):
        return

    def build_embed(self):
        offset = self.current_page * 7
        tracks = self.current['tracks'][(offset-7):offset]

        embed = discord.Embed(title=func.get_lang(self.guildID, 'playlistView'), color=func.settings.embed_color)

        embed.description= func.get_lang(self.guildID, 'playlistViewDesc').format(self.current['name'], self.current['id'], len(self.current['tracks']), owner if (owner := self.current.get('owner')) else f"{self.author.id} (You)", self.current['type'])
        
        perms = self.current['perms']
        permsStr = func.get_lang(self.guildID, 'settingsPermTitle')
        if self.current['type'] == 'share':
            embed.add_field(name=permsStr, value=func.get_lang(self.guildID, 'playlistViewPermsValue').format('✓' if 'write' in perms and self.author.id in perms['write'] else '✘', '✓' if 'remove' in perms and self.author.id in perms['remove'] else '✘'))
        else:
            embed.add_field(name=permsStr, value=func.get_lang(self.guildID, 'playlistViewPermsValue2').format(', '.join(f'<@{user}>' for user in perms['read'])))

        trackStr = func.get_lang(self.guildID, 'playlistViewTrack')
        if tracks:
            if self.current.get("type") == "playlist":    
                embed.add_field(name=trackStr, value="\n".join(f"{func.emoji_source(track['sourceName'])} `{index}.` `[{func.time(track['length'])}]` **{track['title'][:30]}**" for index, track in enumerate(tracks, start=offset - 6)), inline=False)
            else:
                embed.add_field(name=trackStr, value='\n'.join(f"{func.emoji_source(extract(track.info['uri']).domain)} `{index}.` `[{func.time(track.length)}]` **{track.title[:30]}** " for index, track in enumerate(tracks, start=offset - 6)), inline=False)
        else:
            embed.add_field(name=trackStr, value=func.get_lang(self.guildID, 'playlistNoTrack').format(self.current['name']), inline=False)

        embed.set_footer(text=func.get_lang(self.guildID, 'playlistViewPage').format(self.current_page, self.page, self.current['time']))

        return embed

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
        try:
            await self.response.edit(view=self)
        except:
            pass

    @discord.ui.button(label='<<', style=discord.ButtonStyle.grey)
    async def fast_back_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.current:
            return 
        if self.current_page != 1:
            self.current_page = 1
            await interaction.response.edit_message(embed=self.build_embed())
    
    @discord.ui.button(label='Back', style=discord.ButtonStyle.blurple)
    async def back_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.current:
            return 
        if self.current_page > 1:
            self.current_page -= 1
            await interaction.response.edit_message(embed=self.build_embed())
    
    @discord.ui.button(label='Next', style=discord.ButtonStyle.blurple)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.current:
            return 
        if self.current_page < self.page:
            self.current_page += 1
            await interaction.response.edit_message(embed=self.build_embed())

    @discord.ui.button(label='>>', style=discord.ButtonStyle.grey)
    async def fast_next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.current:
            return 
        if self.current_page != self.page:
            self.current_page = self.page
            await interaction.response.edit_message(embed=self.build_embed())

    @discord.ui.button(emoji='🗑️', style=discord.ButtonStyle.red)
    async def stop_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.response.delete()
        self.stop()

class CreateView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=20)
        self.value = None
        self.response = None
        self.add_item(agree())
        self.add_item(discord.ui.Button(label='Support', emoji=':support:915152950471581696', url=func.settings.invite_link))

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
        try:
            await self.response.edit(view=self)
        except:
            pass