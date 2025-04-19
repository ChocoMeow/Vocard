"""
MIT License

Copyright (c) 2017-present Devoxin

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

import struct

from io import BytesIO
from base64 import b64decode, b64encode
from typing import Any, Callable, Dict, Mapping, Optional, Tuple, Final

V2_KEYSET = {'title', 'author', 'length', 'identifier', 'isStream', 'uri', 'sourceName', 'position'}
V3_KEYSET = V2_KEYSET | {'artworkUrl', 'isrc'}

class _MissingObj:
    __slots__ = ()

    def __repr__(self):
        return '...'

MISSING: Any = _MissingObj()

class DataReader:
    __slots__ = ('_buf', '_mark')

    def __init__(self, base64_str: str):
        self._buf: Final[BytesIO] = BytesIO(b64decode(base64_str))
        self._mark: Optional[int] = None

    @property
    def remaining(self) -> int:
        return self._buf.getbuffer().nbytes - self._buf.tell()

    def mark(self) -> None:
        self._mark = self._buf.tell()

    def rewind(self) -> None:
        if self._mark is None or not isinstance(self._mark, int):
            raise IOError('Cannot rewind buffer without a marker!')

        if self._mark < 0:
            raise IOError('Cannot rewind buffer to a negative position!')

        self._buf.seek(self._mark)
        self._mark = None

    def _read(self, count: int) -> bytes:
        return self._buf.read(count)

    def read_byte(self) -> bytes:
        return self._read(1)

    def read_boolean(self) -> bool:
        result, = struct.unpack('B', self.read_byte())
        return result != 0

    def read_unsigned_short(self) -> int:
        result, = struct.unpack('>H', self._read(2))
        return result

    def read_int(self) -> int:
        result, = struct.unpack('>i', self._read(4))
        return result

    def read_long(self) -> int:
        result, = struct.unpack('>Q', self._read(8))
        return result

    def read_nullable_utf(self, utfm: bool = False) -> Optional[str]:
        exists = self.read_boolean()

        if not exists:
            return None

        return self.read_utfm() if utfm else self.read_utf().decode()

    def read_utf(self) -> bytes:
        text_length = self.read_unsigned_short()
        return self._read(text_length)

    def read_utfm(self) -> str:
        text_length = self.read_unsigned_short()
        utf_string = self._read(text_length)
        return read_utfm(text_length, utf_string)

class DataWriter:
    __slots__ = ('_buf',)

    def __init__(self):
        self._buf: Final[BytesIO] = BytesIO()

    def _write(self, data):
        self._buf.write(data)

    def write_byte(self, byte):
        self._buf.write(byte)

    def write_boolean(self, boolean: bool):
        enc = struct.pack('B', 1 if boolean else 0)
        self.write_byte(enc)

    def write_unsigned_short(self, short: int):
        enc = struct.pack('>H', short)
        self._write(enc)

    def write_int(self, integer: int):
        enc = struct.pack('>i', integer)
        self._write(enc)

    def write_long(self, long_value: int):
        enc = struct.pack('>Q', long_value)
        self._write(enc)

    def write_nullable_utf(self, utf_string: Optional[str]):
        self.write_boolean(bool(utf_string))

        if utf_string:
            self.write_utf(utf_string)

    def write_utf(self, utf_string: str):
        utf = utf_string.encode('utf8')
        byte_len = len(utf)

        if byte_len > 65535:
            raise OverflowError('UTF string may not exceed 65535 bytes!')

        self.write_unsigned_short(byte_len)
        self._write(utf)

    def finish(self) -> bytes:
        with BytesIO() as track_buf:
            byte_len = self._buf.getbuffer().nbytes
            flags = byte_len | (1 << 30)
            enc_flags = struct.pack('>i', flags)
            track_buf.write(enc_flags)

            self._buf.seek(0)
            track_buf.write(self._buf.read())
            self._buf.close()

            track_buf.seek(0)
            return track_buf.read()

def decode_probe_info(reader: DataReader) -> Mapping[str, Any]:
    probe_info = reader.read_utf().decode()
    return {'probe_info': probe_info}

def decode_lavasrc_fields(reader: DataReader) -> Mapping[str, Any]:
    if reader.remaining <= 8:
        return {}

    album_name = reader.read_nullable_utf()
    album_url = reader.read_nullable_utf()
    artist_url = reader.read_nullable_utf()
    artist_artwork_url = reader.read_nullable_utf()
    preview_url = reader.read_nullable_utf()
    is_preview = reader.read_boolean()

    return {
        'album_name': album_name,
        'album_url': album_url,
        'artist_url': artist_url,
        'artist_artwork_url': artist_artwork_url,
        'preview_url': preview_url,
        'is_preview': is_preview
    }

DEFAULT_DECODER_MAPPING: Dict[str, Callable[[DataReader], Mapping[str, Any]]] = {
    'http': decode_probe_info,
    'local': decode_probe_info,
    'deezer': decode_lavasrc_fields,
    'spotify': decode_lavasrc_fields,
    'applemusic': decode_lavasrc_fields
}

def read_utfm(utf_len: int, utf_bytes: bytes) -> str:
    chars = []
    count = 0

    while count < utf_len:
        char = utf_bytes[count] & 0xff
        if char > 127:
            break

        count += 1
        chars.append(chr(char))

    while count < utf_len:
        char = utf_bytes[count] & 0xff
        shift = char >> 4

        if 0 <= shift <= 7:
            count += 1
            chars.append(chr(char))
        elif 12 <= shift <= 13:
            count += 2
            if count > utf_len:
                raise UnicodeDecodeError('utf8', b'', 0, utf_len, 'malformed input: partial character at end')
            char2 = utf_bytes[count - 1]
            if (char2 & 0xC0) != 0x80:
                raise UnicodeDecodeError('utf8', b'', 0, utf_len, f'malformed input around byte {count}')

            char_shift = ((char & 0x1F) << 6) | (char2 & 0x3F)
            chars.append(chr(char_shift))
        elif shift == 14:
            count += 3
            if count > utf_len:
                raise UnicodeDecodeError('utf8', b'', 0, utf_len, 'malformed input: partial character at end')

            char2 = utf_bytes[count - 2]
            char3 = utf_bytes[count - 1]

            if (char2 & 0xC0) != 0x80 or (char3 & 0xC0) != 0x80:
                raise UnicodeDecodeError('utf8', b'', 0, utf_len, f'malformed input around byte {(count - 1)}')

            char_shift = ((char & 0x0F) << 12) | ((char2 & 0x3F) << 6) | ((char3 & 0x3F) << 0)
            chars.append(chr(char_shift))
        else:
            raise UnicodeDecodeError('utf8', b'', 0, utf_len, f'malformed input around byte {count}')

    return ''.join(chars).encode('utf-16', 'surrogatepass').decode('utf-16')

def _read_track_common(reader: DataReader) -> Tuple[str, str, int, str, bool, Optional[str]]:
    title = reader.read_utfm()
    author = reader.read_utfm()
    length = reader.read_long()
    identifier = reader.read_utf().decode()
    is_stream = reader.read_boolean()
    uri = reader.read_nullable_utf()
    return (title, author, length, identifier, is_stream, uri)

def _write_track_common(track: Dict[str, Any], writer: DataWriter):
    writer.write_utf(track['title'])
    writer.write_utf(track['author'])
    writer.write_long(track['length'])
    writer.write_utf(track['identifier'])
    writer.write_boolean(track['isStream'])
    writer.write_nullable_utf(track['uri'])

def decode(
    track: str,
    source_decoders: Mapping[str, Callable[[DataReader], Mapping[str, Any]]] = MISSING
) -> dict:

    decoders = DEFAULT_DECODER_MAPPING.copy()

    if source_decoders is not MISSING:
        decoders.update(source_decoders)

    reader = DataReader(track)

    flags = (reader.read_int() & 0xC0000000) >> 30
    version, = struct.unpack('B', reader.read_byte()) if flags & 1 != 0 else (1,)

    title, author, length, identifier, is_stream, uri = _read_track_common(reader)
    extra_fields = {}

    if version == 3:
        extra_fields['artworkUrl'] = reader.read_nullable_utf()
        extra_fields['isrc'] = reader.read_nullable_utf()

    source = reader.read_utf().decode()
    source_specific_fields = {}

    if source in decoders:
        source_specific_fields.update(decoders[source](reader))

    position = reader.read_long()

    return {
        'title': title,
        'author': author,
        'length': length,
        'identifier': identifier,
        'isStream': is_stream,
        'uri': uri,
        'isSeekable': not is_stream,
        'sourceName': source,
        'position': position,
        **extra_fields
    }

def encode(
    track: Dict[str, Any],
    source_encoders: Mapping[str, Callable[[DataWriter, Dict[str, Any]], None]] = MISSING
) -> str:
    assert V3_KEYSET <= track.keys()

    writer = DataWriter()
    version = struct.pack('B', 3)
    writer.write_byte(version)
    _write_track_common(track, writer)
    writer.write_nullable_utf(track['artworkUrl'])
    writer.write_nullable_utf(track['isrc'])
    writer.write_utf(track['sourceName'])

    if source_encoders is not MISSING and track['sourceName'] in source_encoders:
        source_encoders[track['sourceName']](writer, track)

    writer.write_long(track['position'])

    enc = writer.finish()
    return b64encode(enc).decode()