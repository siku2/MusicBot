import abc
import asyncio
import contextlib
import logging
import textwrap
from typing import List, TYPE_CHECKING, Tuple

from discord import Colour, Embed, Guild, TextChannel, User
from discord.ext import commands
from discord.ext.commands import Context

from giesela import BaseEntry, EditPlaylistProxy, Giesela, Optional, Playlist, PlaylistEntry, utils
from .entry_editor import EntryEditor
from ..help import AutoHelpEmbed
from ..interactive import MessageableEmbed, VerticalTextViewer, emoji_handler

if TYPE_CHECKING:
    from giesela.cogs.player import Player

log = logging.getLogger(__name__)


def create_basic_embed(playlist: Playlist) -> Embed:
    embed = Embed(title=playlist.name)
    if playlist.description:
        embed.add_field(name="Description", value=playlist.description, inline=False)
    if playlist.cover:
        embed.set_thumbnail(url=playlist.cover)
    embed.set_author(name=playlist.author.display_name, icon_url=playlist.author.avatar_url)
    embed.set_footer(text="{progress_bar}")
    return embed


class _PlaylistEmbed(VerticalTextViewer, metaclass=abc.ABCMeta):
    """
    Keyword Args:
        bot: `Giesela`.
        playlist: `Playlist`.
    """
    PASS_BOT: bool = False

    bot: Giesela
    player_cog: "Player"
    playlist: Playlist

    def __init__(self, channel: TextChannel, user: User = None, **kwargs):
        self.bot = kwargs.pop("bot")
        self.playlist = kwargs.pop("playlist")
        embed_frame = kwargs.pop("embed_frame", False) or create_basic_embed(self.playlist)

        if self.PASS_BOT:
            kwargs["bot"] = self.bot

        super().__init__(channel, user, embed_frame=embed_frame, **kwargs)

        self.player_cog = self.bot.cogs["Player"]

    @property
    def entries(self) -> List[PlaylistEntry]:
        return self.playlist.entries

    @property
    def index_padding(self) -> int:
        return len(str(len(self.entries)))

    @property
    def total_lines(self) -> int:
        return len(self.entries)

    async def get_line(self, line: int) -> str:
        entry = self.entries[line]
        index = str(line + 1).rjust(self.index_padding, "0")
        title = textwrap.shorten(entry.title, 50)

        return f"`{index}.` {title}"

    async def play(self, guild: Guild, user: User):
        player = await self.player_cog.get_player(guild, member=user)
        await self.playlist.play(player.queue, author=user)


class PlaylistViewer(_PlaylistEmbed):
    def __init__(self, *args, **kwargs):
        playlist = kwargs["playlist"]
        embed = create_basic_embed(playlist)
        embed.add_field(name="Length", value=f"{len(playlist)} entries")
        embed.add_field(name="Duration", value=utils.format_time(playlist.duration))
        super().__init__(*args, embed_frame=embed, **kwargs)

    @emoji_handler("🎵", pos=999)
    async def play_playlist(self, *_):
        await self.play(self.channel.guild, self.user)
        await self.remove_handler(self.play_playlist)


class PlaylistBuilder(AutoHelpEmbed, _PlaylistEmbed, MessageableEmbed):
    PASS_BOT = True

    playlist_editor: EditPlaylistProxy

    _highlighted_line: Optional[int]
    _processing: Optional[Tuple[str, str]]

    def __init__(self, channel: TextChannel, user: User = None, **kwargs):
        super().__init__(channel, user, **kwargs)
        self.downloader = self.player_cog.downloader
        self.playlist_editor = self.playlist.edit()

        self._highlighted_line = None
        self._processing = None

    @property
    def help_title(self) -> str:
        return "Playlist Builder Help"

    @property
    def help_description(self) -> str:
        return "Idk what to write here so I'm just using this for now, okay? okay."

    @property
    def entries(self) -> List[PlaylistEntry]:
        return self.playlist_editor.entries

    @property
    def embed_frame(self) -> Embed:
        embed = super().embed_frame
        changelog = self.playlist_editor.prepare_changelog(width=50, limit=3)
        if changelog:
            embed.add_field(name="Recent Changes", value=changelog, inline=False)
        if self._processing:
            embed.colour = Colour.blue()
            value, name = self._processing
            embed.add_field(name=name, value=value)
        if self.error:
            embed.colour = Colour.red()
            embed.add_field(name="Error", value=f"**{self.error}**")
            self.error = None

        return embed

    async def get_line(self, line: int) -> str:
        entry = self.entries[line]
        index = str(line + 1).rjust(self.index_padding, "0")
        title = textwrap.shorten(entry.title, 50)
        if self._highlighted_line == line:
            title = f"**{title}**"

        change = self.playlist_editor.get_change(entry)
        symbol = f"{change.symbol} " if change else ""

        return f"{symbol}`{index}.` {title}"

    async def on_command_error(self, ctx: Context, exception: Exception):
        await super().on_command_error(ctx, exception)
        await self.show_window()

    # I hope you're using python 3.7 because I have absolutely no intention of rewriting this :P
    @contextlib.asynccontextmanager
    async def processing(self, value: str, title: str = "Processing"):
        self._processing = (value, title)
        asyncio.ensure_future(self.show_window())

        try:
            async with self.channel.typing():
                yield None
        finally:
            self._processing = None

    async def update_processing(self, *, value: str = None, title: str = None):
        if not self._processing:
            raise ValueError("Not processing anything")

        new_value, new_title = self._processing
        new_value = value or new_value
        new_title = title or new_title
        self._processing = (new_value, new_title)

        await self.show_window()

    async def _add_playlist(self, entries: List[str]) -> List[BaseEntry]:
        tasks = self.downloader.get_entries_from_urls(entries)
        _total_tasks = len(tasks)
        _show_task = None
        entries = []

        async with self.processing("Preparing...", title="Processing Playlist"):
            for i, task in enumerate(tasks, 1):
                try:
                    entry = await task
                except asyncio.CancelledError:
                    break
                except Exception:
                    log.exception("Something went wrong while loading playlist")
                    continue

                entries.append(entry)

                if not _show_task or _show_task.done():
                    progress = str(round(100 * i / _total_tasks))
                    _show_task = asyncio.ensure_future(self.update_processing(value=f"{progress}% done"))

            if _show_task:
                await _show_task

        return entries

    @emoji_handler("💾", pos=999)
    async def save_changes(self, *_) -> str:
        """Close and save"""
        self.stop_listener()
        self.playlist_editor.apply()
        return self.playlist_editor.prepare_changelog()

    @emoji_handler("❎", pos=1000)
    async def abort(self, *_) -> None:
        """Close without saving"""
        self.stop_listener()
        return None

    @commands.command("edit")
    async def edit_entry(self, ctx: Context, index: int):
        """Edit an entry"""
        index -= 1
        if not 0 <= index < len(self.entries):
            raise commands.CommandError(f"Index out of bounds  ({index + 1} not in 1 - {len(self.entries)})")
        entry = self.entries[index]
        editor = EntryEditor(ctx.channel, ctx.author, bot=self.bot, entry=entry.get_entry(author=ctx.author))
        new_entry = await editor.display()
        if new_entry:
            self.playlist_editor.edit_entry(entry, new_entry.to_dict())
            await self.show_line(index)

    @commands.command("add")
    async def add_entry(self, ctx: Context, *query: str):
        """Add an entry"""
        query = " ".join(query)

        async with self.processing(f"\"{query}\"", "Searching..."):
            entry = await self.downloader.get_entry_from_query(query)

        if isinstance(entry, list):
            entries = await self._add_playlist(entry)
            for entry in entries:
                self.playlist_editor.add_entry(entry)
            await self.show_window()
        else:
            try:
                entry = self.playlist_editor.add_entry(entry)
            except KeyError:
                raise commands.CommandError(f"\"{entry.title}\" is already in the playlist")
            await self.show_line(self.playlist_editor.index_of(entry))

    @commands.command("remove", aliases=["rm"])
    async def remove_entry(self, _, *indices: int):
        """Remove entries"""
        if not indices:
            raise commands.CommandError("Please provide at least one index to remove")

        for index in sorted(indices, reverse=True):
            self.playlist_editor.remove_entry(index - 1)

        if len(indices) == 1:
            await self.show_line(indices[0])
        else:
            await self.show_window()

    @commands.command("undo", aliases=["revert"])
    async def undo_action(self, _):
        """Undo something"""
        change = self.playlist_editor.undo()
        if not change:
            raise commands.CommandError("Nothing to undo")
        await self.show_window()

    @commands.command("redo")
    async def redo_action(self, _):
        """Redo something"""
        change = self.playlist_editor.redo()
        if not change:
            raise commands.CommandError("Nothing to redo")
        await self.show_window()

    @commands.command("show", aliases=["goto"])
    async def show_target(self, _, *target: str):
        """Show a specific line or entry."""
        target = " ".join(target)
        if target.isnumeric():
            line = int(target) - 1
        else:
            entry = self.playlist_editor.search_entry(target)
            if not entry:
                raise commands.CommandError(f"Couldn't find entry {target}")
            line = self.playlist_editor.index_of(entry)

        if line >= len(self.entries):
            raise commands.CommandError("Line number too big!")

        self._highlighted_line = line
        await self.show_line(line)