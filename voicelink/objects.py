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

from .spotify import Playlist as spPlaylist
from .formatter import encode

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
        "spotify",
        "artist_id",
        "original",
        "_search_type",
        "spotify_track",
        "thumbnail",
        "emoji",
        "length",
        "requester",
        "is_stream",
        "is_seekable",
        "position"
    )

    def __init__(
        self,
        *,
        track_id: str = None,
        info: dict,
        requester: Member,
        search_type: SearchType = SearchType.ytsearch,
        spotify_track = None,
    ):
        self._track_id: Optional[str] = track_id
        self.info: dict = info

        self.identifier: str = info.get("identifier")
        self.title: str = info.get("title", "Unknown")
        self.author: str = info.get("author", "Unknown")
        self.uri: str = info.get("uri", "https://discord.com/application-directory/605618911471468554")
        self.source: str = info.get("sourceName", extract(self.uri).domain)
        self.spotify: bool = self.source == "spotify"
        if self.spotify:
            self.artist_id: Optional[list] = info.get("artist_id")

        self.original: Optional[Track] = None if self.spotify else self
        self._search_type: SearchType = SearchType.ytsearch if self.spotify else search_type
        self.spotify_track: Track = spotify_track

        self.thumbnail: str = info.get("artworkUrl")
        if not self.thumbnail and YOUTUBE_REGEX.match(self.uri):
            self.thumbnail = f"https://img.youtube.com/vi/{self.identifier}/maxresdefault.jpg"
        
        self.emoji: str = get_source(self.source, "emoji")
        self.length: float = 3000 if self.source == "soundcloud" and "/preview/" in self.identifier else info.get("length")
        
        self.requester: Member = requester
        self.is_stream: bool = info.get("isStream", False)
        self.is_seekable: bool = info.get("isSeekable", True)
        self.position: int = info.get("position", 0)

    def __eq__(self, other) -> bool:
        if not isinstance(other, Track):
            return False

        return other.track_id == self.track_id

    def __str__(self) -> str:
        return self.title

    def __repr__(self) -> str:
        return f"<Voicelink.track title={self.title!r} uri=<{self.uri!r}> length={self.length}>"

    def toDict(self) -> dict:
        return {
            "track_id": self.track_id,
            "info": self.info,
            "thumbnail": self.thumbnail
        }

    @property
    def track_id(self) -> str:
        if not self._track_id:
            self._track_id = encode(self)
        
        return self._track_id
    
    @property
    def formatted_length(self) -> str:
        return ctime(self.length)
    
class Playlist:
    """The base playlist object.
       Returns critical playlist information needed for parsing by Lavalink.
       You can also pass in commands.Context to get a discord.py Context object in your tracks.
    """

    __slots__ = (
        "playlist_info",
        "tracks_raw",
        "spotify",
        "name",
        "spotify_playlist",
        "_thumbnail",
        "_uri",
        "tracks"
    )

    def __init__(
        self,
        *,
        playlist_info: dict,
        tracks: list,
        requester: Member = None,
        spotify: bool = False,
        spotify_playlist: Optional[spPlaylist] = None
    ):
        self.playlist_info: dict = playlist_info
        self.tracks_raw: list[Track] = tracks
        self.spotify: bool = spotify
        self.name: str = playlist_info.get("name")
        self.spotify_playlist: Optional[spPlaylist] = spotify_playlist

        self._thumbnail: str = None
        self._uri: str = None
        
        if self.spotify:
            self.tracks = tracks
            self._thumbnail = self.spotify_playlist.image
            self._uri = self.spotify_playlist.uri
        else:
            self.tracks = [
                Track(track_id=track["encoded"], info=track["info"], requester=requester)
                for track in self.tracks_raw
            ]
            self._thumbnail = None
            self._uri = None

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return f"<Voicelink.playlist name={self.name!r} track_count={len(self.tracks)}>"

    @property
    def uri(self) -> Optional[str]:
        """Spotify album/playlist URI, or None if not a Spotify object."""
        return self._uri

    @property
    def thumbnail(self) -> Optional[str]:
        """Spotify album/playlist thumbnail, or None if not a Spotify object."""
        return self._thumbnail

    @property
    def track_count(self) -> int:
        return len(self.tracks)
