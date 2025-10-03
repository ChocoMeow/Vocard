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


class DynamicViewManager(discord.ui.View):
    def __init__(self, views: dict[str, discord.ui.View], *, timeout: float = 180):
        """A manager for multiple dynamic views."""
        super().__init__(timeout=timeout)

        self._views: dict[str, discord.ui.View] = views
        self._current_view: discord.ui.View | None = None

    def add_view(self, name: str, view: discord.ui.View) -> None:
        """
        Add a view to the manager.
        
        Args:
            name (str): The name of the view.
            view (discord.ui.View): The view instance to add.
        """
        if name in self._views:
            raise ValueError(f"A view with the name '{name}' already exists.")

        self._views[name] = view

    def get_view(self, key: str) -> discord.ui.View | None:
        """
        Get a view from the manager.
        
        Args:
            key (str): The name of the view to retrieve.
        
        Returns:
            discord.ui.View | None: The requested view or None if not found.
        """
        return self._views.get(key)

    def remove_view(self, key: str) -> None:
        """
        Remove a view from the manager.
        
        Args:
            key (str): The name of the view to remove.
        """
        if key in self._views:
            del self._views[key]

    def change_view(self, name: str) -> discord.ui.View:
        """
        Change the current active view.
        
        Args:
            name (str): The name of the view to switch to.
            
        Returns:
            discord.ui.View: The newly activated view.
        """
        view = self.get_view(name)
        if not view:
            raise ValueError(f"No view found with the name '{name}'.")
        
        self._current_view = view
        return view

    @property
    def current_view(self) -> discord.ui.View | None:
        """Get the current active view."""
        return self._current_view
