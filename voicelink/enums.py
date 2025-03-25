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
    """The enum for the different search types for Voicelink.

       SearchType.YOUTUBE searches using regular Youtube,
       which is best for all scenarios.

       SearchType.YOUTUBE_MUSIC searches using YouTube Music,
       which is best for getting audio-only results.
       
       SearchType.SPOTIFY searches using Spotify,
       which is an alternative to YouTube or YouTube Music.

       SearchType.SOUNDCLOUD searches using SoundCloud,
       which is an alternative to YouTube or YouTube Music.

       SearchType.APPLE_MUSIC searches using Apple Music,
       which is an alternative to YouTube or YouTube Music.
    """
    
    YOUTUBE = "ytsearch"
    YOUTUBE_MUSIC = "ytmsearch"
    SPOTIFY = "spsearch"
    SOUNDCLOUD = "scsearch"
    APPLE_MUSIC = "amsearch"

    def __str__(self) -> str:
        return self.value
    
    @classmethod
    def match(cls, value: str):
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