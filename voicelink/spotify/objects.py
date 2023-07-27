from typing import List

class Track:
    """The base class for a Spotify Track"""

    def __init__(self, data: dict, image=None) -> None:
        self.name = data.get('name', 'Unknown')
        self.artists = ", ".join(artist["name"] for artist in data.get('artists'))
        self.artistId = [artist['id'] for artist in data.get('artists')]
        self.length = data.get('duration_ms')
        self.id = data.get('id')

        if data.get("album") and data["album"].get("images"):
            self.image = data["album"]["images"][0]["url"]
        else:
            self.image = image

        if data["is_local"]:
            self.uri = None
        else:
            self.uri = data["external_urls"]["spotify"]

    def to_dict(self) -> dict:
        return {
            "title": self.name,
            "author": self.artists,
            "length": self.length,
            "identifier": self.id,
            "artistId": self.artistId,
            "uri": self.uri,
            "isStream": False,
            "isSeekable": True,
            "position": 0,
            "thumbnail": self.image
        }
    
    def __repr__(self) -> str:
        return (
            f"<Voicelink.spotify.Track name={self.name} artists={self.artists} "
            f"length={self.length} id={self.id}>"
        )

class Album:
    """The base class for a Spotify album"""

    def __init__(self, data: dict) -> None:
        self.name = data.get('name', 'Unknown')
        self.artists = ", ".join(artist["name"] for artist in data.get('artists'))
        self.image = data["images"][0]["url"]
        self.tracks = [Track(track, image=self.image) for track in data["tracks"]["items"]]
        self.total_tracks = data["total_tracks"]
        self.id = data.get('id')
        self.uri = data["external_urls"]["spotify"]

    def __repr__(self) -> str:
        return (
            f"<Voicelink.spotify.Album name={self.name} artists={self.artists} id={self.id} "
            f"total_tracks={self.total_tracks} tracks={self.tracks}>"
        )

class Artist:
    """The base class for a Spotify playlist"""

    def __init__(self, data: dict) -> None:
        self.tracks = [Track(track) for track in data['tracks']]
        if self.tracks:
            self.image = self.tracks[0].image
            self.total_tracks = len(self.tracks)
            self.owner = self.tracks[0].artists
            self.id = self.tracks[0].artistId
            self.uri = data['tracks'][0]['album']['artists'][0]['external_urls']['spotify']
            self.name = f"Top tracks - {self.owner}"

    def __repr__(self) -> str:
        return (
            f"<Voicelink.spotify.Artist name={self.name} owner={self.owner} id={self.id} "
            f"total_tracks={self.total_tracks} tracks={self.tracks}>"
        )

class Playlist:
    """The base class for a Spotify playlist"""

    def __init__(self, data: dict, tracks: List[Track]) -> None:
        self.name = data.get('name', 'Unknown')
        self.tracks = tracks
        self.owner = data["owner"]["display_name"]
        self.total_tracks = data["tracks"]["total"]
        self.id = data.get('id')
        if data.get("images") and len(data["images"]):
            self.image = data["images"][0]["url"]
        else:
            self.image = None
        self.uri = data["external_urls"]["spotify"]

    def __repr__(self) -> str:
        return (
            f"<Voicelink.spotify.Playlist name={self.name} owner={self.owner} id={self.id} "
            f"total_tracks={self.total_tracks} tracks={self.tracks}>"
        )