class Asset:
    def __init__(self, userId: str, key: str):
        self.key = key
        self.url = f"https://cdn.discordapp.com/avatars/{userId}/{key}.png"

class User:
    def __init__(self, data: dict):
        self.id = int(data.get("id"))
        self.username = data.get("username")
        self.display_name = data.get("display_name")
        self.avatar = Asset(self.id, data.get("avatar"))
        self.avatar_decoration = data.get("avatar_decoration")
        self.discriminator = data.get("discriminator")
        self.public_flag = data.get("public_flag")
        self.flags = data.get("flags")
        self.banner = data.get("banner")
        self.banner_color = data.get("banner_color")
        self.locale = data.get("locale")
        self.mfa_enabled = data.get("mfa_enabled")
        self.premium_type = data.get("premium_type")
        self.access_token = data.get("access_token")
        self.refresh_token = data.get("refresh_token")
        
        self.sid = None
        self.guild_id = None