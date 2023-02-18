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
    def __init__(self, size:int, duplicateTrack: bool, get_msg):

        self._queue = []
        self._position = 0
        self._size = size
        self._repeat = 0
        self._repeat_position = 0
        self._duplicateTrack = duplicateTrack
        self.get_msg = get_msg
    
    async def get(self):
        track = None
        try:
            track = self._queue[self._position - 1 if self._repeat == 1 else self._position]
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

    async def put(self, item: Track) -> int:
        if len(self._queue) >= self._size:
            raise QueueFull(self.get_msg("voicelinkQueueFull").format(self._size))
        
        if not self._duplicateTrack:
            if item.uri in [track.uri for track in self._queue]:
                raise DuplicateTrack(self.get_msg("voicelinkDuplicateTrack"))

        self._queue.append(item)
        return self.count
    
    async def put_at_front(self, item: Track):
        if len(self._queue) >= self._size:
            raise QueueFull(self.get_msg("voicelinkQueueFull").format(self._size))
        
        if not self._duplicateTrack:
            if item.uri in [track.uri for track in self._queue]:
                raise DuplicateTrack(self.get_msg("voicelinkDuplicateTrack"))

        return self._queue.insert(self._position, item)
    
    async def put_at_index(self, index: int, item: Track):
        if len(self._queue) >= self._size:
            raise QueueFull(self.get_msg("voicelinkQueueFull").format(self._size))
        
        if not self._duplicateTrack:
            if item.uri in [track.uri for track in self._queue]:
                raise DuplicateTrack(self.get_msg("voicelinkDuplicateTrack"))

        return self._queue.insert(self._position - 1 + index, item)

    async def skipto(self, index: int):
        if not 0 < index <= self.count:
            raise OutofList(self.get_msg("voicelinkOutofList"))
        else:
            self._position += index - 1
    
    def backto(self, index: int):
        if not self._position - index >= 0:
            raise OutofList(self.get_msg("voicelinkOutofList"))
        else:
            self._position -= index
    
    def set_repeat(self, mode:str):
        if mode == 'track':
            self._repeat = 1
        elif mode == 'queue':
            self._repeat = 2
            self._repeat_position = self._position - 1
        else:
            self._repeat = 0

    def history_clear(self, is_playing: bool):
        self._queue[:self._position - 1 if is_playing else self._position] = []
        self._position = 1 if is_playing else 0

    def clear(self):
        del self._queue[self._position:]

    def replace(self, queuetype:str, replacement:list):
        if queuetype == "Queue":
            self.clear()
            self._queue += replacement
        elif queuetype == "History":
            self._queue[:self._position] = replacement
    
    def swap(self, num1:int, num2:int):
        try:
            pos = self._position - 1
            self._queue[pos + num1], self._queue[pos + num2] = self._queue[pos + num2], self._queue[pos + num1]
        except IndexError:
            raise OutofList(self.get_msg("voicelinkOutofList"))

    def remove(self, index:int, index2:int, member: Member = None):
        pos = self._position - 1
        if not index2:
            index2 = index
        count = 0
        try:
            for track in self._queue[pos + index: pos + index2 + 1]:
                if member:
                    if track.requester == member:
                        self._queue.remove(track)
                        count += 1
                    continue
                else:
                    self._queue.remove(track)
                    count += 1
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
        return "Off" if self._repeat == 0 else ("Track" if self._repeat == 1 else "Queue")

    @property
    def is_empty(self):
        try:
            self._queue[self._position]
        except:
            return True
        return False

class FairQueue(Queue):
    def __init__(self, size:int, duplicateTrack: bool, get_msg):
        super().__init__(size, duplicateTrack, get_msg)
        self._set = set()

    async def put(self, item: Track) -> int:
        if len(self._queue) >= self._size:
            raise QueueFull(self.get_msg("voicelinkQueueFull").format(self._size))

        if not self._duplicateTrack:
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
                break;
            lastIndex += 1
            self._set.add(track.requester)
        await self.put_at_index(lastIndex, item)
        return lastIndex