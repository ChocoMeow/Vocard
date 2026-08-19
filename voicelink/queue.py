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

import discord

from itertools import cycle
from typing import Optional, Tuple, Callable, Dict, List, Union

from .exceptions import QueueFull, OutofList
from .objects import Track
from .enums import LoopType
from .playback import QueueItem

class LoopTypeCycle:
    def __init__(self) -> None:
        self._cycle = cycle(LoopType)
        self.current = next(self._cycle)

    def next(self) -> LoopType:
        self.current = next(self._cycle)
        return self.current

    def peek_next(self) -> LoopType:
        temp_cycle = cycle(LoopType)
        while next(temp_cycle) != self.current:
            pass
        
        return next(temp_cycle)
    
    def set_mode(self, value: LoopType) -> LoopType:
        while next(self._cycle) != value:
            pass
        self.current = value
        return value

    @property
    def mode(self) -> LoopType:
        return self.current
    
    def __str__(self) -> str:
        return self.current.name.capitalize()

class Queue:
    def __init__(self, size: int, allow_duplicate: bool, get_msg: Callable[[str], str]) -> None:
        self._queue: List[QueueItem] = []
        self._position: int = 0
        self._size: int = size
        self._repeat: LoopTypeCycle = LoopTypeCycle()
        self._repeat_position: int = 0
        self._allow_duplicate: bool = allow_duplicate
        self._item_ids: int = 0

        self.get_msg = get_msg

    def _alloc_id(self) -> int:
        self._item_ids += 1
        return self._item_ids

    def _wrap(self, item: Union[Track, QueueItem]) -> QueueItem:
        if isinstance(item, QueueItem):
            if item.item_id is None:
                item.item_id = self._alloc_id()
            return item
        return QueueItem(item_id=self._alloc_id(), track=item)

    def _unwrap(self, item: Union[Track, QueueItem, None]) -> Optional[Track]:
        if item is None:
            return None
        if isinstance(item, QueueItem):
            return item.track
        return item

    def _item_at(self, index: int) -> QueueItem:
        return self._queue[index]

    def queued_uris(self) -> List[str]:
        return [item.track.uri for item in self._queue]

    def session_track_data(self) -> List[dict]:
        return [item.track.data for item in self._queue]

    def ipc_track_payloads(self) -> List[dict]:
        return [
            {
                "trackId": item.track.track_id,
                "requesterId": str(getattr(getattr(item.track, "requester", None), "id", "")),
            }
            for item in self._queue
        ]

    def peek_next_item(self) -> Optional[QueueItem]:
        try:
            return self._queue[self._position]
        except IndexError:
            return None

    def current_slot_item(self) -> Optional[QueueItem]:
        try:
            return self._queue[self._position - 1]
        except IndexError:
            return None

    def get_item(self, *, force_next: bool = False, skip_exhausted: bool = False) -> Optional[QueueItem]:
        use_track_loop = self._repeat.mode == LoopType.TRACK and not force_next
        if skip_exhausted and use_track_loop:
            use_track_loop = False

        if use_track_loop:
            try:
                item = self._queue[self._position - 1]
                item.begin_new_cycle(self._alloc_id())
                return item
            except IndexError:
                return None

        scanned = 0
        limit = max(len(self._queue), 1) + 1
        while scanned < limit:
            scanned += 1
            try:
                item = self._queue[self._position]
                self._position += 1
            except IndexError:
                if self._repeat.mode == LoopType.QUEUE:
                    try:
                        item = self._queue[self._repeat_position]
                        self._position = self._repeat_position + 1
                    except IndexError:
                        self._repeat.set_mode(LoopType.OFF)
                        return None
                else:
                    return None
            if skip_exhausted and item.fail_exhausted:
                continue
            return item
        return None

    def get(self, *, force_next: bool = False, skip_exhausted: bool = False) -> Optional[Track]:
        return self._unwrap(self.get_item(force_next=force_next, skip_exhausted=skip_exhausted))

    def put(self, item: Union[Track, QueueItem]) -> int:
        if self.count >= self._size:
            raise QueueFull(self.get_msg("queue.errors.queueFull").format(self._size))

        self._queue.append(self._wrap(item))
        return self.count

    def put_at_front(self, item: Union[Track, QueueItem]) -> int:
        if self.count >= self._size:
            raise QueueFull(self.get_msg("queue.errors.queueFull").format(self._size))

        self._queue.insert(self._position, self._wrap(item))
        return 1

    def put_at_index(self, index: int, item: Union[Track, QueueItem]) -> None:
        if self.count >= self._size:
            raise QueueFull(self.get_msg("queue.errors.queueFull").format(self._size))

        return self._queue.insert(self._position - 1 + index, self._wrap(item))

    def skipto(self, index: int) -> None:
        if not 0 < index <= self.count:
            raise OutofList(self.get_msg("queue.errors.outOfList"))
        else:
            self._position += index - 1

    def backto(self, index: int) -> None:
        if not self._position - index >= 0:
            raise OutofList(self.get_msg("queue.errors.outOfList"))
        else:
            self._position -= index

    def prepare_user_reselect(self) -> Optional[QueueItem]:
        item = self.peek_next_item()
        if item is None:
            item = self.current_slot_item()
        if item is not None:
            item.clear_failure_for_user_select(self._alloc_id())
        return item

    def history_clear(self, is_playing: bool) -> None:
        self._queue[:self._position - 1 if is_playing else self._position] = []
        self._position = 1 if is_playing else 0

    def clear(self) -> None:
        del self._queue[self._position:]

    def replace(self, queue_type: str, replacement: list) -> None:
        wrapped: List[QueueItem] = []
        existing = {id(item.track): item for item in self._queue}
        for entry in replacement:
            if isinstance(entry, QueueItem):
                wrapped.append(entry)
            else:
                prior = existing.get(id(entry))
                wrapped.append(prior if prior is not None else self._wrap(entry))
        if queue_type == "queue":
            self.clear()
            self._queue += wrapped
        elif queue_type == "history":
            self._queue[:self._position] = wrapped

    def swap(self, track_index1: int, track_index2: int) -> Tuple[Track, Track]:
        try:
            adjusted_position = self._position - 1
            self._queue[adjusted_position + track_index1], self._queue[adjusted_position + track_index2] = self._queue[adjusted_position + track_index2], self._queue[adjusted_position + track_index1]
            return self._unwrap(self._queue[adjusted_position + track_index1]), self._unwrap(self._queue[adjusted_position + track_index2])
        except IndexError:
            raise OutofList(self.get_msg("queue.errors.outOfList"))

    def move(self, target: int, to: int) -> Optional[Track]:
        if not 0 < target <= self.count or not 0 < to:
            raise OutofList(self.get_msg("queue.errors.outOfList"))

        try:
            item = self._queue[self._position + target - 1]
            self._queue.remove(item)
            self.put_at_index(to, item)
            return self._unwrap(item)
        except:
            raise OutofList(self.get_msg("queue.errors.outOfList"))

    def remove(self, index: int, index2: int = None, member: discord.Member = None) -> Dict[int, Track]:
        pos = self._position - 1

        if index2 is None:
            index2 = index

        elif index2 < index:
            index, index2 = index2, index

        try:
            removed_tracks: Dict[int, Track] = {}
            for i, item in enumerate(list(self._queue[pos + index: pos + index2 + 1])):
                track = self._unwrap(item)
                if member and track.requester != member:
                    continue
            
                self._queue.remove(item)
                removed_tracks[pos + index + i] = track

            return removed_tracks
        except:
            raise OutofList(self.get_msg("queue.errors.outOfList"))

    def history(self, incTrack: bool = False) -> List[Track]:
        if incTrack:
            return [self._unwrap(item) for item in self._queue[:self._position]]
        return [self._unwrap(item) for item in self._queue[:self._position - 1]]

    def tracks(self, incTrack: bool = False) -> List[Track]:
        if incTrack:
            return [self._unwrap(item) for item in self._queue[self._position - 1:]]
        return [self._unwrap(item) for item in self._queue[self._position:]]

    @property
    def count(self) -> int:
        return len(self._queue[self._position:])
    
    @property
    def repeat(self) -> str:
        return self._repeat.mode.name.capitalize()

    @property
    def is_empty(self) -> bool:
        try:
            self._queue[self._position]
        except:
            return True
        return False

class FairQueue(Queue):
    def __init__(self, size: int, allow_duplicate: bool, get_msg) -> None:
        super().__init__(size, allow_duplicate, get_msg)
        self._set = set()

    def put(self, item: Union[Track, QueueItem]) -> int:
        if len(self._queue) >= self._size:
            raise QueueFull(self.get_msg("queue.errors.queueFull").format(self._size))

        tracks = self.tracks(incTrack=True)
        lastIndex = len(tracks)
        incoming = item.track if isinstance(item, QueueItem) else item
        for track in reversed(tracks):
            if track.requester == incoming.requester:
                break
            lastIndex -= 1
        self._set.clear()
        for track in tracks[lastIndex:]:
            if track.requester in self._set:
                break
            lastIndex += 1
            self._set.add(track.requester)

        self.put_at_index(lastIndex, item)
        return lastIndex
    
QUEUE_TYPES: Dict[str, Queue] = {
    "queue": Queue,
    "fairqueue": FairQueue
}
