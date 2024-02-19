from __future__ import annotations

import re
import function as func

from discord import Embed, Client

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .player import Player
    from .objects import Track

def ensure_track(func) -> callable:
    def wrapper(self: Placeholders, *args, **kwargs):
        current = self.get_current()
        if not current:
            return "None"
        return func(self, current, *args, **kwargs)
    return wrapper

class Placeholders:
    def __init__(self, bot: Client, player: Player = None) -> None:
        self.bot: Client = bot
        self.player: Player = player

        self.variables = {
            "channel_name": self.channel_name,
            "track_name": self.track_name,
            "track_url": self.track_url,
            "track_author": self.track_author,
            "track_duration": self.track_duration,
            "track_thumbnail": self.track_thumbnail,
            "track_color": self.track_color,
            "requester": self.requester,
            "requester_name": self.requester_name,
            "requester_avatar": self.requester_avatar,
            "queue_length": self.queue_length,
            "volume": self.volume,
            "dj": self.dj,
            "loop_mode": self.loop_mode,
            "default_embed_color": self.default_embed_color,
            "bot_icon": self.bot_icon,
            "server_invite_link": func.settings.invite_link,
            "invite_link": f"https://discord.com/oauth2/authorize?client_id={self.bot.user.id}&permissions=2184260928&scope=bot%20applications.commands"
        }
        
    def get_current(self) -> Track:
        return self.player.current if self.player else None

    def channel_name(self) -> str:
        return self.player.channel.name if self.player.channel else "None"
    
    @ensure_track
    def track_name(self, track: Track) -> str:
        return track.title

    @ensure_track
    def track_url(self, track: Track) -> str:
        return track.uri
    
    @ensure_track
    def track_author(self, track: Track) -> str:
        return track.author

    @ensure_track
    def track_duration(self, track: Track) -> str:
        return self.player.get_msg("live") if track.is_stream else func.time(track.length)
    
    @ensure_track
    def requester(self, track: Track) -> str:
        return track.requester.mention if track.requester else self.bot.user.mention
    
    @ensure_track
    def requester_name(self, track: Track) -> str:
        return track.requester.name if track.requester else self.bot.user.display_name
    
    @ensure_track
    def requester_avatar(self, track: Track) -> str:
        return track.requester.display_avatar.url if track.requester else self.bot.user.display_avatar.url
    
    @ensure_track
    def track_color(self, track: Track) -> int:
        return int(func.get_source(track.source, "color"), 16)
    
    def track_thumbnail(self) -> str:
        if not self.player or not self.player.current:
            return "https://i.imgur.com/dIFBwU7.png"
        
        return self.player.current.thumbnail or "https://cdn.discordapp.com/attachments/674788144931012638/823086668445384704/eq-dribbble.gif"

    def queue_length(self) -> str:
        return str(self.player.queue.count) if self.player else "0"
    
    def dj(self) -> str:
        if dj_id := self.player.settings.get("dj"):
            return f"<@&{dj_id}>"
        
        return self.player.dj.mention

    def volume(self) -> int:
        return self.player.volume if self.player else 0

    def loop_mode(self) -> str:
        return self.player.queue.repeat if self.player else "Off"

    def default_embed_color(self) -> int:
        return func.settings.embed_color

    def bot_icon(self) -> str:
        return self.bot.user.display_avatar.url if self.player else "https://i.imgur.com/dIFBwU7.png"
    
    def check_callable(self, value) -> str:
        return str(value()) if callable(value) else str(value)
    
    def evaluate_expression(self, s: str):
        if not (s.startswith("{{") and s.endswith("}}")) or "?? " not in s:
            return s

        inner = s[2:-2].strip()
        parts = inner.split("?? ")
        expr = parts[0]
        rest = parts[1] if len(parts) > 1 else ""
        true_val, false_val = rest.split("//") if "//" in rest else (rest, "")

        if not expr.strip() or not true_val.strip():
            return s

        operator_funcs = {
            "!=": lambda var_name, var_val: var_name.strip() in self.variables and self.check_callable(self.variables[var_name.strip()]) != var_val.strip(),
            "=": lambda var_name, var_val: var_name.strip() in self.variables and self.check_callable(self.variables[var_name.strip()]) == var_val.strip()
        }

        for operator, func in operator_funcs.items():
            if operator in expr:
                var_name, var_val = expr.split(operator)
                return true_val.strip() if func(var_name, var_val) else false_val.strip()

        if ">=" in expr or "<=" in expr:
            expr = expr.replace(">=", ">= ")
            expr = expr.replace("<=", "<= ")

        expr_parts = expr.split()
        for i, part in enumerate(expr_parts):
            if part in self.variables:
                expr_parts[i] = self.check_callable(self.variables[part])

        expr = " ".join(expr_parts)
        try:
            return true_val.strip() if eval(expr) else false_val.strip()
        except:
            return ""
        
    def replace(self, msg: str) -> str:
        if not msg:
            return

        try:
            msg = "".join([self.evaluate_expression(sub_s) for sub_s in re.split(r"(\{\{.*?\}\})", msg)])
            keys = re.findall(r'@@(.*?)@@', msg)
            for key in keys:
                value = self.variables.get(key.lower(), None)
                if value is not None:
                    msg = msg.replace(f"@@{key}@@", self.check_callable(value))
        except:
            pass

        return msg
    
def build_embed(raw: dict, placeholder: Placeholders) -> Embed:
    embed = Embed()
    try:
        if author := raw.get("author"):
            embed.set_author(
                name = placeholder.replace(author.get("name")),
                url = placeholder.replace(author.get("url")),
                icon_url = placeholder.replace(author.get("icon_url"))
            )
        
        if title := raw.get("title"):
            embed.title = placeholder.replace(title.get("name"))
            embed.url = placeholder.replace(title.get("url"))

        if fields := raw.get("fields", []):
            for f in fields:
                embed.add_field(name=placeholder.replace(f.get("name")), value=placeholder.replace(f.get("value")), inline=f.get("inline", False))

        if footer := raw.get("footer"):
            embed.set_footer(
                text = placeholder.replace(footer.get("text")),
                icon_url = placeholder.replace(footer.get("icon_url"))
            ) 

        if thumbnail := raw.get("thumbnail"):
            embed.set_thumbnail(url = placeholder.replace(thumbnail))
        
        if image := raw.get("image"):
            embed.set_image(url = placeholder.replace(image))

        embed.description = placeholder.replace(raw.get("description"))
        embed.color = int(placeholder.replace(raw.get("color")))

    except:
        pass

    return embed