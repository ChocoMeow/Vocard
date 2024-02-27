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

import collections
from .exceptions import FilterInvalidArgument, FilterTagAlreadyInUse, FilterTagInvalid

from typing import (
    Dict,
    List
)

class Filter:
    """
    The base class for all filters.
    You can use these filters if you have the latest Lavalink version
    installed. If you do not have the latest Lavalink version,
    these filters will not work.
    """
    def __init__(self):
        self.payload: Dict[str, List] = None
        self.tag: str = None

class Filters:
    def __init__(self) -> None:
        self._filters: List[Filter] = []

    def add_filter(self, *, filter: Filter) -> None:
        if self.has_filter(filter_tag=filter.tag):
            raise FilterTagAlreadyInUse("A filter with that tag is already in use")
        self._filters.append(filter)

    def remove_filter(self, *, filter_tag: str) -> None:
        if not self.has_filter(filter_tag=filter_tag):
            raise FilterTagInvalid("A filter with that tag was not found.")
        
        for index, filter in enumerate(self._filters):
            if filter.tag == filter_tag:
                del self._filters[index]
        
    def has_filter(self, *, filter_tag: str) -> bool:
        return any(f for f in self._filters if f.tag == filter_tag)
    
    def reset_filters(self) -> None:
        self._filters = []
    
    def get_all_payloads(self) -> dict:
        payload = {}
        for filter in self._filters:
            payload.update(filter.payload)
        return payload
    
    def get_filters(self) -> List[Filter]:
        return self._filters
        
class Equalizer(Filter):
    """
    Filter which represents a 15 band equalizer.
    You can adjust the dynamic of the sound using this filter.
    i.e: Applying a bass boost filter to emphasize the bass in a song.
    The format for the levels is: List[Tuple[int, float]]
    """

    def __init__(self, *, tag: str, levels: list):
        super().__init__()

        self.eq = self._factory(levels)
        self.raw = levels

        self.payload = {"equalizer": self.eq}
        self.tag = tag

    def _factory(self, levels: list):
        _dict = collections.defaultdict(int)

        _dict.update(levels)
        _dict = [{"band": i, "gain": _dict[i]} for i in range(15)]

        return _dict

    def __repr__(self) -> str:
        return f"<Voicelink.EqualizerFilter tag={self.tag} eq={self.eq} raw={self.raw}>"

    @classmethod
    def flat(cls):
        """Equalizer preset which represents a flat EQ board,
            with all levels set to their default values.
        """

        levels = [
            (0, 0.0), (1, 0.0), (2, 0.0), (3, 0.0), (4, 0.0),
            (5, 0.0), (6, 0.0), (7, 0.0), (8, 0.0), (9, 0.0),
            (10, 0.0), (11, 0.0), (12, 0.0), (13, 0.0), (14, 0.0)
        ]
        return cls(tag="flat", levels=levels)

    @classmethod
    def boost(cls):
        """Equalizer preset which boosts the sound of a track,
           making it sound fun and energetic by increasing the bass
           and the highs.
        """

        levels = [
            (0, -0.075), (1, 0.125), (2, 0.125), (3, 0.1), (4, 0.1),
            (5, .05), (6, 0.075), (7, 0.0), (8, 0.0), (9, 0.0),
            (10, 0.0), (11, 0.0), (12, 0.125), (13, 0.15), (14, 0.05)
        ]
        return cls(tag="boost", levels=levels)

    @classmethod
    def metal(cls):
        """Equalizer preset which increases the mids of a track, 
            preferably one of the metal genre, to make it sound 
            more full and concert-like.
        """

        levels = [
            (0, 0.0), (1, 0.1), (2, 0.1), (3, 0.15), (4, 0.13),
            (5, 0.1), (6, 0.0), (7, 0.125), (8, 0.175), (9, 0.175),
            (10, 0.125), (11, 0.125), (12, 0.1), (13, 0.075), (14, 0.0)
        ]

        return cls(tag="metal", levels=levels)

    @classmethod
    def piano(cls):
        """Equalizer preset which increases the mids and highs
            of a track, preferably a piano based one, to make it 
            stand out.
        """

        levels = [
            (0, -0.25), (1, -0.25), (2, -0.125), (3, 0.0),
            (4, 0.25), (5, 0.25), (6, 0.0), (7, -0.25), (8, -0.25),
            (9, 0.0), (10, 0.0), (11, 0.5), (12, 0.25), (13, -0.025)
        ]
        return cls(tag="piano", levels=levels)


class Timescale(Filter):
    """Filter which changes the speed and pitch of a track.
       You can make some very nice effects with this filter,
       i.e: a vaporwave-esque filter which slows the track down
       a certain amount to produce said effect.
    """

    def __init__(
        self, 
        *, 
        tag: str,
        speed: float = 1.0, 
        pitch: float = 1.0, 
        rate: float = 1.0
    ):
        super().__init__()

        if speed < 0:
            raise FilterInvalidArgument("Timescale speed must be more than 0.")
        if pitch < 0:
            raise FilterInvalidArgument("Timescale pitch must be more than 0.")
        if rate < 0:
            raise FilterInvalidArgument("Timescale rate must be more than 0.")

        self.speed = speed
        self.pitch = pitch
        self.rate = rate
        self.tag = tag

        self.payload = {
            "timescale": {
                "speed": self.speed,
                "pitch": self.pitch,
                "rate": self.rate
            }
        }

    @classmethod
    def vaporwave(cls):
        """Timescale preset which slows down the currently playing track, 
        giving it the effect of a half-speed record/casette playing.
        
        This preset will assign the tag 'vaporwave'.
        """

        return cls(tag="vaporwave", speed=0.8, pitch=0.8)

    @classmethod
    def nightcore(cls):
        """Timescale preset which speeds up the currently playing track,
        which matches up to nightcore, a genre of sped-up music
        
        This preset will assign the tag 'nightcore'.
        """

        return cls(tag="nightcore", speed=1.25, pitch=1.3)                    

    def __repr__(self):
        return f"<Voicelink.TimescaleFilter tag={self.tag} speed={self.speed} pitch={self.pitch} rate={self.rate}>"


class Karaoke(Filter):
    """Filter which filters the vocal track from any song and leaves the instrumental.
       Best for karaoke as the filter implies.
    """

    def __init__(
        self,
        *,
        tag: str,
        level: float = 1.0,
        mono_level: float = 1.0,
        filter_band: float = 220.0,
        filter_width: float = 100.0
    ):
        super().__init__()

        self.level = level
        self.mono_level = mono_level
        self.filter_band = filter_band
        self.filter_width = filter_width
        self.tag = tag

        self.payload = {
            "karaoke": {
                "level": self.level,
                "monoLevel": self.mono_level,
                "filterBand": self.filter_band,
                "filterWidth": self.filter_width
            }
        }

    def __repr__(self):
        return (
            f"<Voicelink.KaraokeFilter tag={self.tag} level={self.level} mono_level={self.mono_level} "
            f"filter_band={self.filter_band} filter_width={self.filter_width}>"
        )


class Tremolo(Filter):
    """Filter which produces a wavering tone in the music,
       causing it to sound like the music is changing in volume rapidly.
    """

    def __init__(
        self, 
        *, 
        tag: str,
        frequency: float = 2.0, 
        depth: float = 0.5
    ):
        super().__init__()

        if frequency < 0:
            raise FilterInvalidArgument("Tremolo frequency must be more than 0.")
        if depth < 0 or depth > 1:
            raise FilterInvalidArgument("Tremolo depth must be between 0 and 1.")

        self.frequency = frequency
        self.depth = depth
        self.tag = tag

        self.payload = {
            "tremolo": {
                "frequency": self.frequency,
                "depth": self.depth
            }
        }

    def __repr__(self):
        return f"<Voicelink.TremoloFilter tag={self.tag} frequency={self.frequency} depth={self.depth}>"


class Vibrato(Filter):
    """Filter which produces a wavering tone in the music, similar to the Tremolo filter,
       but changes in pitch rather than volume.
    """

    def __init__(
        self, 
        *, 
        tag: str,
        frequency: float = 2.0, 
        depth: float = 0.5
    ):

        super().__init__()
        if frequency < 0 or frequency > 14:
            raise FilterInvalidArgument("Vibrato frequency must be between 0 and 14.")
        if depth < 0 or depth > 1:
            raise FilterInvalidArgument("Vibrato depth must be between 0 and 1.")

        self.frequency = frequency
        self.depth = depth
        self.tag = tag

        self.payload = {
            "vibrato": {
                "frequency": self.frequency,
                "depth": self.depth
            }
        }
        
    def __repr__(self):
        return f"<Voicelink.VibratoFilter tag={self.tag} frequency={self.frequency} depth={self.depth}>"


class Rotation(Filter):
    """Filter which produces a stereo-like panning effect, which sounds like
    the audio is being rotated around the listener's head
    """

    def __init__(self, *, tag: str, rotation_hertz: float = 5):
        super().__init__()

        self.rotation_hertz = rotation_hertz
        self.tag = tag
        self.payload = {"rotation": {"rotationHz": self.rotation_hertz}}

    @classmethod
    def nightD(cls):
        return cls(tag="8d", rotation_hertz=0.2)

    def __repr__(self) -> str:
        return f"<Voicelink.RotationFilter tag={self.tag} rotation_hertz={self.rotation_hertz}>"


class ChannelMix(Filter):
    """Filter which manually adjusts the panning of the audio, which can make
    for some cool effects when done correctly.
    """

    def __init__(
        self,
        *,
        tag: str,
        left_to_left: float = 1,
        right_to_right: float = 1,
        left_to_right: float = 0,
        right_to_left: float = 0
    ):
        super().__init__()

        if 0 > left_to_left > 1:
            raise ValueError("'left_to_left' value must be more than or equal to 0 or less than or equal to 1.")
        if 0 > right_to_right > 1:
            raise ValueError("'right_to_right' value must be more than or equal to 0 or less than or equal to 1.")
        if 0 > left_to_right > 1:
            raise ValueError("'left_to_right' value must be more than or equal to 0 or less than or equal to 1.")
        if 0 > right_to_left > 1:
            raise ValueError("'right_to_left' value must be more than or equal to 0 or less than or equal to 1.")

        self.left_to_left = left_to_left
        self.left_to_right = left_to_right
        self.right_to_left = right_to_left
        self.right_to_right = right_to_right
        self.tag = tag

        self.payload = {
            "channelMix": {
                "leftToLeft": self.left_to_left, 
                "leftToRight": self.left_to_right, 
                "rightToLeft": self.right_to_left, 
                "rightToRight": self.right_to_right
            }
        }

    def __repr__(self) -> str:
        return ( 
            f"<Voicelink.ChannelMix tag={self.tag} left_to_left={self.left_to_left} left_to_right={self.left_to_right} "
            f"right_to_left={self.right_to_left} right_to_right={self.right_to_right}>" 
        )

class Distortion(Filter):
    """Filter which generates a distortion effect. Useful for certain filter implementations where
    distortion is needed. 
    """

    def __init__(
        self,
        *,
        tag: str,
        sin_offset: float =  0,
        sin_scale: float = 1,
        cos_offset: float = 0,
        cos_scale: float = 1,
        tan_offset: float = 0,
        tan_scale: float = 1,
        offset: float = 0,
        scale: float = 1
    ):
        super().__init__()

        self.sin_offset = sin_offset
        self.sin_scale = sin_scale
        self.cos_offset = cos_offset
        self.cos_scale = cos_scale
        self.tan_offset = tan_offset
        self.tan_scale = tan_scale
        self.offset = offset
        self.scale = scale
        self.tag = tag

        self.payload = {
            "distortion": {
                "sinOffset": self.sin_offset,
                "sinScale": self.sin_scale,
                "cosOffset": self.cos_offset,
                "cosScale": self.cos_scale,
                "tanOffset": self.tan_offset,
                "tanScale": self.tan_scale,
                "offset": self.offset,
                "scale": self.scale
            }
        }

    def __repr__(self) -> str:
        return (
            f"<Voicelink.Distortion tag={self.tag} sin_offset={self.sin_offset} sin_scale={self.sin_scale}> "
            f"cos_offset={self.cos_offset} cos_scale={self.cos_scale} tan_offset={self.tan_offset} "
            f"tan_scale={self.tan_scale} offset={self.offset} scale={self.scale}"
        )


class LowPass(Filter):
    """Filter which supresses higher frequencies and allows lower frequencies to pass.
    You can also do this with the Equalizer filter, but this is an easier way to do it.
    """

    def __init__(self, *, tag: str, smoothing: float = 20):
        super().__init__()

        self.smoothing = smoothing
        self.tag = tag
        self.payload = {"lowPass": {"smoothing": self.smoothing}}

    def __repr__(self) -> str:
        return f"<Voicelink.LowPass tag={self.tag} smoothing={self.smoothing}>"


