import os
from dotenv import load_dotenv

class Settings:
    def __init__(self, settings: dict) -> None:
        self.invite_link = "https://discord.gg/wRCgB7vBQv"
        self.nodes = settings.get("nodes", {})
        self.max_queue = settings.get("default_max_queue", 1000)
        self.bot_prefix = settings.get("prefix", "")
        self.activity = settings.get("activity", [{"listen": "/help"}])
        self.embed_color = int(settings.get("embed_color", "0xb3b3b3"), 16)
        self.bot_access_user = settings.get("bot_access_user", [])
        self.emoji_source_raw = settings.get("emoji_source_raw", {})
        self.cooldowns_settings = settings.get("cooldowns", {})
        self.aliases_settings = settings.get("aliases", {})
        self.controller = settings.get("default_controller", {})
        self.lyrics_platform = settings.get("lyrics_platform", "A_ZLyrics").lower()
        self.ipc_server = settings.get("ipc_server", {})
        self.version = settings.get("version", "")

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