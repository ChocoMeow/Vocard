"""MIT License

Copyright (c) 2023 - present Vocard Development

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
    10|furnished to do so, subject to the following conditions:

The above copyright notice is included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND.
"""

from __future__ import annotations

import time

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from .playback import safe_log_text

FAILURE_WINDOW_SECONDS = 300
DEGRADED_CLEAR_SECONDS = 600
DISTINCT_ITEM_THRESHOLD = 3
DISTINCT_ENCODED_THRESHOLD = 2
LAST_ERROR_LIMIT = 120

SOURCE_SCOPE_CODES = {
    "YOUTUBE_SOURCE_FAILED",
    "SOURCE_PLUGIN_ERROR",
    "SOURCE_AUTH_REQUIRED",
}
RATE_LIMIT_CODE = "SOURCE_RATE_LIMITED"

_TRACK_UNAVAILABLE = (
    "age-restricted",
    "age restricted",
    "private video",
    "copyright",
    "video unavailable",
    "not available in your country",
    "uploader has not made this video available",
    "removed by",
    "account associated with this video has been terminated",
)
_RATE_LIMIT = (
    "this content isn’t available",
    "this content isn't available",
    "429",
    "rate limit",
    "ratelimit",
)
_AUTH = (
    "oauth",
    "sign in",
    "login required",
    "no valid po token",
    "po token",
    "401",
    "unauthorized",
)


@dataclass(frozen=True)
class Classification:
    code: str
    scope: str


@dataclass
class WindowEvent:
    item_id: int
    encoded: Optional[str]
    code: str
    ts: float


@dataclass
class HealthComponent:
    component: str
    status: str = "ok"
    severity: str = "info"
    installed_version: Optional[str] = None
    available_version: Optional[str] = None
    message: Optional[str] = None
    last_error: Optional[Dict[str, Any]] = None
    last_seen: float = 0.0
    plugin_name: Optional[str] = None
    last_source_event_at: float = 0.0
    persistent: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "component": self.component,
            "status": self.status,
            "severity": self.severity,
            "installed_version": self.installed_version,
            "available_version": None,
            "message": self.message,
            "last_error": self.last_error,
            "last_seen": int(self.last_seen) if self.last_seen else None,
        }


def _blob(source: Optional[str], exception: Optional[dict]) -> str:
    payload = exception if isinstance(exception, dict) else {}
    nested = payload.get("exception") if isinstance(payload.get("exception"), dict) else payload
    parts = [
        source or "",
        str(nested.get("message") or ""),
        str(nested.get("cause") or ""),
        str(nested.get("causeMessage") or ""),
    ]
    return " ".join(parts).lower()


def classify_track_exception(source: Optional[str] = None, exception: Optional[dict] = None) -> Classification:
    text = _blob(source, exception)
    src = (source or "").lower()

    if any(token in text for token in _TRACK_UNAVAILABLE):
        return Classification("TRACK_UNAVAILABLE", "track")
    if any(token in text for token in _RATE_LIMIT):
        return Classification(RATE_LIMIT_CODE, "track")
    if any(token in text for token in _AUTH):
        return Classification("SOURCE_AUTH_REQUIRED", "source")
    if (
        "allclientsfailedexception" in text
        or "all clients failed" in text
        or ("youtube" in src and "client" in text and "fail" in text)
    ):
        return Classification("YOUTUBE_SOURCE_FAILED", "source")
    if "plugin" in text or "extractor" in text:
        if "youtube" in src or "youtube" in text:
            return Classification("YOUTUBE_SOURCE_FAILED", "source")
        return Classification("SOURCE_PLUGIN_ERROR", "source")
    return Classification("UNKNOWN_PLAYBACK_ERROR", "track")


def source_component_id(source: Optional[str]) -> Optional[str]:
    name = (source or "").lower()
    if not name:
        return None
    if "youtube" in name or name in ("ytsearch", "ytmsearch", "youtu.be"):
        return "source:youtube"
    if "spotify" in name or "lavasrc" in name or name in ("spsearch",):
        return "source:spotify"
    return None


def plugin_component_id(plugin_name: Optional[str]) -> Optional[str]:
    name = (plugin_name or "").lower()
    if "youtube" in name:
        return "source:youtube"
    if "spotify" in name or "lavasrc" in name:
        return "source:spotify"
    return None


def _last_error_payload(code: str, exception: Optional[dict]) -> Dict[str, Any]:
    payload = exception if isinstance(exception, dict) else {}
    nested = payload.get("exception") if isinstance(payload.get("exception"), dict) else payload
    detail = safe_log_text(nested.get("cause") or nested.get("message"), limit=LAST_ERROR_LIMIT)
    return {"code": code, "detail": detail}


class PlaybackHealthStore:
    def __init__(self) -> None:
        self.components: Dict[str, HealthComponent] = {}
        self._windows: Dict[str, Dict[int, WindowEvent]] = {}
        self._guild_failures: Dict[int, Dict[str, Any]] = {}

    def _now(self, now: Optional[float]) -> float:
        return time.time() if now is None else now

    def _component(self, component_id: str) -> HealthComponent:
        if component_id not in self.components:
            self.components[component_id] = HealthComponent(component=component_id)
        return self.components[component_id]

    def _prune_window(self, component_id: str, now: float) -> None:
        window = self._windows.get(component_id, {})
        self._windows[component_id] = {
            item_id: event for item_id, event in window.items() if now - event.ts <= FAILURE_WINDOW_SECONDS
        }

    def _source_message(self, component: HealthComponent, *, persistent: bool = False) -> str:
        plugin = component.plugin_name or component.component.split(":", 1)[-1]
        version = component.installed_version or "unknown"
        label = "YouTube" if component.component == "source:youtube" else plugin
        if persistent:
            return (
                f"{label} source is reporting repeated failures. "
                f"Installed plugin: {plugin} {version}. "
                f"Check/update the Lavalink {label} plugin."
            )
        return (
            f"{label} source is reporting failures. "
            f"Installed plugin: {plugin} {version}."
        )

    def _window_persistent(self, component_id: str, now: float) -> bool:
        self._prune_window(component_id, now)
        events = list(self._windows.get(component_id, {}).values())
        source_events = [event for event in events if event.code in SOURCE_SCOPE_CODES]
        rate_events = [event for event in events if event.code == RATE_LIMIT_CODE]
        distinct_source_items = {event.item_id for event in source_events}
        distinct_source_encoded = {event.encoded for event in source_events if event.encoded}
        distinct_rate_items = {event.item_id for event in rate_events}
        return (
            len(distinct_source_items) >= DISTINCT_ITEM_THRESHOLD
            or len(distinct_source_encoded) >= DISTINCT_ENCODED_THRESHOLD
            or len(distinct_rate_items) >= DISTINCT_ITEM_THRESHOLD
        )

    def _evaluate_source(self, component_id: str, now: float, *, source_scoped_event: bool = False) -> bool:
        persistent_now = self._window_persistent(component_id, now)
        component = self._component(component_id)
        if persistent_now:
            component.persistent = True
        changed = False

        if component.status == "unavailable":
            return False

        if (source_scoped_event or component.persistent) and component.status == "ok":
            component.status = "degraded"
            component.severity = "error" if component.persistent else "warning"
            component.message = self._source_message(component, persistent=component.persistent)
            component.last_seen = now
            changed = True
        elif component.status == "degraded" and component.persistent:
            message = self._source_message(component, persistent=True)
            if component.severity != "error" or component.message != message:
                component.severity = "error"
                component.message = message
                component.last_seen = now
                changed = True
        elif component.status == "degraded" and not component.persistent:
            idle = now - (component.last_source_event_at or 0)
            if not source_scoped_event and idle >= DEGRADED_CLEAR_SECONDS:
                component.status = "ok"
                component.severity = "info"
                component.message = None
                component.last_seen = now
                changed = True
        return changed

    def record_node(
        self,
        identifier: str,
        *,
        available: bool,
        version: Optional[str] = None,
        plugins: Optional[List[Any]] = None,
        now: Optional[float] = None,
    ) -> bool:
        now = self._now(now)
        component = self._component(f"node:{identifier}")
        previous = component.status
        component.installed_version = version
        component.last_seen = now
        if available:
            component.status = "ok"
            component.severity = "info"
            component.message = None
        else:
            component.status = "unavailable"
            component.severity = "error"
            component.message = f"Lavalink node {identifier} is disconnected."
            component.last_error = {"code": "NODE_UNAVAILABLE", "detail": None}

        for plugin in plugins or []:
            name = getattr(plugin, "name", None) or (plugin.get("name") if isinstance(plugin, dict) else None)
            plugin_version = getattr(plugin, "version", None) or (
                plugin.get("version") if isinstance(plugin, dict) else None
            )
            source_id = plugin_component_id(name)
            if not source_id:
                continue
            source = self._component(source_id)
            source.plugin_name = name
            source.installed_version = plugin_version
            source.last_seen = now
            if source.status == "unavailable":
                source.status = "ok"
                source.severity = "info"
        return previous != component.status

    def record_exception(
        self,
        *,
        source: Optional[str] = None,
        exception: Optional[dict] = None,
        item_id: Optional[int] = None,
        encoded: Optional[str] = None,
        title: Optional[str] = None,
        guild_id: Optional[int] = None,
        node_available: bool = True,
        now: Optional[float] = None,
    ) -> Tuple[Classification, bool]:
        now = self._now(now)
        if not node_available:
            classification = Classification("NODE_UNAVAILABLE", "node")
        else:
            classification = classify_track_exception(source, exception)

        last_error = _last_error_payload(classification.code, exception)
        component_id = source_component_id(source)
        if classification.code == "NODE_UNAVAILABLE":
            component_id = component_id  # node status is owned by record_node
        changed = False

        if component_id:
            component = self._component(component_id)
            component.last_error = last_error
            component.last_seen = now
            if classification.scope == "source" or classification.code == RATE_LIMIT_CODE:
                component.last_source_event_at = now
                if item_id is not None:
                    self._prune_window(component_id, now)
                    window = self._windows.setdefault(component_id, {})
                    window[item_id] = WindowEvent(
                        item_id=item_id,
                        encoded=encoded,
                        code=classification.code,
                        ts=now,
                    )
                changed = self._evaluate_source(
                    component_id,
                    now,
                    source_scoped_event=classification.scope == "source",
                ) or changed

        if guild_id is not None:
            self._guild_failures[guild_id] = {
                "code": classification.code,
                "title": title,
                "source": source,
            }
        return classification, changed

    def record_track_start(self, source: Optional[str] = None, now: Optional[float] = None) -> bool:
        now = self._now(now)
        component_id = source_component_id(source)
        if not component_id or component_id not in self.components:
            return False
        component = self.components[component_id]
        if component.status != "degraded":
            return False
        self._windows[component_id] = {}
        component.status = "ok"
        component.severity = "info"
        component.message = None
        component.persistent = False
        component.last_seen = now
        return True

    def guild_failure(self, guild_id: Optional[int]) -> Optional[Dict[str, Any]]:
        if guild_id is None:
            return None
        return self._guild_failures.get(guild_id)

    def clear_guild_failure(self, guild_id: Optional[int]) -> None:
        if guild_id is not None:
            self._guild_failures.pop(guild_id, None)

    def expire_degraded(self, now: Optional[float] = None) -> bool:
        now = self._now(now)
        changed = False
        for component_id in list(self.components):
            if component_id.startswith("source:"):
                changed = self._evaluate_source(component_id, now) or changed
        return changed

    def snapshot(
        self,
        *,
        guild_id: Optional[int] = None,
        voice_connected: Optional[bool] = None,
        now: Optional[float] = None,
    ) -> Dict[str, Any]:
        self.expire_degraded(now)
        components = [component.to_dict() for component in self.components.values()]
        if voice_connected is not None:
            components.append({
                "component": "voice",
                "status": "ok" if voice_connected else "unavailable",
                "severity": "info" if voice_connected else "warning",
                "installed_version": None,
                "available_version": None,
                "message": None if voice_connected else "Discord voice is disconnected.",
                "last_error": None,
                "last_seen": int(self._now(now)),
            })
        return {
            "components": components,
            "playbackFailure": self.guild_failure(guild_id),
        }

    def ipc_payload(
        self,
        *,
        guild_id: Optional[int] = None,
        voice_connected: Optional[bool] = None,
        playback_failure: Optional[Dict[str, Any]] = None,
        now: Optional[float] = None,
    ) -> Dict[str, Any]:
        snapshot = self.snapshot(guild_id=guild_id, voice_connected=voice_connected, now=now)
        if playback_failure is not None:
            snapshot["playbackFailure"] = playback_failure
        payload = {"op": "playbackHealth", **snapshot}
        if guild_id is not None:
            payload["guildId"] = str(guild_id)
        return payload

    def plugin_summaries(self) -> List[str]:
        lines = []
        for component in self.components.values():
            if component.component.startswith("source:") and component.plugin_name:
                lines.append(f"{component.plugin_name} {component.installed_version or '?'}".strip())
        return lines


health_store = PlaybackHealthStore()
