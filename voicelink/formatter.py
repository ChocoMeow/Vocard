from __future__ import annotations

import base64, io, abc, struct, dataclasses

from typing import Union, BinaryIO, Optional, TYPE_CHECKING
if TYPE_CHECKING:
    from .objects import Track

@dataclasses.dataclass(frozen=True)
class Codec:
    encoding: str
    error_handler: str

    def encode(self, data: str) -> bytes:
        return data.encode(self.encoding, self.error_handler)

    def decode(self, data: bytes) -> str:
        return data.decode(self.encoding, self.error_handler)

UTF8 = Codec("utf-8", "surrogatepass")

_FORMAT_BOOL = "?"
_FORMAT_BYTE = "b"
_FORMAT_INT = ">i"
_FORMAT_LONG = ">q"
_FORMAT_USHORT = ">H"

class HasStream(abc.ABC):
    @property
    @abc.abstractmethod
    def stream(self) -> BinaryIO:
        ...

class Reader(HasStream):
    def __init__(self, stream: Union[BinaryIO, HasStream]) -> None:
        self._stream: BinaryIO = stream.stream if isinstance(stream, HasStream) else stream

    @property
    def stream(self) -> BinaryIO:
        return self._stream

    def read_bool(self) -> bool:
        return struct.unpack(_FORMAT_BOOL, self._stream.read(1))[0]

    def read_byte(self) -> int:
        return struct.unpack(_FORMAT_BYTE, self._stream.read(1))[0]

    def read_int(self) -> int:
        return struct.unpack(_FORMAT_INT, self._stream.read(4))[0]

    def read_long(self) -> int:
        return struct.unpack(_FORMAT_LONG, self._stream.read(8))[0]

    def read_ushort(self) -> int:
        return struct.unpack(_FORMAT_USHORT, self._stream.read(2))[0]

    def read_utf(self) -> str:
        length = self.read_ushort()
        data = self._stream.read(length)
        return UTF8.decode(data)

    def read_optional_utf(self) -> Optional[str]:
        if self.read_bool():
            return self.read_utf()
        else:
            return None

class Writer:
    _stream: BinaryIO

    def __init__(self, stream: Union[BinaryIO, HasStream] = None ) -> None:
        if stream is None:
            stream = io.BytesIO()
        elif isinstance(stream, HasStream):
            stream = stream.stream

        self._stream = stream
        self._string_codec: Codec = UTF8

    @property
    def stream(self) -> BinaryIO:
        return self._stream

    def write_bool(self, data: bool) -> None:
        self._stream.write(struct.pack(_FORMAT_BOOL, data))

    def write_byte(self, data: int) -> None:
        self._stream.write(struct.pack(_FORMAT_BYTE, data))

    def write_int(self, data: int) -> None:
        self._stream.write(struct.pack(_FORMAT_INT, data))

    def write_long(self, data: int) -> None:
        self._stream.write(struct.pack(_FORMAT_LONG, data))

    def write_ushort(self, data: int) -> None:
        self._stream.write(struct.pack(_FORMAT_USHORT, data))

    def write_utf(self, data: str) -> None:
        data = self._string_codec.encode(data)
        self.write_ushort(len(data))
        self._stream.write(data)

    def write_optional_utf(self, data: Optional[str]) -> None:
        if data is None:
            self.write_bool(False)
        else:
            self.write_bool(True)
            self.write_utf(data)

class MessageInput(HasStream):
    def __init__(self, stream: Union[BinaryIO, HasStream]) -> None:
        self._stream: Reader = Reader(stream)
        self._flags: int = 0
        self._size: int = 0

    @property
    def stream(self) -> BinaryIO:
        return self._stream.stream

    @property
    def flags(self) -> int:
        return self._flags

    def next(self) -> Optional[Reader]:
        value = self._stream.read_int()
        self._flags = (value & 0xC0000000) >> 30
        self._size = value & 0x3FFFFFFF

        if not self._size:
            return None

        data = self._stream.stream.read(self._size)

        return Reader(io.BytesIO(data))

class MessageOutput(HasStream):
    _stream: Writer
    _body_stream: io.BytesIO

    def __init__(self, stream: Union[BinaryIO, HasStream]) -> None:
        self._string_codec: Codec = UTF8

        self._stream = Writer(stream)
        self._body_stream = io.BytesIO()

    @property
    def stream(self) -> BinaryIO:
        return self._stream.stream

    def start(self) -> Writer:
        self._body_stream.truncate(0)
        self._body_stream.seek(0)
        return Writer(self._body_stream)

    def commit(self, flags: int = None) -> None:
        data = self._body_stream.getvalue()
        header = len(data)
        if flags:
            header |= flags << 30

        self._stream.write_int(header)
        self._stream.stream.write(data)

    def finish(self) -> None:
        self._stream.write_int(0)

class TrackDecoder:
    """TrackDecoder for track messages."""

    def decode(self, stream: MessageInput):
        """Decode an entire message and return the `Track`."""

        body_reader = stream.next()
        if not body_reader:
            raise ValueError("empty stream")

        version = body_reader.read_byte()

        return {
            "title": body_reader.read_utf(),
            "author": body_reader.read_utf(),
            "length": body_reader.read_long(),
            "identifier": body_reader.read_utf(),
            "is_stream": body_reader.read_bool(),
            "uri": body_reader.read_optional_utf(),
            "artworkUrl": None if version not in [0, 3] else body_reader.read_optional_utf(),
            "isrc": None if version != 3 else body_reader.read_optional_utf(),
            "sourceName": body_reader.read_utf(),
            "position": body_reader.read_long()
        }
    
class TrackEncoder:
    def encode(self, stream: MessageOutput, track: Track) -> None:
        body_writer = stream.start()

        body_writer.write_byte(0)
        body_writer.write_utf(track.title)
        body_writer.write_utf(track.author)
        body_writer.write_long(track.length)
        body_writer.write_utf(track.identifier)
        body_writer.write_bool(track.is_stream)
        body_writer.write_optional_utf(track.uri)
        body_writer.write_optional_utf(track.thumbnail)
        body_writer.write_utf(track.source)
        body_writer.write_long(0)

        stream.commit()

def decode(data: Union[str, bytes]) -> dict:
    decoded = base64.b64decode(data)
    stream = MessageInput(io.BytesIO(decoded))
    return TrackDecoder().decode(stream)

def encode(track) -> bytes:
    buf = io.BytesIO()
    stream = MessageOutput(buf)
    TrackEncoder().encode(stream, track)
    return base64.b64encode(buf.getvalue()).decode("utf-8")
