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

from typing import List, Generic, TypeVar
from math import ceil

T = TypeVar("T")


class Pagination(Generic[T]):
    """
    A class to manage pagination for a list of items.

    Attributes:
        items (List[T]): The list of items to paginate.
        page_size (int): The number of items per page.
        current_page (int): The current page index (0-based).
        total_pages (int): The total number of pages.
    """

    def __init__(self, items: List[T], page_size: int):
        """
        Initializes the Pagination class.

        Args:
            items (List[T]): The list of items to paginate.
            page_size (int): The number of items per page.

        Raises:
            ValueError: If page_size is less than or equal to 0.
        """
        if page_size <= 0:
            raise ValueError("page_size must be greater than 0")

        self._items: List[T] = items
        self._page_size: int = page_size
        self._current_page: int = 0
        self.total_pages: int = ceil(len(items) / page_size)

    def add_item(self, item: T) -> None:
        """
        Adds an item to the pagination and updates total pages.

        Args:
            item (T): The item to add.
        """
        self._items.append(item)
        self.total_pages = ceil(len(self._items) / self._page_size)
    
    def remove_item(self, item: T) -> None:
        """
        Removes an item from the pagination and updates total pages.

        Args:
            item (T): The item to remove.
        """
        self._items.remove(item)
        self.total_pages = ceil(len(self._items) / self._page_size)
        if self._current_page >= self.total_pages:
            self._current_page = max(0, self.total_pages - 1)
            
    def get_current_page_items(self) -> List[T]:
        """
        Retrieves the items for the current page.

        Returns:
            List[T]: The items on the current page.
        """
        return self._items[self.start_index:self.end_index]

    def go_back(self) -> None:
        """Moves to the previous page if available."""
        if self.has_previous_page:
            self._current_page -= 1

    def go_next(self) -> None:
        """Moves to the next page if available."""
        if self.has_next_page:
            self._current_page += 1

    def go_page(self, page_number: int) -> None:
        """
        Navigate to a specific page, clamped between 0 and total_pages.
        
        Args:
            page_number (int): The page number to navigate to (0-based).
        """
        self._current_page = max(0, min(page_number, self.total_pages - 1))

    @property
    def has_next_page(self) -> bool:
        """
        Checks if there is a next page.

        Returns:
            bool: True if there is a next page, False otherwise.
        """
        return self._current_page < self.total_pages - 1

    @property
    def has_previous_page(self) -> bool:
        """
        Checks if there is a previous page.

        Returns:
            bool: True if there is a previous page, False otherwise.
        """
        return self._current_page > 0

    @property
    def start_index(self) -> int:
        """
        Gets the start index of the items for the current page.

        Returns:
            int: The start index (0-based) of the current page.
        """
        return self._current_page * self._page_size

    @property
    def end_index(self) -> int:
        """
        Gets the end index of the items for the current page.

        Returns:
            int: The end index (exclusive) of the current page.
        """
        return min(self.start_index + self._page_size, len(self._items))

    @property
    def current_page(self) -> int:
        """
        Returns the current page number (1-based).

        Returns:
            int: The current page number, starting from 1.
        """
        return self._current_page + 1
    
    @property
    def total_items(self) -> int:
        """
        Gets the total number of items in the pagination.

        Returns:
            int: The total number of items across all pages.
        """
        return len(self._items)

    @property
    def items(self) -> List[T]:
        """
        Gets the list of all items in the pagination.

        Returns:
            List[T]: The list of all items.
        """
        return self._items