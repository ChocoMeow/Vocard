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

from .utils import Pagination, BaseModal
from .pagination import PaginationView

from ..language import LangHandler
from ..config import Config
from ..utils import format_ms, truncate_string

if TYPE_CHECKING:
    from ..player import Player
    from ..objects import Track

class QueueView(PaginationView):
    """
    A Discord UI view for displaying and interacting with a paginated list of tracks.

    Attributes:
        player (Player): The player containing the track queue or history.
        author (discord.Member): The member who initiated the view.
        is_queue (bool): Indicates if the list is a queue or history.
        pagination (Pagination[Track]): Manages pagination of track lists.
        response (discord.Message): The message containing the view.
        total_duration (str): The total duration of the tracks.
    """

    def __init__(self, player: "Player", author: discord.Member, is_queue: bool = True) -> None:
        
        self.player: Player = player
        self.is_queue: bool = is_queue
        self.total_duration = self.calculate_total_duration()
        self.response: discord.Message = None

        super().__init__(
            Pagination[Track](
                items=player.queue.tracks() if is_queue else list(reversed(player.queue.history())),
                page_size=7,
            ),
            author
        )

    def calculate_total_duration(self) -> str:
        """Calculate the total duration of the tracks."""
        try:
            return format_ms(sum(track.length for track in self.pagination._items))
        except Exception:
            return "∞"

    def format_description(self, tracks: list["Track"], texts: list[str]) -> str:
        """Format the description for the embed based on current tracks."""
        now_playing = (
            texts[1].format(self.player.current.uri,
                            f"```{self.player.current.title}```")
            if self.player.current else texts[2].format("None")
        )

        track_list = "\n".join([
            f"{track.emoji} `{i:>2}.` `[{texts[3] if track.is_stream else format_ms(track.length)}]` "
            f"[{truncate_string(track.title)}]({track.uri}) {track.requester.mention}"
            for i, track in enumerate(tracks, start=self.pagination.start_index + 1)
        ])

        return f"{now_playing}\n**{texts[4] if self.is_queue else texts[5]}**\n{track_list}"

    async def on_timeout(self) -> None:
        """Disable all buttons when the view times out."""
        for child in self.children:
            child.disabled = True
        try:
            await self.response.edit(view=self)
        except discord.HTTPException:
            pass
        
    async def build_embed(self) -> discord.Embed:
        """Build the embed for the current page of tracks."""
        tracks = self.pagination.get_current_page_items()
        texts = await LangHandler.get_lang(
            self.author.guild.id,
            "queue.view.title",
            "queue.view.desc",
            "player.playback.nowplayingDesc",
            "common.status.live",
            "queue.management.title",
            "queue.view.historyTitle",
            "playlist.view.footer2",
        )

        embed = discord.Embed(title=texts[0], color=Config().embed_color)
        embed.description = self.format_description(tracks, texts)
        
        if self.player.current:
            embed.set_thumbnail(url=self.player.current.thumbnail)
            
        embed.set_footer(text=texts[6].format(self.total_duration))

        return embed

    async def update_message(self, interaction: discord.Interaction) -> None:
        """Update the view and edit the message with the new embed."""
        super().update_view()

        if interaction.response.is_done():
            await interaction.followup.edit_message(self.response.id, embed=await self.build_embed(), view=self)
        else:
            await interaction.response.edit_message(embed=await self.build_embed(), view=self)