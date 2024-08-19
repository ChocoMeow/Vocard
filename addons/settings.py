from typing import (
    Dict,
    List,
    Any,
    Union
)

class Settings:
    def __init__(self, settings: Dict) -> None:
        self.token: str = settings.get("token")
        self.client_id: int = int(settings.get("client_id", 0))
        self.spotify_client_id: str = settings.get("spotify_client_id")
        self.spotify_client_secret: str = settings.get("spotify_client_secret")
        self.genius_token: str = settings.get("genius_token")
        self.mongodb_url: str = settings.get("mongodb_url")
        self.mongodb_name: str = settings.get("mongodb_name")
        
        self.invite_link: str = "https://discord.gg/wRCgB7vBQv"
        self.nodes: Dict[str, Dict[str, Union[str, int, bool]]] = settings.get("nodes", {})
        self.max_queue: int = settings.get("default_max_queue", 1000)
        self.bot_prefix: str = settings.get("prefix", "")
        self.activity: List[Dict[str, str]] = settings.get("activity", [{"listen": "/help"}])
        self.logging: Dict[Union[str, Dict[str, Union[str, bool]]]] = settings.get("logging", {})
        self.embed_color: str = int(settings.get("embed_color", "0xb3b3b3"), 16)
        self.bot_access_user: List[int] = settings.get("bot_access_user", [])
        self.sources_settings: Dict[Dict[str, str]] = settings.get("sources_settings", {})
        self.cooldowns_settings: Dict[str, List[int]] = settings.get("cooldowns", {})
        self.aliases_settings: Dict[str, List[str]] = settings.get("aliases", {})
        self.controller: Dict[str, Dict[str, Any]] = settings.get("default_controller", {})
        self.voice_status_template: str = settings.get("default_voice_status_template", "")
        self.lyrics_platform: str = settings.get("lyrics_platform", "A_ZLyrics").lower()
        self.ipc_client: Dict[str, Union[str, bool, int]] = settings.get("ipc_client", {})
        self.version: str = settings.get("version", "")