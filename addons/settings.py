import os
from dotenv import load_dotenv

class Settings:
    def __init__(self, settings: dict) -> None:
        self.invite_link: str = "https://discord.gg/wRCgB7vBQv"
        self.nodes: dict = settings.get("nodes", {})
        self.max_queue: int = settings.get("default_max_queue", 1000)
        self.bot_prefix: str = settings.get("prefix", "")
        self.activity: dict = settings.get("activity", [{"listen": "/help"}])
        self.embed_color: str = int(settings.get("embed_color", "0xb3b3b3"), 16)
        self.bot_access_user: list = settings.get("bot_access_user", [])
        self.sources_settings: dict = settings.get("sources_settings", {})
        self.cooldowns_settings: dict = settings.get("cooldowns", {})
        self.aliases_settings: dict = settings.get("aliases", {})
        self.controller: dict = settings.get("default_controller", {})
        self.lyrics_platform: str = settings.get("lyrics_platform", "A_ZLyrics").lower()
        self.ipc_server: dict = settings.get("ipc_server", {})
        self.version: str = settings.get("version", "")

class TOKENS:
    def __init__(self) -> None:
        load_dotenv()

        self.token = os.getenv("TOKEN")
        self.client_id = os.getenv("CLIENT_ID")
        self.client_secret_id = os.getenv("CLIENT_SECRET_ID")
        self.sercet_key = os.getenv("SERCET_KEY")
        self.bug_report_channel_id = int(os.getenv("BUG_REPORT_CHANNEL_ID"))
        self.spotify_client_id = os.getenv("SPOTIFY_CLIENT_ID")
        self.spotify_client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")
        self.genius_token = os.getenv("GENIUS_TOKEN")
        self.mongodb_url = os.getenv("MONGODB_URL")
        self.mongodb_name = os.getenv("MONGODB_NAME")