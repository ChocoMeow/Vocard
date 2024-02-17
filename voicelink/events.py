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

from __future__ import annotations

from .pool import NodePool
from discord.ext.commands import Bot
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .player import Player

class VoicelinkEvent:
    """The base class for all events dispatched by a node. 
       Every event must be formatted within your bot's code as a listener.
       i.e: If you want to listen for when a track starts, the event would be:
       ```py
       @bot.listen
       async def on_voicelink_track_start(self, event):
       ```
    """
    name = "event"
    handler_args = ()

    def dispatch(self, bot: Bot):
        bot.dispatch(f"voicelink_{self.name}", *self.handler_args)


class TrackStartEvent(VoicelinkEvent):
    """Fired when a track has successfully started.
       Returns the player associated with the event and the voicelink.Track object.
    """
    name = "track_start"

    def __init__(self, data: dict, player: Player):
        self.player: Player = player
        self.track = self.player._current

        # on_voicelink_track_start(player, track)
        self.handler_args = self.player, self.track

    def __repr__(self) -> str:
        return f"<Voicelink.TrackStartEvent player={self.player} track_id={self.track.track_id}>"


class TrackEndEvent(VoicelinkEvent):
    """Fired when a track has successfully ended.
       Returns the player associated with the event along with the voicelink.Track object and reason.
    """
    name = "track_end"

    def __init__(self, data: dict, player: Player):
        self.player: Player = player
        self.track = self.player._ending_track
        self.reason: str = data["reason"]

        # on_voicelink_track_end(player, track, reason)
        self.handler_args = self.player, self.track, self.reason

    def __repr__(self) -> str:
        return (
            f"<Voicelink.TrackEndEvent player={self.player} track_id={self.track.track_id} "
            f"reason={self.reason}>"
        )


class TrackStuckEvent(VoicelinkEvent):
    """Fired when a track is stuck and cannot be played. Returns the player
       associated with the event along with the voicelink.Track object
       to be further parsed by the end user.
    """
    name = "track_stuck"

    def __init__(self, data: dict, player: Player):
        self.player: Player = player
        self.track = self.player._ending_track
        self.threshold: float = data["thresholdMs"]

        # on_voicelink_track_stuck(player, track, threshold)
        self.handler_args = self.player, self.track, self.threshold

    def __repr__(self) -> str:
        return f"<Voicelink.TrackStuckEvent player={self.player!r} track={self.track!r} " \
               f"threshold={self.threshold!r}>"


class TrackExceptionEvent(VoicelinkEvent):
    """Fired when a track error has occured.
       Returns the player associated with the event along with the error code and exception.
    """
    name = "track_exception"

    def __init__(self, data: dict, player: Player):
        self.player: Player = player
        self.track = self.player._ending_track
        self.exception: dict = data.get("exception", {
            "severity": "",
            "message": "",
            "cause": ""
        })

        # on_voicelink_track_exception(player, track, error)
        self.handler_args = self.player, self.track, self.exception

    def __repr__(self) -> str:
        return f"<Voicelink.TrackExceptionEvent player={self.player!r} exception={self.exception!r}>"


class WebSocketClosedPayload:
    def __init__(self, data: dict):
        self.guild = NodePool.get_node().bot.get_guild(int(data["guildId"]))
        self.code: int = data["code"]
        self.reason: str = data["code"]
        self.by_remote: bool = data["byRemote"]

    def __repr__(self) -> str:
        return f"<Voicelink.WebSocketClosedPayload guild={self.guild!r} code={self.code!r} " \
               f"reason={self.reason!r} by_remote={self.by_remote!r}>"


class WebSocketClosedEvent(VoicelinkEvent):
    """Fired when a websocket connection to a node has been closed.
       Returns the reason and the error code.
    """
    name = "websocket_closed"

    def __init__(self, data: dict, _):
        self.payload = WebSocketClosedPayload(data)

        # on_voicelink_websocket_closed(payload)
        self.handler_args = self.payload,

    def __repr__(self) -> str:
        return f"<Voicelink.WebsocketClosedEvent payload={self.payload!r}>"


class WebSocketOpenEvent(VoicelinkEvent):
    """Fired when a websocket connection to a node has been initiated.
       Returns the target and the session SSRC.
    """
    name = "websocket_open"

    def __init__(self, data: dict, _):
        self.target: str = data["target"]
        self.ssrc: int = data["ssrc"]

        # on_voicelink_websocket_open(target, ssrc)
        self.handler_args = self.target, self.ssrc

    def __repr__(self) -> str:
        return f"<Voicelink.WebsocketOpenEvent target={self.target!r} ssrc={self.ssrc!r}>"

