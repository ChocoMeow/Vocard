class SpotifyRequestException(Exception):
    """An error occurred when making a request to the Spotify API"""
    pass


class InvalidSpotifyURL(Exception):
    """An invalid Spotify URL was passed"""
    pass
