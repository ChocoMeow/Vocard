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

import re
from typing import Optional

from discord import Member
from tldextract import extract

from .enums import SearchType
from function import (
    emoji_source,
    time as ctime
)

from .formatter import encode

YOUTUBE_REGEX = re.compile(r'(https?://)?(www\.)?youtube\.(com|nl)/watch\?v=([-\w]+)')
class Track:
    """The base track object. Returns critical track information needed for parsing by Lavalink.
       You can also pass in commands.Context to get a discord.py Context object in your track.
    """

    def __init__(
        self,
        *,
        track_id: str = None,
        info: dict,
        requester: Member,
        search_type: SearchType = SearchType.ytsearch,
        spotify_track = None,
    ):
        self.track_id = track_id
        self.info = info

        self.identifier = info.get("identifier")
        self.title = info.get("title", "Unknown")
        self.author = info.get("author", "Unknown")
        self.uri = info.get("uri", "https://discord.com/application-directory/605618911471468554")
        self.source = info.get("sourceName", extract(self.uri).domain)
        self.spotify = True if self.source == "spotify" else False
        if self.spotify:
            self.artistId: Optional[list] = info.get("artistId")

        self.original: Optional[Track] = None if self.spotify else self
        self._search_type = SearchType.ytmsearch if self.spotify else search_type
        self.spotify_track = spotify_track

        self.thumbnail = None
        
        self.emoji = emoji_source(self.source)
        
        if info.get("thumbnail"):
            self.thumbnail = info.get("thumbnail")
        elif YOUTUBE_REGEX.match(self.uri):
            self.thumbnail = f"https://img.youtube.com/vi/{self.identifier}/hqdefault.jpg"            

        if self.source == "soundcloud" and "/preview/" in self.identifier:
            self.length = 30000
        else:
            self.length = info.get("length")
        
        self.formatLength = ctime(self.length)
        self.requester = requester
        self.is_stream = info.get("isStream", False)
        self.is_seekable = info.get("isSeekable", True)
        self.position = info.get("position", 0)

        if not track_id:
            self.track_id = encode(self)
            
    def toDict(self):
        return {
            "track_id": self.track_id,
            "info": self.info,
            "thumbnail": self.thumbnail
        }
    
    def encode(self):
        return encode(self)
    
    def __eq__(self, other):
        if not isinstance(other, Track):
            return False

        return other.track_id == self.track_id

    def __str__(self):
        return self.title

    def __repr__(self):
        return f"<Voicelink.track title={self.title!r} uri=<{self.uri!r}> length={self.length}>"

class Playlist:
    """The base playlist object.
       Returns critical playlist information needed for parsing by Lavalink.
       You can also pass in commands.Context to get a discord.py Context object in your tracks.
    """

    def __init__(
        self,
        *,
        playlist_info: dict,
        tracks: list,
        requester: Member = None,
        spotify: bool = False,
        spotify_playlist = None
    ):
        self.playlist_info = playlist_info
        self.tracks_raw = tracks
        self.spotify = spotify
        self.name = playlist_info.get("name")
        self.spotify_playlist = spotify_playlist

        self._thumbnail = None
        self._uri = None
        
        if self.spotify:
            self.tracks = tracks
            self._thumbnail = self.spotify_playlist.image
            self._uri = self.spotify_playlist.uri
        else:
            self.tracks = [
                Track(track_id=track["track"], info=track["info"], requester=requester)
                for track in self.tracks_raw
            ]
            self._thumbnail = None
            self._uri = None

        self.track_count = len(self.tracks)

    def __str__(self):
        return self.name

    def __repr__(self):
        return f"<Voicelink.playlist name={self.name!r} track_count={len(self.tracks)}>"

    @property
    def uri(self) -> Optional[str]:
        """Spotify album/playlist URI, or None if not a Spotify object."""
        return self._uri

    @property
    def thumbnail(self) -> Optional[str]:
        """Spotify album/playlist thumbnail, or None if not a Spotify object."""
        return self._thumbnail
