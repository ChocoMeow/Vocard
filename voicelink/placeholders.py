import re

import function as func

class Placeholders:
    def __init__(self, player) -> None:
        self.player = player
        self.variables = {
            "channel_name": self.channel_name,
            "track_name": self.track_name,
            "track_url": self.track_url,
            "track_thumbnail": self.track_thumbnail,
            "requester": self.requester,
            "duration": self.duration,
            "queue_length": self.queue_length,
            "volume": self.volume,
            "dj": self.dj,
            "loop_mode": self.loop_mode,
            "default_embed_color": self.default_embed_color,
            "bot_icon": self.bot_icon,
            "server_invite_link": func.settings.invite_link,
            "invite_link": f"https://discord.com/oauth2/authorize?client_id={self.player._bot.user.id}&permissions=2184260928&scope=bot%20applications.commands"
        }
    
    @property
    def channel_name(self) -> str:
        if not self.player.channel:
            return "None"
        
        return self.player.channel.name

    @property
    def track_name(self) -> str:
        if self.player.current is None:
            return "None"
        
        return self.player.current.title

    @property
    def track_url(self) -> str:
        if self.player.current is None:
            return ""
        
        return self.player.current.uri

    @property
    def track_thumbnail(self) -> str:
        if self.player.current is None:
            return ""
        
        return self.player.current.thumbnail
    
    @property
    def requester(self) -> str:
        if self.player.current is None:
            return "None"
        
        if requester := self.player.current.requester:
            return requester.mention
        else:
            return self.player._bot.user.mention
    
    @property
    def duration(self) -> str:
        track = self.player.current
        if not track:
            return "None"
        
        return self.player.get_msg("live") if track.is_stream else func.time(track.length)

    @property
    def dj(self) -> str:
        if dj_id := self.player.settings.get("dj"):
            return f"<@&{dj_id}>"
        
        return self.player.dj.mention
    
    @property
    def queue_length(self) -> str:
        return str(self.player.queue.count)
    
    @property
    def volume(self) -> int:
        return self.player.volume
    
    @property
    def loop_mode(self) -> str:
        return self.player.queue.repeat

    @property
    def default_embed_color(self) -> int:
        return func.settings.embed_color

    @property
    def bot_icon(self) -> str:
        return self.player._bot.user.display_avatar
    
    def evaluate_expression(self, s: str):
        if not s.startswith("{{") or not s.endswith("}}"):
            return s
        inner = s[2:-2].strip()
        if "?? " not in inner:
            return s
        if "//" in inner:
            expr, rest = inner.split("?? ")
            true_val, false_val = rest.split("//")
        else:
            expr, true_val = inner.split("?? ")
            false_val = ""
        if not expr.strip() or not true_val.strip():
            return s
        if "!=" in expr:
            var_name, var_val = expr.split("!=")
            if var_name.strip() in self.variables and str(self.variables[var_name.strip()]) != var_val.strip():
                return true_val.strip()
            else:
                return false_val.strip()
        elif "=" in expr:
            var_name, var_val = expr.split("=")
            if var_name.strip() in self.variables and str(self.variables[var_name.strip()]) == var_val.strip():
                return true_val.strip()
            else:
                return false_val.strip()
        else:
            if ">=" in expr or "<=" in expr:
                expr = expr.replace(">=", ">= ")
                expr = expr.replace("<=", "<= ")
            expr_parts = expr.split()
            for i, part in enumerate(expr_parts):
                if part in self.variables:
                    expr_parts[i] = str(self.variables[part])
            expr = " ".join(expr_parts)
            try:
                if eval(expr):
                    return true_val.strip()
                else:
                    return false_val.strip()
            except:
                return ""
        
    def replace(self, msg: str) -> str:
        if not msg:
            return
        
        msg = "".join([self.evaluate_expression(sub_s) for sub_s in re.split(r"(\{\{.*?\}\})", msg)])
        keys = re.findall(r'@@(.*?)@@', msg)
        for key in keys:
            value = self.variables.get(key.lower(), None)
            if value is None:
                continue

            msg = msg.replace(f"@@{key}@@", str(value))

        return msg