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

    def __init__(
        self,
        message: str = "Getting errors from Lavalink REST api",
        *,
        method: str = None,
        path: str = None,
        kind: str = None,
        status: int = None,
        body: str = None,
        node_id: str = None,
    ):
        super().__init__(message)
        self.method = method
        self.path = path
        self.kind = kind
        self.status = status
        self.body = body
        self.node_id = node_id

    @property
    def is_play_patch(self) -> bool:
        return self.kind == "PLAYER_PLAY"


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

class QueueFull(VoicelinkException):
    pass

class OutofList(VoicelinkException):
    pass

class DuplicateTrack(VoicelinkException):
    pass