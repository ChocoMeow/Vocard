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
import unicodedata

from tldextract import extract
from discord.ext import commands
from typing import Any

from .utils import DynamicViewManager, Pagination
from .pagination import PaginationView
from ..config import Config
from ..utils import format_ms, truncate_string, dispatch_message
from ..mongodb import MongoDBHandler
from ..language import LangHandler
from ..exceptions import VoicelinkException

class PlaylistDropdown(discord.ui.Select):
    def __init__(self, results: list[dict[str, Any]], lang: str) -> None:
        self.view: PlaylistViewManager

        super().__init__(
            placeholder=LangHandler._get_lang(lang, "playlist.view.playlistSelect"),
            custom_id="selector",
            options=[
                discord.SelectOption(
                    emoji=playlist['emoji'],
                    label=f'{index}. {playlist["name"]}',
                    value=playlist["id"],
                    description=f"{playlist['time']} · {playlist['type']}"
                ) for index, playlist in enumerate(results, start=1) if playlist['type'] != 'error'
            ]
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        view: PlaylistView = self.view.change_view(self.values[0])
        await interaction.response.edit_message(embed=view.build_embed(), view=view)


class PlaylistView(PaginationView):
    def __init__(
        self,
        primary_view: "PlaylistViewManager",
        playlist_data: dict[str, Any]
    ) -> None:
        self.primary_view: PlaylistViewManager = primary_view
        self.author: discord.Member = primary_view.ctx.author

        self.playlist_id: str = playlist_data.get("id")
        self.emoji: str = playlist_data.get("emoji")
        self.name: str = playlist_data.get("name")
        self.time: str = playlist_data.get("time")
        self.type: str = playlist_data.get("type")
        self.owner_id: int = playlist_data.get("owner")
        self.perms: dict[str, list[int]] = playlist_data.get("perms")

        super().__init__(Pagination[dict[str, Any]](playlist_data.get("tracks"), page_size=7), primary_view.ctx.author)
    
    def build_embed(self) -> discord.Embed:
        """Build the embed for the current page of tracks."""
        tracks = self.pagination.get_current_page_items()
        texts = LangHandler._get_lang(
            self.primary_view.lang,
            "playlist.view.detailTitle", "playlist.view.detailDesc", "settings.permissions.title",
            "playlist.view.permsValue", "playlist.view.permsValue2",
            "playlist.view.trackList", "playlist.errors.noTrack", "playlist.view.footer2"
        )

        embed = discord.Embed(title=texts[0], color=Config().embed_color)
        embed.description = texts[1].format(
            self.name,
            self.playlist_id,
            self.pagination.total_items,
            self.primary_view.ctx.bot.get_user(self.owner_id),
            self.type.upper()
        ) + "\n"

        embed.description += texts[2] + "\n"
        if self.type == 'share':
            write_perm = '✓' if 'write' in self.perms and self.author.id in self.perms['write'] else '✘'
            remove_perm = '✓' if 'remove' in self.perms and self.author.id in self.perms['remove'] else '✘'
            embed.description += texts[3].format(write_perm, remove_perm)
        else:
            readable_users = ', '.join(f'<@{user}>' for user in self.perms['read'])
            embed.description += texts[4].format(readable_users)

        # Add track information
        embed.description += f"\n\n**{texts[5]}:**\n"
        if tracks:
            for index, track in enumerate(tracks, start=self.pagination.start_index + 1):
                if isinstance(track, dict):
                    source_emoji = Config().get_source_config(track['sourceName'], 'emoji')
                    track_info = f"{source_emoji} `{index:>2}.` `[{format_ms(track['length'])}]` [{truncate_string(track['title'])}]({track['uri']})"
                else:
                    source_emoji = Config().get_source_config(extract(track.info['uri']).domain, 'emoji')
                    track_info = f"{source_emoji} `{index:>2}.` `[{format_ms(track.length)}]` [{truncate_string(track.title)}]({track.uri})"
                embed.description += track_info + "\n"
        else:
            embed.description += texts[6].format(self.name)

        # Set the footer
        embed.set_footer(text=texts[7].format(self.time))
        return embed

    def update_view(self, extra_states = None):
        texts = LangHandler._get_lang(self.lang, "pagination.play", "pagination.share", "pagination.export", "pagination.delete")
        extra_states = {
            "play": {
                "label": texts[0],
            },
            "share": {
                "label": texts[1],
            },
            "export": {
                "label": texts[2],
            },
            "delete": {
                "label": texts[3],
            },
        }
        return super().update_view(extra_states)
    
    async def on_error(self, interaction: discord.Interaction, error: Exception, item: discord.ui.Item) -> None:
        if isinstance(error, VoicelinkException):
            return await dispatch_message(interaction, content=getattr(error, 'original', error), ephemeral=True)
    
    async def update_message(self, interaction: discord.Interaction) -> None:
        """Update the view and edit the message with the new embed."""
        self.update_view()

        if interaction.response.is_done():
            await interaction.followup.edit_message(self.primary_view.response.id, embed=self.build_embed(), view=self)
        else:
            await interaction.response.edit_message(embed=self.build_embed(), view=self)
            
    @discord.ui.button(label="<")
    async def back_to_home(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        """Return to the main playlist view."""
        view: PlaylistViewManager = self.primary_view.change_view("home")
        await interaction.response.edit_message(embed=view.build_embed(), view=view)
    
    @discord.ui.button(label="Play", custom_id="play", style=discord.ButtonStyle.green)
    async def play_all(self, interaction: discord.Interaction[commands.Bot], button: discord.ui.Button) -> None:
        await interaction.response.defer()
        cmd = interaction.client.get_command("playlist play")
        await cmd(self.primary_view.ctx, self.name)
    
    @discord.ui.button(label="Share", custom_id="share", style=discord.ButtonStyle.gray)
    async def share(self, interaction: discord.Interaction[commands.Bot], button: discord.ui.Button) -> None:
        await interaction.response.defer()

    @discord.ui.button(label="Export", custom_id="export", style=discord.ButtonStyle.gray)
    async def export(self, interaction: discord.Interaction[commands.Bot], button: discord.ui.Button) -> None:
        await interaction.response.defer()
        cmd = interaction.client.get_command("playlist export")
        await cmd(self.primary_view.ctx, self.name)

    @discord.ui.button(label="Delete", custom_id="delete", style=discord.ButtonStyle.red)
    async def delete(self, interaction: discord.Interaction[commands.Bot], button: discord.ui.Button) -> None:
        await interaction.response.defer()
        cmd = interaction.client.get_command("playlist delete")
        await cmd(self.primary_view.ctx, name=self.name)
        
        if self.playlist_id != "200":
            view: PlaylistViewManager = self.primary_view.change_view("home")
            view.results = [item for item in view.results if item.get("id") != self.playlist_id]
            view.clear_items()
            view.add_item(PlaylistDropdown(view.results, view.lang))
            self.primary_view.remove_view(self.playlist_id)
            await view.response.edit(embed=view.build_embed(), view=view)

class PlaylistViewManager(DynamicViewManager):
    def __init__(self, ctx: commands.Context, results: list[dict[str, Any]]):
        self.ctx: commands.Context[commands.Bot] = ctx
        self.results: list[dict[str, Any]] = results
        self.lang: str = MongoDBHandler.get_cached_settings(ctx.guild.id).get("lang")
        
        views = {"home": self}
        views.update({result["id"]: PlaylistView(self, result) for result in results})
        
        super().__init__(views=views, timeout=None)

        self.response: discord.Message = None
        self.add_item(PlaylistDropdown(results, self.lang))

    async def on_timeout(self) -> None:
        for view in self._views.values():
            view.stop()

        for child in self.current_view.children:
            child.disabled = True

        try:
            await self.response.edit(view=self)
        except:
            pass

    def get_width(self, s):
        width = 0
        for char in str(s):
            if unicodedata.east_asian_width(char) in ('F', 'W'):
                width += 2
            else:
                width += 1
        return width
    
    def pad_string(self, s, width):
        s = str(s)
        current_width = self.get_width(s)
        padding = width - current_width
        return s + " " * padding
    
    def build_embed(self) -> discord.Embed:
        """
        Build the embed for the playlist overview.
        
        Returns:
            discord.Embed: The constructed embed with playlist details.
        """
        max_p, _, _ = Config().get_playlist_config()
        text = LangHandler._get_lang(self.lang, "playlist.view.title", "playlist.view.headers", "playlist.view.footer")
        
        headers = text[1].split(",")
        headers.insert(0, "")
        content = [headers]

        description = ""
        for index in range(max_p):
            info = self.results[index] if index < len(self.results) else {}
            if info:
                content.append([
                    info.get('emoji', '  '),
                    info.get('id', "-" * 3),
                    f"[{info.get('time', '--:--')}]",
                    truncate_string(info.get('name', "-" * 6), 12),
                    len(info.get('tracks', []))
                ])

        column_widths = [max(self.get_width(str(item)) for item in column) for column in zip(*content)]

        for row in content:
            formatted_row = "   ".join(self.pad_string(item, width) for item, width in zip(row, column_widths))
            description += formatted_row + "\n"
            
        embed = discord.Embed(
            description=f'```{description}```',
            color=Config().embed_color
        )

        embed.set_author(
            name=text[0].format(self.ctx.author.display_name),
            icon_url=self.ctx.author.display_avatar.url
        )
        embed.set_footer(text=text[2])
        return embed