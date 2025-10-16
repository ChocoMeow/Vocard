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

from enum import Enum, auto

class LoopType(Enum):
    """The enum for the different loop types for Voicelink

        LoopType.OFF: 1
        LoopType.TRACK: 2
        LoopType.QUEUE: 3

    """
    
    OFF = auto()
    TRACK = auto()
    QUEUE = auto()
    
class SearchType(Enum):
    """Enum representing different search types for Voicelink.

    Each search type corresponds to a specific platform that can be used 
    for retrieving audio or video content. The options available are:

    - SearchType.YOUTUBE: 
      Searches using regular YouTube, ideal for all scenarios.
    
    - SearchType.YOUTUBE_MUSIC: 
      Searches using YouTube Music, best for obtaining audio-only results.
    
    - SearchType.SPOTIFY: 
      Searches using Spotify, a viable alternative to YouTube and YouTube Music.
    
    - SearchType.SOUNDCLOUD: 
      Searches using SoundCloud, another alternative to YouTube and YouTube Music.
    
    - SearchType.APPLE_MUSIC: 
      Searches using Apple Music, offering a different option for audio content.
    
    - SearchType.DEEZER: 
      Searches using Deezer, providing another music streaming alternative.
    
    - SearchType.YANDEX_MUSIC: 
      Searches using Yandex Music, catering to users in the Yandex ecosystem.
    
    - SearchType.VK_MUSIC: 
      Searches using VK Music, popular in certain regions for music streaming.
    
    - SearchType.TIDAL: 
      Searches using Tidal, known for high-fidelity music streaming.
    
    - SearchType.QOBUZ: 
      Searches using Qobuz, recognized for high-resolution audio.
    
    - SearchType.JIOSAAVN: 
      Searches using JioSaavn, a popular platform in India for music streaming.
    """
    
    YOUTUBE = "ytsearch"
    YOUTUBE_MUSIC = "ytmsearch"
    SPOTIFY = "spsearch"
    SOUNDCLOUD = "scsearch"
    APPLE_MUSIC = "amsearch"
    DEEZER = "dzsearch"
    YANDEX_MUSIC = "ymsearch"
    VK_MUSIC = "vksearch"
    TIDAL = "tdsearch"
    QOBUZ = "qbsearch"
    JIOSAAVN = "jssearch"

    def __str__(self) -> str:
        return self.value
    
    @classmethod
    def from_platform(cls, value: str):
        """find an enum based on a search string."""
        normalized_value = value.lower().replace("_", "").replace(" ", "")

        for member in cls:
            normalized_name = member.name.lower().replace("_", "")
            if member.value == value or normalized_name == normalized_value:
                return member
        return None

    @property
    def display_name(self) -> str:
        return self.name.replace("_", " ").title()

class TrackRecType(Enum):
    """Enum representing track recommendation key formats for various platforms.

    Each key format is used to generate a recommendation link or identifier
    for a given track ID on the respective platform.

    - RecommendationType.SPOTIFY:
      Generates a Spotify recommendation key in the format 'sprec:mix:track:{track_id}'.

    - RecommendationType.YOUTUBE:
      Generates a YouTube recommendation URL with a playlist context.
      
    - RecommendationType.YOUTUBE_MUSIC:
      Same as YouTube, generates a YouTube Music recommendation URL.
      
    - RecommendationType.DEEZER:
      Generates a Deezer recommendation key in the format 'dzrec:{track_id}'.
      
    - RecommendationType.YANDEX_MUSIC:
      Generates a Yandex Music recommendation key in the format 'ymrec:{track_id}'.
    
    - RecommendationType.VK_MUSIC:
      Generates a VK Music recommendation key in the format 'vkrec:{track_id}'.
    
    - RecommendationType.TIDAL:
      Generates a Tidal recommendation key in the format 'tdrec:{track_id}'.
    
    - RecommendationType.QOBUZ:
      Generates a Qobuz recommendation key in the format 'qbrec:{track_id}'.
    
    - RecommendationType.JIOSAAVN:
      Generates a JioSaavn recommendation key in the format 'jsrec:{track_id}'
    """

    YOUTUBE = "https://www.youtube.com/watch?v={track_id}&list=RD{track_id}"
    YOUTUBE_MUSIC = YOUTUBE
    SPOTIFY = "sprec:mix:track:{track_id}"
    DEEZER = "dzrec:{track_id}"
    YANDEX_MUSIC = "ymrec:{track_id}"
    VK_MUSIC = "vkrec:{track_id}"
    TIDAL = "tdrec:{track_id}"
    QOBUZ = "qbrec:{track_id}"
    JIOSAAVN = "jsrec:{track_id}"

    def __str__(self) -> str:
        return self.name

    def format(self, track_id: str) -> str:
        """Format the recommendation key using the provided track ID.
        
        Args:
            track_id (str): The ID of the track to format.
        
        Returns:
            str: The formatted recommendation link.
        """
        return self.value.format(track_id=track_id)

    @classmethod
    def from_platform(cls, platform: str) -> 'TrackRecType':
        """Find the enum member based on a platform name.
        
        Args:
            platform (str): The name of the platform.
        
        Returns:
            TrackRecType: The corresponding enum member, or None if not found.
        """
        normalized = platform.lower().replace("_", "").replace(" ", "")
        for member in cls:
            if member.name.lower().replace("_", "") == normalized:
                return member
            
        return None
      
class RequestMethod(Enum):
    """The enum for the different request methods in Voicelink
    """
    GET = "get"
    PATCH = "patch"
    DELETE = "delete"
    POST = "post"

    def __str__(self) -> str:
        return self.value
    
class NodeAlgorithm(Enum):
    """The enum for the different node algorithms in Voicelink.
    
        The enums in this class are to only differentiate different
        methods, since the actual method is handled in the
        get_best_node() method.

        NodeAlgorithm.by_ping returns a node based on it's latency,
        preferring a node with the lowest response time

        NodeAlgorithm.by_region returns a node based on its voice region,
        which the region is specified by the user in the method as an arg. 
        This method will only work if you set a voice region when you create a node.
    """

    # We don't have to define anything special for these, since these just serve as flags
    BY_PING = auto()
    BY_REGION = auto()
    BY_PLAYERS = auto()

    def __str__(self) -> str:
        return self.value