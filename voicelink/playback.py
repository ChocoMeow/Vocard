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

from collections import deque
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Deque, Dict, Iterable, List, Optional, Tuple

TRACK_START_TIMEOUT = 15
EXCEPTION_END_FALLBACK = 2
MAX_PENDING_EVENTS = 8
MAX_ITEM_RETRIES = 1
STALE_OP_CAP = 32
PLAYBACK_LOGGER_NAME = "vocard.playback"


class PlaybackAdvanceReason(Enum):
    FINISHED = "FINISHED"
    MANUAL_SKIP = "MANUAL_SKIP"
    FORCEPLAY = "FORCEPLAY"
    PLAYBACK_EXCEPTION = "PLAYBACK_EXCEPTION"
    LOAD_FAILED = "LOAD_FAILED"
    TRACK_STUCK = "TRACK_STUCK"
    REPLACED = "REPLACED"
    NODE_DISCONNECT = "NODE_DISCONNECT"
    VOICE_DISCONNECT = "VOICE_DISCONNECT"
    PLAY_REQUEST_FAILED = "PLAY_REQUEST_FAILED"
    CLEANUP = "CLEANUP"
    AUTOPLAY = "AUTOPLAY"
    UNKNOWN = "UNKNOWN"

    def __str__(self) -> str:
        return self.value


class AttemptState(Enum):
    STARTING = "STARTING"
    STARTED = "STARTED"
    FAILED = "FAILED"
    RETRYING = "RETRYING"
    ENDING = "ENDING"
    ENDED = "ENDED"
    RECOVERING = "RECOVERING"


class AttemptIntent(Enum):
    NONE = "NONE"
    SKIP = "SKIP"
    STOP = "STOP"
    FORCEPLAY = "FORCEPLAY"


class TerminalSource(Enum):
    FINISHED = "FINISHED"
    LOAD_FAILED = "LOAD_FAILED"
    TRACK_STUCK = "TRACK_STUCK"
    WATCHDOG = "WATCHDOG"
    EXCEPTION_FALLBACK = "EXCEPTION_FALLBACK"
    SKIP = "SKIP"
    STOP = "STOP"
    CLEANUP = "CLEANUP"
    PLAY_REST = "PLAY_REST"
    RECOVERY_ABANDON = "RECOVERY_ABANDON"


class PendingEventKind(Enum):
    TRACK_START = "TRACK_START"
    TRACK_END = "TRACK_END"
    TRACK_EXCEPTION = "TRACK_EXCEPTION"
    TRACK_STUCK = "TRACK_STUCK"


class ForceplayOpState(Enum):
    PENDING_STOP = "PENDING_STOP"
    ADVANCING = "ADVANCING"
    DONE = "DONE"
    STALE = "STALE"


class EventDisposition(Enum):
    APPLY = "APPLY"
    PENDING = "PENDING"
    IGNORE = "IGNORE"
    AMBIGUOUS = "AMBIGUOUS"


FAILURE_TERMINALS = {
    TerminalSource.LOAD_FAILED,
    TerminalSource.TRACK_STUCK,
    TerminalSource.WATCHDOG,
    TerminalSource.EXCEPTION_FALLBACK,
    TerminalSource.PLAY_REST,
}

ADVANCE_REASON_FOR_SOURCE = {
    TerminalSource.FINISHED: PlaybackAdvanceReason.FINISHED,
    TerminalSource.LOAD_FAILED: PlaybackAdvanceReason.LOAD_FAILED,
    TerminalSource.TRACK_STUCK: PlaybackAdvanceReason.TRACK_STUCK,
    TerminalSource.WATCHDOG: PlaybackAdvanceReason.PLAY_REQUEST_FAILED,
    TerminalSource.EXCEPTION_FALLBACK: PlaybackAdvanceReason.PLAYBACK_EXCEPTION,
    TerminalSource.SKIP: PlaybackAdvanceReason.MANUAL_SKIP,
    TerminalSource.STOP: PlaybackAdvanceReason.CLEANUP,
    TerminalSource.CLEANUP: PlaybackAdvanceReason.CLEANUP,
    TerminalSource.PLAY_REST: PlaybackAdvanceReason.PLAY_REQUEST_FAILED,
    TerminalSource.RECOVERY_ABANDON: PlaybackAdvanceReason.CLEANUP,
}


def encoded_from_payload(data: Optional[dict]) -> Optional[str]:
    if not data:
        return None
    track = data.get("track")
    if isinstance(track, dict):
        return track.get("encoded") or track.get("encodedTrack")
    if isinstance(track, str):
        return track
    return data.get("encodedTrack")


def snapshot_exception(data: Optional[dict]) -> dict:
    if not data:
        return {"severity": "", "message": "", "cause": ""}
    exception = data.get("exception")
    if isinstance(exception, dict):
        return {
            "severity": exception.get("severity", ""),
            "message": exception.get("message", ""),
            "cause": exception.get("cause", ""),
        }
    return {"severity": "", "message": "", "cause": ""}


@dataclass
class QueueItem:
    item_id: int
    track: Any
    retry_count: int = 0
    fail_exhausted: bool = False
    history_recorded: bool = False

    def can_retry(self) -> bool:
        return self.retry_count < MAX_ITEM_RETRIES and not self.fail_exhausted

    def mark_retry(self) -> None:
        self.retry_count += 1
        if self.retry_count >= MAX_ITEM_RETRIES:
            self.fail_exhausted = True

    def mark_exhausted(self) -> None:
        self.fail_exhausted = True

    def begin_new_cycle(self, new_item_id: int) -> None:
        self.item_id = new_item_id
        self.retry_count = 0
        self.fail_exhausted = False
        self.history_recorded = False

    def clear_failure_for_user_select(self, new_item_id: int) -> None:
        self.begin_new_cycle(new_item_id)


@dataclass
class PendingEvent:
    kind: PendingEventKind
    encoded: Optional[str] = None
    reason: Optional[str] = None
    exception: Optional[dict] = None
    threshold: Optional[float] = None
    payload: Optional[dict] = None


@dataclass
class PlaybackAttempt:
    attempt_id: int
    item_id: int
    encoded_track_id: Optional[str]
    play_seq: int
    state: AttemptState = AttemptState.STARTING
    armed: bool = False
    play_in_flight: bool = False
    intent: AttemptIntent = AttemptIntent.NONE
    start_pos: int = 0
    end_time: Optional[int] = None
    terminal_source: Optional[TerminalSource] = None
    recorded_exception: Optional[dict] = None
    pending: Deque[PendingEvent] = field(default_factory=deque)
    previous_encoded: Optional[str] = None

    @property
    def is_terminal(self) -> bool:
        return self.terminal_source is not None or self.state in (
            AttemptState.FAILED,
            AttemptState.ENDED,
            AttemptState.ENDING,
        )

    def claim_terminal(self, source: TerminalSource) -> bool:
        if self.terminal_source is not None:
            return False
        self.terminal_source = source
        if source == TerminalSource.FINISHED:
            self.state = AttemptState.ENDED
        elif source in (TerminalSource.SKIP, TerminalSource.STOP, TerminalSource.CLEANUP, TerminalSource.RECOVERY_ABANDON):
            self.state = AttemptState.ENDING
        else:
            self.state = AttemptState.FAILED
        self.armed = False
        self.play_in_flight = False
        return True

    def enqueue_pending(self, event: PendingEvent) -> None:
        if len(self.pending) >= MAX_PENDING_EVENTS:
            self.pending.popleft()
        self.pending.append(event)

    def take_pending(self) -> List[PendingEvent]:
        events = list(self.pending)
        self.pending.clear()
        return events

    def discard_pending(self) -> None:
        self.pending.clear()


@dataclass
class RetryReservation:
    item_id: int
    source: TerminalSource
    cancelled: bool = False


@dataclass
class ForceplayOp:
    op_id: int
    target_item_id: int
    superseded_item_id: Optional[int]
    superseded_attempt_id: Optional[int]
    state: ForceplayOpState = ForceplayOpState.PENDING_STOP


@dataclass
class AdvanceCommit:
    reason: PlaybackAdvanceReason
    from_item: Optional[QueueItem]
    to_item: Optional[QueueItem]
    from_attempt_id: Optional[int]
    logs: List[Dict[str, Any]] = field(default_factory=list)
    side_effect: str = "QUEUE_ADVANCE"


class PlaybackPolicy:
    """Pure playback transition rules used by Player and unit tests."""

    def encoded_matches(self, attempt: Optional[PlaybackAttempt], encoded: Optional[str]) -> bool:
        if attempt is None:
            return False
        if not encoded or not attempt.encoded_track_id:
            return True
        return encoded == attempt.encoded_track_id

    def classify_event(
        self,
        attempt: Optional[PlaybackAttempt],
        kind: PendingEventKind,
        encoded: Optional[str],
    ) -> EventDisposition:
        if attempt is None:
            return EventDisposition.IGNORE
        if encoded and attempt.encoded_track_id and encoded != attempt.encoded_track_id:
            return EventDisposition.IGNORE
        if attempt.play_in_flight and not attempt.armed:
            return EventDisposition.PENDING
        if not attempt.armed and attempt.state == AttemptState.STARTING:
            return EventDisposition.PENDING if attempt.play_in_flight else EventDisposition.IGNORE
        if attempt.is_terminal and kind != PendingEventKind.TRACK_EXCEPTION:
            return EventDisposition.IGNORE
        if (
            attempt.previous_encoded
            and encoded
            and encoded == attempt.previous_encoded
            and encoded == attempt.encoded_track_id
            and attempt.state == AttemptState.STARTING
        ):
            return EventDisposition.AMBIGUOUS
        return EventDisposition.APPLY

    def should_retry(self, item: Optional[QueueItem], source: TerminalSource) -> bool:
        return False

    def forceplay_accepts_replaced(
        self,
        op: Optional[ForceplayOp],
        attempt: Optional[PlaybackAttempt],
        item_id: Optional[int],
    ) -> bool:
        if op is None or attempt is None or item_id is None:
            return False
        if op.state != ForceplayOpState.PENDING_STOP:
            return False
        if op.superseded_item_id != item_id:
            return False
        if op.superseded_attempt_id != attempt.attempt_id:
            return False
        return True


class PlaybackSession:
    """Player-facing session state. Safe to construct without Discord/Lavalink."""

    def __init__(self) -> None:
        self._attempt_ids = 0
        self._play_seqs = 0
        self._forceplay_ids = 0
        self.attempt: Optional[PlaybackAttempt] = None
        self.current_item: Optional[QueueItem] = None
        self.reservation: Optional[RetryReservation] = None
        self.forceplay: Optional[ForceplayOp] = None
        self.desired_connected: bool = True
        self.tearing_down: bool = False
        self.watchdog_suspended: bool = False
        self.stale_ops: Dict[int, int] = {}
        self.reconcile_generation: int = 0
        self.pending_reconcile: bool = False
        self.logs: List[Dict[str, Any]] = []
        self.queue_advance_logs: List[Dict[str, Any]] = []
        self.side_effects: List[str] = []
        self.history_writes: List[int] = []
        self.policy = PlaybackPolicy()
        self.last_ended_encoded: Optional[str] = None

    def _next_attempt_id(self) -> int:
        self._attempt_ids += 1
        return self._attempt_ids

    def next_play_seq(self) -> int:
        self._play_seqs += 1
        return self._play_seqs

    def _next_forceplay_id(self) -> int:
        self._forceplay_ids += 1
        return self._forceplay_ids

    def log(self, event: str, **fields: Any) -> None:
        record = {"event": event, **fields}
        self.logs.append(record)
        if event == "QUEUE_ADVANCE":
            self.queue_advance_logs.append(record)

    def remember_stale(self, item_id: int, play_seq: int) -> None:
        self.stale_ops[item_id] = play_seq
        while len(self.stale_ops) > STALE_OP_CAP:
            oldest = next(iter(self.stale_ops))
            self.stale_ops.pop(oldest, None)

    def prune_stale(self, item_id: Optional[int] = None, play_seq: Optional[int] = None) -> None:
        if item_id is not None:
            recorded = self.stale_ops.get(item_id)
            if recorded is None or play_seq is None or recorded <= play_seq:
                self.stale_ops.pop(item_id, None)
        if play_seq is not None:
            for key, seq in [(k, s) for k, s in self.stale_ops.items() if s <= play_seq]:
                if key != (self.current_item.item_id if self.current_item else None):
                    if self.attempt and key == self.attempt.item_id and self.attempt.play_seq > play_seq:
                        continue
                    if key not in (
                        {self.attempt.item_id} if self.attempt else set()
                    ) and key not in (
                        {self.forceplay.target_item_id, self.forceplay.superseded_item_id}
                        if self.forceplay else set()
                    ):
                        if seq < play_seq:
                            self.stale_ops.pop(key, None)

    def create_attempt(
        self,
        item: QueueItem,
        *,
        start_pos: int = 0,
        previous_encoded: Optional[str] = None,
        state: AttemptState = AttemptState.STARTING,
    ) -> PlaybackAttempt:
        encoded = getattr(item.track, "track_id", None)
        attempt = PlaybackAttempt(
            attempt_id=self._next_attempt_id(),
            item_id=item.item_id,
            encoded_track_id=encoded,
            play_seq=self.next_play_seq(),
            state=state,
            armed=False,
            start_pos=start_pos,
            end_time=getattr(item.track, "end_time", None),
            previous_encoded=previous_encoded,
        )
        self.attempt = attempt
        self.current_item = item
        return attempt

    def mark_play_in_flight(self) -> Optional[int]:
        if not self.attempt:
            return None
        self.attempt.play_in_flight = True
        return self.attempt.play_seq

    def validate_play_completion(self, play_seq: int, item_id: int, attempt_id: int) -> bool:
        if self.tearing_down or not self.desired_connected:
            return False
        if not self.attempt or not self.current_item:
            return False
        if self.attempt.is_terminal:
            return False
        if self.attempt.play_seq != play_seq:
            return False
        if self.attempt.attempt_id != attempt_id:
            return False
        if self.current_item.item_id != item_id:
            return False
        if item_id in self.stale_ops and self.stale_ops[item_id] >= play_seq:
            return False
        return True

    def arm_after_play_success(self) -> List[PendingEvent]:
        if not self.attempt:
            return []
        self.attempt.armed = True
        self.attempt.play_in_flight = False
        return self.attempt.take_pending()

    def fail_play_patch(self) -> List[PendingEvent]:
        if not self.attempt:
            return []
        self.attempt.play_in_flight = False
        pending = list(self.attempt.pending)
        self.attempt.discard_pending()
        return pending

    def record_history_if_needed(self) -> bool:
        item = self.current_item
        if item is None or item.history_recorded:
            return False
        requester = getattr(item.track, "requester", None)
        if requester is not None and getattr(requester, "bot", False):
            item.history_recorded = True
            return False
        item.history_recorded = True
        self.history_writes.append(item.item_id)
        return True

    def enqueue_or_apply(
        self,
        kind: PendingEventKind,
        *,
        encoded: Optional[str] = None,
        reason: Optional[str] = None,
        exception: Optional[dict] = None,
        threshold: Optional[float] = None,
        payload: Optional[dict] = None,
    ) -> EventDisposition:
        disposition = self.policy.classify_event(self.attempt, kind, encoded)
        if disposition == EventDisposition.PENDING and self.attempt:
            self.attempt.enqueue_pending(PendingEvent(
                kind=kind,
                encoded=encoded,
                reason=reason,
                exception=exception,
                threshold=threshold,
                payload=payload,
            ))
        if disposition == EventDisposition.AMBIGUOUS:
            self.log(
                "AMBIGUOUS_EVENT",
                kind=kind.value,
                encoded=encoded,
                attempt_id=self.attempt.attempt_id if self.attempt else None,
                item_id=self.attempt.item_id if self.attempt else None,
            )
        return disposition

    def apply_track_start(self, encoded: Optional[str] = None) -> bool:
        if not self.attempt or self.attempt.is_terminal:
            return False
        if not self.policy.encoded_matches(self.attempt, encoded):
            return False
        if self.attempt.state in (AttemptState.STARTING, AttemptState.RECOVERING):
            self.attempt.state = AttemptState.STARTED
            self.log(
                "TRACK_START",
                item_id=self.attempt.item_id,
                attempt_id=self.attempt.attempt_id,
            )
            return True
        return False

    def apply_track_exception(self, exception: Optional[dict] = None) -> bool:
        if not self.attempt or self.attempt.is_terminal:
            return False
        if self.attempt.recorded_exception:
            return False
        self.attempt.recorded_exception = exception or {}
        self.log(
            "TRACK_EXCEPTION",
            item_id=self.attempt.item_id,
            attempt_id=self.attempt.attempt_id,
        )
        return True

    def claim(self, source: TerminalSource) -> bool:
        if not self.attempt:
            return False
        return self.attempt.claim_terminal(source)

    def begin_retry_reservation(self, source: TerminalSource) -> Optional[RetryReservation]:
        if not self.current_item:
            return None
        self.reservation = RetryReservation(item_id=self.current_item.item_id, source=source)
        return self.reservation

    def cancel_reservation(self) -> bool:
        if not self.reservation or self.reservation.cancelled:
            return False
        self.reservation.cancelled = True
        return True

    def consume_reservation(self) -> Optional[RetryReservation]:
        reservation = self.reservation
        if reservation is None or reservation.cancelled:
            self.reservation = None
            return None
        if self.current_item is None or reservation.item_id != self.current_item.item_id:
            self.reservation = None
            return None
        self.reservation = None
        return reservation

    def commit_retry(self) -> Optional[PlaybackAttempt]:
        item = self.current_item
        reservation = self.consume_reservation()
        if item is None or reservation is None:
            return None
        if not item.can_retry():
            return None
        old = self.attempt
        previous = old.encoded_track_id if old else None
        if old:
            old.state = AttemptState.ENDED
            old.discard_pending()
        item.mark_retry()
        attempt = self.create_attempt(item, start_pos=getattr(item.track, "position", 0) or 0, previous_encoded=previous)
        self.side_effects.append("RETRY")
        self.log(
            "RETRY",
            item_id=item.item_id,
            attempt_id=attempt.attempt_id,
            retry_count=item.retry_count,
        )
        return attempt

    def commit_advance(
        self,
        reason: PlaybackAdvanceReason,
        next_item: Optional[QueueItem],
    ) -> AdvanceCommit:
        from_item = self.current_item
        from_attempt = self.attempt
        if from_attempt:
            from_attempt.discard_pending()
            if not from_attempt.is_terminal:
                from_attempt.state = AttemptState.ENDED
            self.last_ended_encoded = from_attempt.encoded_track_id
        if from_item:
            self.remember_stale(from_item.item_id, from_attempt.play_seq if from_attempt else 0)
        self.reservation = None
        if self.forceplay and self.forceplay.state == ForceplayOpState.ADVANCING:
            self.forceplay.state = ForceplayOpState.DONE
        self.current_item = next_item
        to_attempt = None
        if next_item is not None:
            start = getattr(next_item.track, "position", 0) or 0
            to_attempt = self.create_attempt(
                next_item,
                start_pos=start,
                previous_encoded=self.last_ended_encoded,
            )
        else:
            self.attempt = None
        log_fields = {
            "from_item": from_item.item_id if from_item else None,
            "to_item": next_item.item_id if next_item else None,
            "attempt_id": from_attempt.attempt_id if from_attempt else None,
            "reason": str(reason),
            "retry_count": from_item.retry_count if from_item else 0,
        }
        if from_item:
            log_fields["track"] = getattr(from_item.track, "title", None)
        if from_item is not None:
            self.log("QUEUE_ADVANCE", **log_fields)
        self.side_effects.append("QUEUE_ADVANCE")
        if next_item is None:
            self.prune_stale(play_seq=from_attempt.play_seq if from_attempt else None)
        return AdvanceCommit(
            reason=reason,
            from_item=from_item,
            to_item=next_item,
            from_attempt_id=from_attempt.attempt_id if from_attempt else None,
        )

    def decide_after_failure(self, source: TerminalSource) -> str:
        if self.tearing_down or not self.desired_connected:
            return "TEARDOWN"
        if self.policy.should_retry(self.current_item, source):
            self.begin_retry_reservation(source)
            return "RETRY"
        if self.current_item:
            self.current_item.mark_exhausted()
        return "ADVANCE"

    def user_skip(self) -> str:
        if self.tearing_down or not self.desired_connected:
            return "TEARDOWN"
        if self.reservation and not self.reservation.cancelled:
            self.cancel_reservation()
            return "ADVANCE"
        if self.attempt and not self.attempt.is_terminal:
            started = self.attempt.state == AttemptState.STARTED
            in_flight = self.attempt.play_in_flight
            play_seq = self.attempt.play_seq
            item_id = self.attempt.item_id
            if started:
                self.attempt.intent = AttemptIntent.SKIP
                if in_flight:
                    self.remember_stale(item_id, play_seq)
                return "STOP_THEN_ADVANCE"
            if self.attempt.claim_terminal(TerminalSource.SKIP):
                if in_flight:
                    self.remember_stale(item_id, play_seq)
                self.attempt.intent = AttemptIntent.SKIP
                return "ADVANCE"
            return "IGNORE"
        if self.attempt and self.attempt.is_terminal and self.current_item:
            return "ADVANCE"
        return "IGNORE"

    def user_leave(self) -> None:
        self.desired_connected = False
        self.tearing_down = True
        self.cancel_reservation()
        if self.attempt:
            self.attempt.intent = AttemptIntent.STOP
            self.attempt.discard_pending()
            if not self.attempt.is_terminal:
                self.attempt.claim_terminal(TerminalSource.STOP)
            if self.attempt.play_in_flight:
                self.remember_stale(self.attempt.item_id, self.attempt.play_seq)
        self.forceplay = None

    def begin_forceplay(self, target_item_id: int) -> ForceplayOp:
        superseded_item = self.current_item.item_id if self.current_item else None
        superseded_attempt = self.attempt.attempt_id if self.attempt else None
        if self.reservation:
            self.cancel_reservation()
        if self.attempt and self.attempt.play_in_flight:
            self.remember_stale(self.attempt.item_id, self.attempt.play_seq)
        if self.attempt:
            self.attempt.intent = AttemptIntent.FORCEPLAY
        op = ForceplayOp(
            op_id=self._next_forceplay_id(),
            target_item_id=target_item_id,
            superseded_item_id=superseded_item,
            superseded_attempt_id=superseded_attempt,
        )
        self.forceplay = op
        return op

    def on_replaced(self) -> str:
        if self.policy.forceplay_accepts_replaced(
            self.forceplay,
            self.attempt,
            self.current_item.item_id if self.current_item else None,
        ):
            if self.attempt and self.attempt.claim_terminal(TerminalSource.SKIP):
                self.forceplay.state = ForceplayOpState.ADVANCING
                return "FORCEPLAY_ADVANCE"
            return "RECONCILE"
        self.log("TRACK_END", reason="replaced", attempt_id=self.attempt.attempt_id if self.attempt else None)
        return "IGNORE"

    def on_stopped(self) -> str:
        if not self.attempt:
            return "IGNORE"
        intent = self.attempt.intent
        if intent == AttemptIntent.STOP or self.tearing_down or not self.desired_connected:
            self.attempt.claim_terminal(TerminalSource.STOP)
            return "TEARDOWN"
        if intent == AttemptIntent.FORCEPLAY:
            if self.forceplay and self.forceplay.state == ForceplayOpState.PENDING_STOP:
                if self.attempt.claim_terminal(TerminalSource.SKIP):
                    self.forceplay.state = ForceplayOpState.ADVANCING
                    return "FORCEPLAY_ADVANCE"
            return "IGNORE"
        if intent == AttemptIntent.SKIP:
            if self.attempt.claim_terminal(TerminalSource.SKIP):
                return "ADVANCE"
            return "IGNORE"
        self.log("TRACK_END", reason="stopped", attempt_id=self.attempt.attempt_id)
        return "IGNORE"

    def on_finished(self) -> str:
        if not self.attempt:
            return "IGNORE"
        if self.attempt.state != AttemptState.STARTED:
            self.log(
                "AMBIGUOUS_EVENT",
                kind="TRACK_END",
                reason="finished",
                attempt_id=self.attempt.attempt_id,
                item_id=self.attempt.item_id,
            )
            return "IGNORE"
        if self.attempt.claim_terminal(TerminalSource.FINISHED):
            return "ADVANCE"
        return "IGNORE"

    def on_load_failed(self) -> str:
        if not self.attempt:
            return "IGNORE"
        if not self.attempt.claim_terminal(TerminalSource.LOAD_FAILED):
            return "IGNORE"
        return self.decide_after_failure(TerminalSource.LOAD_FAILED)

    def on_stuck(self) -> str:
        if not self.attempt:
            return "IGNORE"
        if not self.attempt.claim_terminal(TerminalSource.TRACK_STUCK):
            return "IGNORE"
        return self.decide_after_failure(TerminalSource.TRACK_STUCK)

    def on_watchdog(self) -> str:
        if self.watchdog_suspended or self.tearing_down or not self.desired_connected:
            return "IGNORE"
        if not self.attempt or self.attempt.state != AttemptState.STARTING or not self.attempt.armed:
            return "IGNORE"
        if self.attempt.intent != AttemptIntent.NONE:
            return "IGNORE"
        if not self.attempt.claim_terminal(TerminalSource.WATCHDOG):
            return "IGNORE"
        return self.decide_after_failure(TerminalSource.WATCHDOG)

    def on_exception_fallback(self) -> str:
        if not self.attempt:
            return "IGNORE"
        if self.attempt.is_terminal:
            return "IGNORE"
        if not self.attempt.claim_terminal(TerminalSource.EXCEPTION_FALLBACK):
            return "IGNORE"
        return self.decide_after_failure(TerminalSource.EXCEPTION_FALLBACK)

    def on_cleanup(self) -> str:
        if self.tearing_down or not self.desired_connected:
            if self.attempt:
                self.attempt.claim_terminal(TerminalSource.CLEANUP)
            return "TEARDOWN"
        if self.attempt:
            self.attempt.claim_terminal(TerminalSource.CLEANUP)
        return "RECOVER"

    def retry_start_position(self, *, recovery_after_started: bool, last_position: int = 0) -> int:
        item = self.current_item
        intended = getattr(item.track, "position", 0) or 0 if item else 0
        if recovery_after_started:
            return last_position or intended
        return intended

    def intended_end_time(self) -> Optional[int]:
        if not self.current_item:
            return None
        return getattr(self.current_item.track, "end_time", None)

    def mark_reconcile(self) -> int:
        self.pending_reconcile = True
        self.reconcile_generation += 1
        return self.reconcile_generation

    def take_reconcile(self, generation: int) -> bool:
        if not self.pending_reconcile:
            return False
        if generation != self.reconcile_generation:
            return False
        if self.tearing_down or not self.desired_connected:
            return False
        self.pending_reconcile = False
        return True
