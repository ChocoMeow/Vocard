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

        LoopType.off: 1
        LoopType.track: 2
        LoopType.queue: 3

    """
    
    off = auto()
    track = auto()
    queue = auto()
    
class SearchType(Enum):
    """The enum for the different search types for Voicelink.
       This feature is exclusively for the Spotify search feature of Voicelink.
       If you are not using this feature, this class is not necessary.

       SearchType.ytsearch searches using regular Youtube,
       which is best for all scenarios.

       SearchType.ytmsearch searches using YouTube Music,
       which is best for getting audio-only results.

       SearchType.scsearch searches using SoundCloud,
       which is an alternative to YouTube or YouTube Music.
    """
    
    ytsearch = "ytsearch"
    ytmsearch = "ytmsearch"
    scsearch = "scsearch"
    amsearch = "amsearch"

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
    by_ping = auto()
    by_region = auto()

    def __str__(self) -> str:
        return self.value