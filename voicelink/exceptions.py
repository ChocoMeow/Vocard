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

class VoicelinkException(Exception):
    """Base of all Voicelink exceptions."""


class NodeException(Exception):
    """Base exception for nodes."""


class NodeCreationError(NodeException):
    """There was a problem while creating the node."""


class NodeConnectionFailure(NodeException):
    """There was a problem while connecting to the node."""


class NodeConnectionClosed(NodeException):
    """The node's connection is closed."""
    pass


class NodeNotAvailable(VoicelinkException):
    """The node is currently unavailable."""
    pass


class NoNodesAvailable(VoicelinkException):
    """There are no nodes currently available."""
    pass


class TrackInvalidPosition(VoicelinkException):
    """An invalid position was chosen for a track."""
    pass


class TrackLoadError(VoicelinkException):
    """There was an error while loading a track."""
    pass


class FilterInvalidArgument(VoicelinkException):
    """An invalid argument was passed to a filter."""
    pass

class FilterTagAlreadyInUse(VoicelinkException):
    """A filter with a tag is already in use by another filter"""
    pass

class FilterTagInvalid(VoicelinkException):
    """An invalid tag was passed or Voicelink was unable to find a filter tag"""
    pass

class SpotifyAlbumLoadFailed(VoicelinkException):
    """The voicelink Spotify client was unable to load an album."""
    pass


class SpotifyTrackLoadFailed(VoicelinkException):
    """The voicelink Spotify client was unable to load a track."""
    pass


class SpotifyPlaylistLoadFailed(VoicelinkException):
    """The voicelink Spotify client was unable to load a playlist."""
    pass


class InvalidSpotifyClientAuthorization(VoicelinkException):
    """No Spotify client authorization was provided for track searching."""
    pass


class QueueFull(VoicelinkException):
    pass

class OutofList(VoicelinkException):
    pass

class DuplicateTrack(VoicelinkException):
    pass