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
        self.controller = settings.get("default_controller", 
        {
            "embeds": {
                "active": {
                    "description": "**Now Playing: ```[@@track_name@@]```\nLink: [Click Me](@@track_url@@) | Requester: @@requester@@ | DJ: @@dj@@**",
                    "footer": {
                        "text": "Queue Length: @@queue_length@@ | Duration: @@duration@@ | Volume: @@volume@@% {{loop_mode!=Off ?? | Repeat: @@loop_mode@@}}",
                    },
                    "image": "@@track_thumbnail@@",
                    "author": {
                        "name": "Music Controller | @@channel_name@@",
                        "icon_url": "@@bot_icon@@"
                    },
                    "color": "@@default_embed_color@@"
                },
                "inactive": {
                    "title": {
                        "name": "There are no songs playing right now"
                    },
                    "description": "[Support](@@server_invite_link@@) | [Invite](@@invite_link@@) | [Questionnaire](https://forms.gle/Qm8vjBfg2kp13YGD7)",
                    "image": "https://i.imgur.com/dIFBwU7.png",
                    "color": "@@default_embed_color@@"
                }
            },
            "default_buttons": [
                ["back", "resume", "skip", {"stop": "red"}, "add"],
                ["tracks"]
            ]
        })
        self.lyrics_platform = settings.get("lyrics_platform", "A_ZLyrics").lower()
        self.ipc_server = settings.get("ipc_server", {
                "host": "127.0.0.1",
                "port": 8000,
                "enable": False
            }
        )
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