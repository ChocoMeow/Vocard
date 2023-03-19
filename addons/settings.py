class Settings:
    def __init__(self, settings: dict) -> None:
        self.invite_link = "https://discord.gg/wRCgB7vBQv"
        self.nodes = settings.get("nodes", {})
        self.max_queue = settings.get("default_max_queue", 1000)
        self.bot_prefix = settings.get("prefix", "")
        self.embed_color = int(settings.get("embed_color", "0xb3b3b3"), 16)
        self.bot_access_user = settings.get("bot_access_user", [])
        self.emoji_source_raw = settings.get("emoji_source_raw", {})
        self.cooldowns_settings = settings.get("cooldowns", {})
        self.aliases_settings = settings.get("aliases", {})
        self.controller_settings = settings.get("controller", [["back", "resume", "skip", {"stop": "red"}, "add"], ["tracks"]])
        self.ipc_server = settings.get("ipc_server", {
                "host": "127.0.0.1",
                "port": 8000,
                "enable": False
            }
        )