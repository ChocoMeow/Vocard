"""MIT License

Copyright (c) 2023 Vocard Development

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

from .exceptions import QueueFull, OutofList, DuplicateTrack
from .objects import Track
from discord import Member

class Queue:
    def __init__(self, size: int, duplicate_track: bool, get_msg):
        self._queue = []
        self._position = 0
        self._size = size
        self._repeat = 0
        self._repeat_position = 0
        self._duplicate_track = duplicate_track

        self._repeat_mode = {
            0: "off",
            1: "track",
            2: "queue",
        }

        self.get_msg = get_msg

    def get(self):
        track = None
        try:
            track = self._queue[self._position -
                                1 if self._repeat == 1 else self._position]
            if self._repeat != 1:
                self._position += 1
        except:
            if self._repeat == 2:
                try:
                    track = self._queue[self._repeat_position]
                    self._position = self._repeat_position + 1
                except IndexError:
                    self._repeat = 0

        return track

    def put(self, item: Track) -> int:
        if self.count >= self._size:
            raise QueueFull(self.get_msg("voicelinkQueueFull").format(self._size))

        if not self._duplicate_track:
            if item.uri in [track.uri for track in self._queue]:
                raise DuplicateTrack(self.get_msg("voicelinkDuplicateTrack"))

        self._queue.append(item)
        return self.count

    def put_at_front(self, item: Track):
        if self.count >= self._size:
            raise QueueFull(self.get_msg("voicelinkQueueFull").format(self._size))

        if not self._duplicate_track:
            if item.uri in [track.uri for track in self._queue]:
                raise DuplicateTrack(self.get_msg("voicelinkDuplicateTrack"))

        self._queue.insert(self._position, item)
        return 1

    def put_at_index(self, index: int, item: Track):
        if self.count >= self._size:
            raise QueueFull(self.get_msg("voicelinkQueueFull").format(self._size))

        if not self._duplicate_track:
            if item.uri in [track.uri for track in self._queue]:
                raise DuplicateTrack(self.get_msg("voicelinkDuplicateTrack"))

        return self._queue.insert(self._position - 1 + index, item)

    def skipto(self, index: int):
        if not 0 < index <= self.count:
            raise OutofList(self.get_msg("voicelinkOutofList"))
        else:
            self._position += index - 1

    def backto(self, index: int):
        if not self._position - index >= 0:
            raise OutofList(self.get_msg("voicelinkOutofList"))
        else:
            self._position -= index

    def history_clear(self, is_playing: bool):
        self._queue[:self._position - 1 if is_playing else self._position] = []
        self._position = 1 if is_playing else 0

    def clear(self):
        del self._queue[self._position:]

    def replace(self, queue_type: str, replacement: list):
        if queue_type == "queue":
            self.clear()
            self._queue += replacement
        elif queue_type == "history":
            self._queue[:self._position] = replacement

    def swap(self, num1: int, num2: int):
        try:
            pos = self._position - 1
            self._queue[pos + num1], self._queue[pos + num2] = self._queue[pos + num2], self._queue[pos + num1]
            return self._queue[pos + num1], self._queue[pos + num2]
        except IndexError:
            raise OutofList(self.get_msg("voicelinkOutofList"))

    def move(self, target: int, to: int):
        if not 0 < target <= self.count or not 0 < to:
            raise OutofList(self.get_msg("voicelinkOutofList"))

        try:
            moveItem = self._queue[self._position + target - 1]
            self._queue.remove(moveItem)
            self.put_at_index(to, moveItem)
            return moveItem
        except:
            raise OutofList(self.get_msg("voicelinkOutofList"))

    def remove(self, index: int, index2: int = None, member: Member = None):
        pos = self._position - 1

        if index2 is None:
            index2 = index

        elif index2 < index:
            index, index2 = index2, index

        try:
            count = []
            for i, track in enumerate(self._queue[pos + index: pos + index2 + 1]):
                if member:
                    if track.requester != member:
                        continue
            
                self._queue.remove(track)
                count.append({"position": pos + index + i, "track": track})

            return count
        except:
            raise OutofList(self.get_msg("voicelinkOutofList"))

    def history(self, incTrack: bool = False) -> list:
        if incTrack:
            return self._queue[:self._position]
        return self._queue[:self._position - 1]

    def tracks(self, incTrack: bool = False):
        if incTrack:
            return self._queue[self._position - 1:]
        return self._queue[self._position:]

    @property
    def count(self):
        return len(self._queue[self._position:])

    @property
    def repeat(self):
        return self._repeat_mode.get(self._repeat, "Off").capitalize()

    @property
    def is_empty(self):
        try:
            self._queue[self._position]
        except:
            return True
        return False


class FairQueue(Queue):
    def __init__(self, size: int, duplicate_track: bool, get_msg):
        super().__init__(size, duplicate_track, get_msg)
        self._set = set()

    def put(self, item: Track) -> int:
        if len(self._queue) >= self._size:
            raise QueueFull(self.get_msg("voicelinkQueueFull").format(self._size))

        if not self._duplicate_track:
            if item.uri in [track.uri for track in self._queue]:
                raise DuplicateTrack(self.get_msg("voicelinkDuplicateTrack"))

        tracks = self.tracks(incTrack=True)
        lastIndex = len(tracks)
        for track in reversed(tracks):
            if track.requester == item.requester:
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
