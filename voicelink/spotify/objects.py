class Track:
    """The base class for a Spotify Track"""

    __slots__ = (
        "name",
        "artists",
        "artist_id",
        "length",
        "id",
        "image",
        "uri"
    )

    def __init__(self, data: dict, image = None) -> None:
        self.name: str = data.get('name', 'Unknown')
        self.artists: str = ", ".join(artist["name"] for artist in data.get('artists'))
        self.artist_id: list[str] = [artist['id'] for artist in data.get('artists')]
        self.length: int = data.get('duration_ms')
        self.id: str = data.get('id')
        self.image: str = images[0]["url"] if (images := data.get("album", {}).get("images")) else image
        self.uri: str = None if data["is_local"] else data["external_urls"]["spotify"]

    def to_dict(self) -> dict:
        return {
            "title": self.name,
            "author": self.artists,
            "length": self.length,
            "identifier": self.id,
            "artist_id": self.artist_id,
            "uri": self.uri,
            "isStream": False,
            "isSeekable": True,
            "position": 0,
            "artworkUrl": self.image
        }
    
    def __repr__(self) -> str:
        return (
            f"<Voicelink.spotify.Track name={self.name} artists={self.artists} "
            f"length={self.length} id={self.id}>"
        )

class Album:
    """The base class for a Spotify album"""

    __slots__ = (
        "name",
        "artists",
        "image",
        "tracks",
        "total_tracks",
        "id",
        "uri"
    )

    def __init__(self, data: dict) -> None:
        self.name: str = data.get('name', 'Unknown')
        self.artists: str = ", ".join(artist["name"] for artist in data.get('artists'))
        self.image: str = data["images"][0]["url"]
        self.tracks: list[Track] = [Track(track, image=self.image) for track in data["tracks"]["items"]]
        self.total_tracks: int = data["total_tracks"]
        self.id: str = data.get('id')
        self.uri: str = data["external_urls"]["spotify"]

    def __repr__(self) -> str:
        return (
            f"<Voicelink.spotify.Album name={self.name} artists={self.artists} id={self.id} "
            f"total_tracks={self.total_tracks} tracks={self.tracks}>"
        )

class Artist:
    """The base class for a Spotify playlist"""

    __slots__ = (
        "tracks",
        "image",
        "total_tracks",
        "owner",
        "id",
        "uri",
        "name"
    )
    def __init__(self, data: dict) -> None:
        self.tracks: list[Track] = [Track(track) for track in data['tracks']]
        if self.tracks:
            self.image: str = self.tracks[0].image
            self.total_tracks: int = len(self.tracks)
            self.owner: str = self.tracks[0].artists
            self.id: str = self.tracks[0].artist_id
            self.uri: str = data['tracks'][0]['album']['artists'][0]['external_urls']['spotify']
            self.name: str = f"Top tracks - {self.owner}"

    def __repr__(self) -> str:
        return (
            f"<Voicelink.spotify.Artist name={self.name} owner={self.owner} id={self.id} "
            f"total_tracks={self.total_tracks} tracks={self.tracks}>"
        )

class Playlist:
    """The base class for a Spotify playlist"""

    __slots__ = (
        "name",
        "tracks",
        "owner",
        "total_tracks",
        "id",
        "image",
        "uri"
    )
    
    def __init__(self, data: dict, tracks: list[Track]) -> None:
        self.name: str = data.get('name', 'Unknown')
        self.tracks: list[Track] = tracks
        self.owner: str = data["owner"]["display_name"]
        self.total_tracks: int = data["tracks"]["total"]
        self.id: str = data.get('id')
        self.image: str = data["images"][0]["url"] if len(data.get("images", [])) else None
        self.uri: str = data["external_urls"]["spotify"]

    def __repr__(self) -> str:
        return (
            f"<Voicelink.spotify.Playlist name={self.name} owner={self.owner} id={self.id} "
            f"total_tracks={self.total_tracks} tracks={self.tracks}>"
        )