from discord.ext import commands
from re import findall
from importlib import import_module

class Placeholders:
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.voicelink = import_module("voicelink")
        self.variables = {
            "guilds": self.guilds_count,
            "users": self.users_count,
            "players": self.players_count,
            "nodes": self.nodes_count
        }
    
    def guilds_count(self) -> int:
        return len(self.bot.guilds)
    
    def users_count(self) -> int:
        return len(self.bot.users)
    
    def players_count(self) -> int:
        count = 0
        for node in self.voicelink.NodePool._nodes.values():
            count += len(node._players)

        return count
    
    def nodes_count(self):
        return len(self.voicelink.NodePool._nodes)
    
    def replace(self, msg: str) -> str:
        keys = findall(r'@@(.*?)@@', msg)

        for key in keys:
            value = self.variables.get(key.lower(), None)
            if value:
                msg = msg.replace(f"@@{key}@@", str(value()))

        return msg