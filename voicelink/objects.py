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

import re
from typing import Optional

from discord import Member
from tldextract import extract

from .enums import SearchType
from function import (
    get_source,
    time as ctime
)

from .transformer import encode

YOUTUBE_REGEX = re.compile(r'(https?://)?(www\.)?youtube\.(com|nl)/watch\?v=([-\w]+)')

class Track:
    """The base track object. Returns critical track information needed for parsing by Lavalink.
       You can also pass in commands.Context to get a discord.py Context object in your track.
    """

    __slots__ = (
        "_track_id",
        "info",
        "identifier",
        "title",
        "author",
        "uri",
        "source",
        "_search_type",
        "thumbnail",
        "emoji",
        "length",
        "requester",
        "is_stream",
        "is_seekable",
        "position",
        "end_time"
    )

    def __init__(
        self,
        *,
        track_id: str = None,
        info: dict,
        requester: Member,
        search_type: SearchType = SearchType.YOUTUBE,
    ):
        self._track_id: Optional[str] = track_id
        self.info: dict = info

        self.identifier: str = info.get("identifier")
        self.title: str = info.get("title", "Unknown")
        self.author: str = info.get("author", "Unknown")
        self.uri: str = info.get("uri", "https://discord.com/application-directory/605618911471468554")
        self.source: str = info.get("sourceName", extract(self.uri).domain)
        self._search_type: SearchType = search_type

        self.thumbnail: str = info.get("artworkUrl")
        if not self.thumbnail and YOUTUBE_REGEX.match(self.uri):
            self.thumbnail = f"https://img.youtube.com/vi/{self.identifier}/maxresdefault.jpg"
        
        self.emoji: str = get_source(self.source, "emoji")
        self.length: float = info.get("length")
        
        self.requester: Member = requester
        self.is_stream: bool = info.get("isStream", False)
        self.is_seekable: bool = info.get("isSeekable", True)
        self.position: int = info.get("position", 0)

        self.end_time: Optional[int] = None

    def __eq__(self, other) -> bool:
        if not isinstance(other, Track):
            return False

        return other.track_id == self.track_id

    def __str__(self) -> str:
        return self.title

    def __repr__(self) -> str:
        return f"<Voicelink.track title={self.title!r} uri=<{self.uri!r}> length={self.length}>"

    @property
    def track_id(self) -> str:
        if not self._track_id:
            self._track_id = encode(self.info)
        
        return self._track_id
    
    @property
    def formatted_length(self) -> str:
        return ctime(self.length)
    
    @property
    def data(self) -> dict:
        return {
            "track_id": self.track_id,
            "requester_id": self.requester.id
        }
    
class Playlist:
    """The base playlist object.
       Returns critical playlist information needed for parsing by Lavalink.
       You can also pass in commands.Context to get a discord.py Context object in your tracks.
    """

    __slots__ = (
        "playlist_info",
        "name",
        "thumbnail",
        "uri",
        "tracks"
    )

    def __init__(
        self,
        *,
        playlist_info: dict,
        tracks: list,
        requester: Member = None,
    ):
        self.playlist_info: dict = playlist_info
        self.name: str = playlist_info.get("name")
        self.thumbnail: str = None
        self.uri: str = None
        
        self.tracks = [
            Track(track_id=track["encoded"], info=track["info"], requester=requester)
            for track in tracks
        ]

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return f"<Voicelink.playlist name={self.name!r} track_count={len(self.tracks)}>"

    @property
    def track_count(self) -> int:
        return len(self.tracks)
