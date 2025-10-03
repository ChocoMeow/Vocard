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


class BaseModal(discord.ui.Modal):
    def __init__(self, title: str, items: list[discord.ui.Item], timeout: float = None, custom_id: str = None) -> None:
        super().__init__(title=title, timeout=timeout, custom_id=custom_id)
        self._add_items(items)
        self.values: dict[str, str] = {}

    def _add_items(self, items: list[discord.ui.Item]) -> None:
        """Add items to the modal."""
        for item in items:
            self.add_item(item)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        """Handle the modal submission."""
        await interaction.response.defer()

        for item in self.walk_children():
            if isinstance(item, discord.ui.TextInput):
                self.values[item.custom_id] = item.value
