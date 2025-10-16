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

import random
import time
import socket
import discord

from itertools import zip_longest
from typing import Dict, Optional, Union
from timeit import default_timer as timer
from discord.ext import commands
from discord.utils import MISSING

from .mongodb import MongoDBHandler
from .language import LangHandler

# __all__ = [
#     "ExponentialBackoff",
#     "NodeStats",
#     "NodeInfoVersion",
#     "NodeInfo",
#     "Plugin",
#     "Ping"
# ]

class ExponentialBackoff:
    """
    The MIT License (MIT)
    Copyright (c) 2015-present Rapptz
    Permission is hereby granted, free of charge, to any person obtaining a
    copy of this software and associated documentation files (the "Software"),
    to deal in the Software without restriction, including without limitation
    the rights to use, copy, modify, merge, publish, distribute, sublicense,
    and/or sell copies of the Software, and to permit persons to whom the
    Software is furnished to do so, subject to the following conditions:
    The above copyright notice and this permission notice shall be included in
    all copies or substantial portions of the Software.
    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
    OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
    FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
    AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
    LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
    FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
    DEALINGS IN THE SOFTWARE.
    """

    def __init__(self, base: int = 1, *, integral: bool = False) -> None:

        self._base = base

        self._exp = 0
        self._max = 10
        self._reset_time = base * 2 ** 11
        self._last_invocation = time.monotonic()

        rand = random.Random()
        rand.seed()

        self._randfunc = rand.randrange if integral else rand.uniform

    def delay(self) -> float:

        invocation = time.monotonic()
        interval = invocation - self._last_invocation
        self._last_invocation = invocation

        if interval > self._reset_time:
            self._exp = 0

        self._exp = min(self._exp + 1, self._max)
        return self._randfunc(0, self._base * 2 ** self._exp)


class NodeStats:
    """The base class for the node stats object.
       Gives critical information on the node, which is updated every minute.
    """

    def __init__(self, data: Dict) -> None:

        memory: Dict = data.get("memory")
        self.used: int = memory.get("used")
        self.free: int = memory.get("free")
        self.reservable: int = memory.get("reservable")
        self.allocated: int = memory.get("allocated")

        cpu: Dict = data.get("cpu")
        self.cpu_cores: int = cpu.get("cores")
        self.cpu_system_load: float = cpu.get("systemLoad")
        self.cpu_process_load: float = cpu.get("lavalinkLoad")

        self.players_active: int = data.get("playingPlayers")
        self.players_total: int = data.get("players")
        self.uptime: int = data.get("uptime")

    def __repr__(self) -> str:
        return f"<Voicelink.NodeStats total_players={self.players_total!r} playing_active={self.players_active!r}>"

class NodeInfoVersion:
    """The base class for the node info object.
       Gives version information on the node.
    """
    def __init__(self, data: Dict) -> None:
        self.semver: str = data.get("semver")
        self.major: int = data.get("major")
        self.minor: int = data.get("minor")
        self.patch: int = data.get("patch")
        self.pre_release: Optional[str] = data.get("preRelease")
        self.build: Optional[str] = data.get("build")

class NodeInfo:
    """The base class for the node info object.
       Gives basic information on the node.
    """
    def __init__(self, data: Dict) -> None:
        self.version: NodeInfoVersion = NodeInfoVersion(data.get("version"))
        self.build_time: int = data.get("buildTime")
        self.jvm: str = data.get("jvm")
        self.lavaplayer: str = data.get("lavaplayer")
        self.plugins: Optional[Dict[str, Plugin]] = [Plugin(plugin_data) for plugin_data in data.get("plugins")]

class Plugin:
    """The base class for the plugin object.
       Gives basic information on the plugin.
    """
    def __init__(self, data: Dict) -> None:
        self.name: str = data.get("name")
        self.version: str = data.get("version")

class Ping:
    # Thanks to https://github.com/zhengxiaowai/tcping for the nice ping impl
    def __init__(self, host, port, timeout=5):
        self.timer = self.Timer()

        self._successed = 0
        self._failed = 0
        self._conn_time = None
        self._host = host
        self._port = port
        self._timeout = timeout

    class Socket(object):
        def __init__(self, family, type_, timeout):
            s = socket.socket(family, type_)
            s.settimeout(timeout)
            self._s = s

        def connect(self, host, port):
            self._s.connect((host, int(port)))

        def shutdown(self):
            self._s.shutdown(socket.SHUT_RD)

        def close(self):
            self._s.close()


    class Timer(object):
        def __init__(self):
            self._start = 0
            self._stop = 0

        def start(self):
            self._start = timer()

        def stop(self):
            self._stop = timer()

        def cost(self, funcs, args):
            self.start()
            for func, arg in zip_longest(funcs, args):
                if arg:
                    func(*arg)
                else:
                    func()

            self.stop()
            return self._stop - self._start

    def _create_socket(self, family, type_):
        return self.Socket(family, type_, self._timeout)

    def get_ping(self):
        s = self._create_socket(socket.AF_INET, socket.SOCK_STREAM)
     
        cost_time = self.timer.cost(
            (s.connect, s.shutdown),
            ((self._host, self._port), None))
        s_runtime = 1000 * (cost_time)

        return s_runtime

class TempCtx():
    def __init__(self, author: discord.Member, channel: discord.VoiceChannel) -> None:
        self.author: discord.Member = author
        self.channel: discord.VoiceChannel = channel
        self.guild: discord.Guild = channel.guild

def format_to_ms(time_str: str) -> int:
    """
    Converts a time string in one of the formats ('HH:MM:SS', 'MM:SS', 'SS') to milliseconds.
    
    Args:
        time_str (str): The input time string.
    
    Returns:
        int: Time in milliseconds, or 0 if parsing fails.
    """
    formats = ['%H:%M:%S', '%M:%S', '%S']
    
    for fmt in formats:
        try:
            parsed = time.strptime(time_str, fmt)
            total_seconds = parsed.tm_hour * 3600 + parsed.tm_min * 60 + parsed.tm_sec
            return total_seconds * 1000
        except ValueError:
            continue
    
    return 0

def format_ms(milliseconds: Union[float, int]) -> str:
    """
    Converts milliseconds to a formatted time string.
    
    Args:
        milliseconds (int): The time in milliseconds.
        
    Returns:
        str: The formatted time string.
        
    Examples:
        65000 -> "01:05"
        3723000 -> "1:02:03"
        90061000 -> "1 days, 01:01:01"
    """
    if isinstance(milliseconds, float):
        milliseconds = int(milliseconds)
        
    seconds = (milliseconds // 1000) % 60
    minutes = (milliseconds // 60_000) % 60
    hours = (milliseconds // 3_600_000) % 24
    days = milliseconds // 86_400_000

    if days:
        return f"{days} days, {hours:02}:{minutes:02}:{seconds:02}"
    if hours:
        return f"{hours}:{minutes:02}:{seconds:02}"
    return f"{minutes:02}:{seconds:02}"

def format_bytes(bytes: int, unit: bool = False):
    """
    Converts bytes to a human-readable string in MB or GB.
    Args:
        bytes (int): The number of bytes.
        unit (bool): If True, appends the unit (MB or GB) to the result.
        
    Returns:
        str: The formatted string.
    """
    if bytes <= 1_000_000_000:
        return f"{bytes / (1024 ** 2):.1f}" + ("MB" if unit else "")
    
    else:
        return f"{bytes / (1024 ** 3):.1f}" + ("GB" if unit else "")

def truncate_string(text: str, length: int = 40) -> str:
    """
    Truncates a string to a specified maximum length, appending '...' if the string exceeds that length.

    Args:
        text (str): The input string to truncate.
        length (int, optional): The maximum allowed length of the output string, including the ellipsis. Defaults to 40.

    Returns:
        str: The truncated string with '...' appended if it was longer than the specified length.
    """
    return text[:length - 3] + "..." if len(text) > length else text

async def dispatch_message(
    ctx: Union[commands.Context, discord.Interaction, TempCtx],
    content: Union[str, discord.Embed] = None,
    *params,
    view: Optional[discord.ui.View] = None,
    file: Optional[discord.File] = None,
    delete_after: Optional[float] = MISSING,
    ephemeral: bool = False,
    requires_fetch: bool = False
) -> Optional[discord.Message]:
    """
    Dispatches a message or embed to the appropriate Discord context.

    Args:
        ctx: The command or interaction context.
        content: The message content or embed to send.
        *params: Parameters to format the content string.
        view: Optional UI view.
        file: Optional file to attach.
        delete_after: Optional auto-delete duration.
        ephemeral: Whether the message should be ephemeral.
        requires_fetch: Whether to fetch the message after sending.

    Returns:
        The sent message object, or None.
    """
    if content is None:
        content = "No content provided."

    # Determine the text to send
    embed = content if isinstance(content, discord.Embed) else None
    text = None if embed else content.format(*params)
        
    # Determine the sending function
    send_func = (
        ctx.send if isinstance(ctx, commands.Context) else
        ctx.channel.send if isinstance(ctx, TempCtx) else
        ctx.followup.send if ctx.response.is_done() else
        ctx.response.send_message
    )

    # Check settings for delete_after duration
    settings = await MongoDBHandler.get_settings(ctx.guild.id)
    send_kwargs = {
        "content": text,
        "embed": embed,
        "allowed_mentions": discord.AllowedMentions().none(),
        "silent": settings.get("silent_msg", False),
    }
    
    if file:
        send_kwargs["file"] = file
    
    if view:
        send_kwargs["view"] = view
        
    if "delete_after" in send_func.__code__.co_varnames:
        if delete_after is MISSING and settings and ctx.channel.id == settings.get("music_request_channel", {}).get("text_channel_id"):
            delete_after = 10
        send_kwargs["delete_after"] = delete_after
    
    if "ephemeral" in send_func.__code__.co_varnames:
        send_kwargs["ephemeral"] = ephemeral

    # Send the message or embed
    message = await send_func(**send_kwargs)

    if isinstance(message, discord.InteractionCallbackResponse):
        message = message.resource
    
    if requires_fetch and isinstance(message, (discord.WebhookMessage, discord.InteractionMessage)):
        message = await message.fetch()

    return message

async def send_localized_message(
    ctx: Union[commands.Context, discord.Interaction, TempCtx],
    content_key: str,
    *params,
    language: str = None,
    **kwargs
) -> Optional[discord.Message]:
    """
    Sends a localized message using a language key and optional formatting parameters.

    Args:
        ctx (Union[commands.Context, discord.Interaction]): The Discord context or interaction.
        content_key (str): The key used to retrieve the localized message.
        language (str, optional): Language code to override guild default. Must exist in LangHandler.get_all_languages().
        *params: Optional parameters to format the localized message.
        **kwargs: Additional keyword arguments passed to dispatch_message (e.g., view, file, delete_after, ephemeral, requires_fetch).

    Returns:
        Optional[discord.Message]: The sent message object, or None if sending failed.
    """
    if language and language in LangHandler.get_all_languages():
        localized_text = LangHandler._get_lang(language, content_key)
    else:
        localized_text = await LangHandler.get_lang(ctx.guild.id, content_key)
    
    if localized_text:
        try:
            formatted_text = localized_text.format(*params)
        except (IndexError, KeyError):
            formatted_text = localized_text
    else:
        formatted_text = "Translation not found."

    return await dispatch_message(ctx, content=formatted_text, **kwargs)