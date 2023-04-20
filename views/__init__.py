from discord.ext import commands

class ButtonOnCooldown(commands.CommandError):
    def __init__(self, retry_after: float) -> None:
        self.retry_after = retry_after
        
from .controller import InteractiveController
from .search import SearchView
from .help import HelpView
from .list import ListView
from .lyrics import LyricsView
from .chapter import ChapterView
from .playlist import PlaylistView, CreateView
from .inbox import InboxView
from .link import LinkView
from .debug import DebugModal
from .embedBuilder import EmbedBuilderView
