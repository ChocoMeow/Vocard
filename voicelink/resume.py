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

from typing import Dict, Optional

from .enums import RequestMethod

RESUME_TIMEOUT_SECONDS = 60
REST_KIND_SESSION = "SESSION"
REST_KIND_PLAYER_GET = "PLAYER_GET"


def websocket_headers(
    *,
    password: str,
    user_id: str,
    client_name: str,
    session_id: Optional[str] = None,
) -> Dict[str, str]:
    """Lavalink v4 websocket headers. Does not send the v3 Resume-Key header."""
    headers = {
        "Authorization": password,
        "User-Id": user_id,
        "Client-Name": client_name,
    }
    if session_id:
        headers["Session-Id"] = session_id
    return headers


def resuming_payload(timeout: int = RESUME_TIMEOUT_SECONDS) -> dict:
    return {"resuming": True, "timeout": timeout}


async def enable_session_resuming(node, session_id: str, timeout: int = RESUME_TIMEOUT_SECONDS) -> None:
    """PATCH /v4/sessions/{id} so a later websocket reconnect can resume players."""
    if not session_id:
        return
    await node.send(
        RequestMethod.PATCH,
        query=f"sessions/{session_id}",
        data=resuming_payload(timeout),
        kind=REST_KIND_SESSION,
    )


async def fetch_player_state(node, session_id: str, guild_id: int) -> Optional[dict]:
    """GET /v4/sessions/{id}/players/{guildId} for resume/stale-PATCH reconciliation."""
    if not session_id:
        return None
    try:
        return await node.send(
            RequestMethod.GET,
            query=f"sessions/{session_id}/players/{guild_id}",
            kind=REST_KIND_PLAYER_GET,
        )
    except Exception:
        return None


def remote_encoded_track(player_state: Optional[dict]) -> Optional[str]:
    if not player_state:
        return None
    track = player_state.get("track")
    if isinstance(track, dict):
        return track.get("encoded")
    return None


def remote_is_playing(player_state: Optional[dict]) -> bool:
    if not player_state:
        return False
    track = player_state.get("track")
    if not track:
        return False
    return not player_state.get("paused", False)
