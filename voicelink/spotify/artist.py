from .track import Track

class Artist:
    """The base class for a Spotify playlist"""

    def __init__(self, data: dict) -> None:
        self.tracks = [ Track(track) for track in data['tracks'] ]
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
