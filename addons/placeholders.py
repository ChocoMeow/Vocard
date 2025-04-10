"""MIT License

Copyright (c) 2023 - present Vocard Development

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

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