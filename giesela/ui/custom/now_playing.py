import asyncio

from discord import Embed, Message, TextChannel, User

from giesela import GieselaEntry, GieselaPlayer, Playlist, RadioSongEntry, TimestampEntry, YoutubeEntry
from giesela.ui import create_player_bar
from giesela.utils import (ordinal, to_timestamp)
from .. import InteractableEmbed, IntervalUpdatingMessage, emoji_handler


def create_progress_bar(progress: float, duration: float) -> str:
    progress_ratio = progress / duration
    progress_bar = create_player_bar(progress_ratio, 18)
    return progress_bar


class NowPlayingEmbed(IntervalUpdatingMessage, InteractableEmbed):
    """
    Keyword Args:
        seek_amount: Amount of seconds to forward/rewind
    """
    seek_amount: float
    player: GieselaPlayer

    def __init__(self, channel: TextChannel, player: GieselaPlayer, **kwargs):
        self.seek_amount = kwargs.pop("seek_amount", 30)
        super().__init__(channel, **kwargs)
        self.player = player

    async def get_embed(self) -> Embed:
        entry = self.player.current_entry

        if not entry:
            return Embed(description="Nothing playing")

        fields = []
        author = {}
        footer = {}

        playing_state = "►" if self.player.is_paused else "❚❚"
        progress_bar = None
        song_progress = self.player.progress
        song_duration = entry.duration

        title = entry.title
        colour = 0xa9b244
        cover = None

        entry_author: User = entry.meta.get("author")
        playlist: Playlist = entry.meta.get("playlist")

        if isinstance(entry, GieselaEntry):
            author = dict(name=entry.artist, icon_url=entry.artist_image)
            cover = entry.cover
            title = entry.song_title
        elif isinstance(entry, RadioSongEntry):
            cover = entry.song_data.cover
            author = dict(name=entry.song_data.artist or Embed.Empty, icon_url=entry.song_data.artist_image or Embed.Empty)
            if entry.song_data.song_title:
                title = entry.song_data.song_title
        else:
            if isinstance(entry, YoutubeEntry):
                cover = entry.thumbnail
            if entry_author:
                author = dict(name=entry_author.display_name, icon_url=entry_author.avatar_url)

        if isinstance(entry, RadioSongEntry):
            colour = 0xa23dd1
            footer = dict(text=f"🔴 Live from {entry.station.name}", icon_url=entry.station.logo or Embed.Empty)
            song_progress = entry.song_progress
            song_duration = entry.song_data.duration
        elif isinstance(entry, GieselaEntry):
            colour = 0xF9FF6E
            fields.append(dict(name="Album", value=entry.album))
        elif isinstance(entry, TimestampEntry):
            colour = 0x00FFFF
            sub_entry = entry.get_sub_entry(self.player)
            title = sub_entry["name"]
            sub_index = sub_entry["index"]

            footer = dict(text=f"{sub_index + 1}{ordinal(sub_index + 1)} sub-entry of \"{entry.title}\" "
                               f"[{to_timestamp(song_progress)}/{to_timestamp(song_duration)}]")

            song_progress = sub_entry["progress"]
            song_duration = sub_entry["duration"]

            cover = entry.thumbnail
        elif isinstance(entry, YoutubeEntry):
            colour = 0xa9b244

        if song_progress is not None and song_duration is not None:
            progress_bar = progress_bar or create_progress_bar(song_progress, song_duration)
            desc = f"{playing_state} {progress_bar} `[{to_timestamp(song_progress)}/{to_timestamp(song_duration)}]`"
        else:
            desc = f"{playing_state}"

        if playlist:
            fields.append(dict(name="Playlist", value=playlist.name))
            if not cover:
                cover = playlist.cover

        em = Embed(
            title=title,
            description=desc,
            url=entry.url,
            colour=colour
        )

        for field in fields:
            em.add_field(**field)

        if footer:
            em.set_footer(**footer)
        if cover:
            em.set_thumbnail(url=cover)
        if author:
            em.set_author(**author)

        return em

    async def on_create_message(self, msg: Message):
        await self.add_reactions(msg)

    async def start(self):
        await super().start()

    @emoji_handler("⏮", pos=1)
    async def prev_entry(self, *_):
        self.player.queue.replay(0, revert=True)

    @emoji_handler("⏪", pos=2)
    async def fast_rewind(self, *_):
        await self.player.seek(self.player.progress - self.seek_amount)

    @emoji_handler("⏯", pos=3)
    async def play_pause(self, *_):
        if self.player.is_playing:
            await self.player.pause()
        else:
            await self.player.resume()

    @emoji_handler("⏩", pos=4)
    async def fast_forward(self, *_):
        await self.player.seek(self.player.progress + self.seek_amount)

    @emoji_handler("⏭", pos=5)
    async def next_entry(self, *_):
        await self.player.skip()

    async def delayed_update(self):
        await asyncio.sleep(.5)
        await self.trigger_update()

    async def on_any_emoji(self, *_):
        asyncio.ensure_future(self.delayed_update())
