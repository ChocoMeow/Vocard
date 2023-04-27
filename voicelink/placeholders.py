from __future__ import annotations

import re
import function as func

from discord import Embed
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .player import Player

class Placeholders:
    def __init__(self, player: Player = None) -> None:
        self.player = player

        if player:
            self.variables = {
                "channel_name": self.channel_name,
                "track_name": self.track_name,
                "track_url": self.track_url,
                "track_thumbnail": self.track_thumbnail,
                "requester": self.requester,
                "requester_name": self.requester_name,
                "requester_avatar": self.requester_avatar,
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
        else:
            self.variables = {
                "channel_name": "Test Channel",
                "track_name": "Test Track",
                "track_url": "http://example.com",
                "track_thumbnail": "https://i.imgur.com/dIFBwU7.png",
                "requester": "<@12345678>",
                "requester_name": "Test",
                "requester_avatar": "https://i.imgur.com/dIFBwU7.png",
                "duration": "00:00",
                "queue_length": 0,
                "volume": 100,
                "dj": "<@12345678>",
                "loop_mode": "Off",
                "default_embed_color": self.default_embed_color,
                "bot_icon": "https://i.imgur.com/dIFBwU7.png",
                "server_invite_link": func.settings.invite_link,
                "invite_link": f"https://discord.com/oauth2/authorize?client_id={func.tokens.client_id}&permissions=2184260928&scope=bot%20applications.commands"
            }
        
    def channel_name(self) -> str:
        if not self.player.channel:
            return "None"
        
        return self.player.channel.name

    def track_name(self) -> str:
        if self.player.current is None:
            return "None"
        
        return self.player.current.title

    def track_url(self) -> str:
        if self.player.current is None:
            return ""
        
        return self.player.current.uri

    def track_thumbnail(self) -> str:
        if self.player.current is None:
            return ""
        
        return self.player.current.thumbnail or "https://cdn.discordapp.com/attachments/674788144931012638/823086668445384704/eq-dribbble.gif"

    def requester(self) -> str:
        if self.player.current is None:
            return "None"
        
        if requester := self.player.current.requester:
            return requester.mention
        else:
            return self.player._bot.user.mention
    
    def requester_name(self) -> str:
        if self.player.current is None:
            return "None"
        
        if requester := self.player.current.requester:
            return requester.name
        else:
            return self.player._bot.user.name
        
    def requester_avatar(self) -> str:
        if self.player.current is None:
            return "None"
        
        if requester := self.player.current.requester:
            return requester.display_avatar.url
        else:
            return self.player._bot.user.display_avatar.url
    
    def duration(self) -> str:
        track = self.player.current
        if not track:
            return "None"
        
        return self.player.get_msg("live") if track.is_stream else func.time(track.length)
    
    def dj(self) -> str:
        if dj_id := self.player.settings.get("dj"):
            return f"<@&{dj_id}>"
        
        return self.player.dj.mention

    def queue_length(self) -> str:
        return str(self.player.queue.count)

    def volume(self) -> int:
        return self.player.volume

    def loop_mode(self) -> str:
        return self.player.queue.repeat

    def default_embed_color(self) -> int:
        return func.settings.embed_color

    def bot_icon(self) -> str:
        return self.player._bot.user.display_avatar.url
    
    def check_callable(self, value):
        return str(value()) if callable(value) else str(value)
    
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
            if var_name.strip() in self.variables and self.check_callable(self.variables[var_name.strip()]) != var_val.strip():
                return true_val.strip()
            else:
                return false_val.strip()
        elif "=" in expr:
            var_name, var_val = expr.split("=")
            if var_name.strip() in self.variables and self.check_callable(self.variables[var_name.strip()]) == var_val.strip():
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
                    expr_parts[i] = self.check_callable(self.variables[part])
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
        
        try:
            msg = "".join([self.evaluate_expression(sub_s) for sub_s in re.split(r"(\{\{.*?\}\})", msg)])
            keys = re.findall(r'@@(.*?)@@', msg)
            for key in keys:
                value = self.variables.get(key.lower(), None)
                if value is None:
                    continue

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