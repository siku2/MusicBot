import asyncio
import datetime
import logging
import os
import random
import time
import urllib
import urllib.error
from collections import deque
from itertools import islice
from typing import TYPE_CHECKING

from youtube_dl.utils import DownloadError, ExtractorError, UnsupportedError

from .entry import (DiscogsEntry, RadioSongEntry, RadioStationEntry, SpotifyEntry, StreamEntry, TimestampEntry, VGMEntry, YoutubeEntry)
from .exceptions import ExtractionError, WrongEntryTypeError
from .lib.api.VGMdb import get_entry as get_vgm_track
from .lib.api.discogs import get_entry as get_discogs_track
from .lib.api.spotify import get_spotify_track
from .lib.event_emitter import EventEmitter
from .utils import clean_songname, get_header, get_video_sub_queue
from .webiesela import WebieselaServer

if TYPE_CHECKING:
    from giesela import Playlist

log = logging.getLogger(__name__)


class Queue(EventEmitter):

    def __init__(self, bot, player, downloader):
        super().__init__()
        self.bot = bot
        self.loop = bot.loop
        self.player = player
        self.downloader = downloader
        self.entries = deque()
        self.history = []

    def __iter__(self):
        return iter(self.entries)

    def get_web_dict(self):
        data = {
            "entries": [entry.to_web_dict(True) for entry in self.entries.copy()],
            "history": [entry.to_web_dict(True) for entry in self.history.copy()]
        }
        return data

    def shuffle(self):
        random.shuffle(self.entries)
        WebieselaServer.send_player_information(self.player.channel.guild.id)

    def clear(self):
        self.entries.clear()
        WebieselaServer.send_player_information(self.player.channel.guild.id)

    def move(self, from_index, to_index):
        if not (0 <= from_index < len(self.entries) and 0 <= to_index < len(self.entries)):
            return False

        self.entries.rotate(-from_index)
        move_entry = self.entries.popleft()
        self.entries.rotate(from_index - to_index)

        self.entries.appendleft(move_entry)
        self.entries.rotate(to_index)

        if self.peek() is move_entry:
            move_entry.get_ready_future()

        WebieselaServer.send_player_information(self.player.channel.guild.id)

        return move_entry

    def replay(self, index: int = None, revert: bool = False) -> bool:
        if index is None:
            entry = self.player.current_entry
            if entry:
                entry = entry.copy()
            else:
                return False
        else:
            if not 0 <= index < len(self.history):
                return False
            entry = self.history[index].copy()

        self._add_entry(entry, placement=0)

        if revert and self.player.current_entry:
            self.player.skip()

        return True

    def push_history(self, entry):
        entry = entry.copy()

        entry.meta["finish_time"] = time.time()
        q = self.bot.config.history_limit - 1
        self.history = [entry, *self.history[:q]]

        WebieselaServer.send_player_information(self.player.channel.guild.id)

    async def load_playlist(self, playlist: "Playlist", **meta):
        for playlist_entry in playlist:
            entry = playlist_entry.get_entry(self, **meta)
            self._add_entry(entry, more_to_come=True)
        WebieselaServer.send_player_information(self.player.channel.guild.id)
        self.emit("entry-added", queue=self)

    async def add_stream_entry(self, stream_url, **meta):
        info = {"title": stream_url, "extractor": None}
        try:
            info = await self.downloader.extract_info(self.loop, stream_url, download=False)

        except DownloadError as e:
            if e.exc_info[0] == UnsupportedError:
                print("[STREAM] Assuming content is a direct stream")

            elif e.exc_info[0] == urllib.error.URLError:
                if os.path.exists(os.path.abspath(stream_url)):
                    raise ExtractionError("This is not a stream, this is a file path.")

                else:  # it might be a file path that just doesn't exist
                    raise ExtractionError("Invalid input: {0.exc_info[0]}: {0.exc_info[1].reason}".format(e))

            else:
                raise ExtractionError("Unknown error: {}".format(e))

        except Exception as e:
            print("Could not extract information from {} ({}), falling back to direct".format(stream_url, e))

        dest_url = stream_url
        if info.get("extractor"):
            dest_url = info.get("url")

        if info.get("extractor", None) == "twitch:stream":
            title = info.get("description")
        else:
            title = info.get("title", "Untitled")

        entry = StreamEntry(
            self,
            stream_url,
            title,
            destination=dest_url,
            **meta
        )

        self._add_entry(entry)

        return entry, len(self.entries)

    async def add_radio_entry(self, station_info, now=False, **meta):
        if station_info.has_current_song_info:
            entry = RadioSongEntry(self, station_info, **meta)
        else:
            entry = RadioStationEntry(self, station_info, **meta)

        if now:
            await entry._download()

            if self.player.current_entry:
                self.player.handle_manually = True

            self.player.play_entry(entry)
            WebieselaServer.send_player_information(self.player.channel.guild.id)
        else:
            self._add_entry(entry)

    async def add_entry(self, song_url, **meta):
        """
            Validates and adds a song_url to be played. This does not start the download of the song.

            Returns the entry & the position it is in the queue.

            :param song_url: The song url to add to the queue.
            :param meta: Any additional metadata to add to the queue entry.
        """

        entry = await self.get_entry(song_url, **meta)
        self._add_entry(entry)
        return entry, len(self.entries)

    async def add_entry_next(self, song_url, **meta):
        """
            Validates and adds a song_url to be played. This does not start the download of the song.

            Returns the entry & the position it is in the queue.

            :param song_url: The song url to add to the queue.
            :param meta: Any additional metadata to add to the queue entry.
        """

        entry = await self.get_entry(song_url, **meta)
        self._add_entry(entry, 0)
        return entry, len(self.entries)

    async def get_entry_from_query(self, query, **meta):

        try:
            info = await self.downloader.extract_info(
                self.loop, query, download=False, process=False)
        except Exception as e:
            raise ExtractionError(
                "Could not extract information from {}\n\n{}".format(query, e))

        if not info:
            raise ExtractionError("Couldn't extract info")

        if info.get("url", "").startswith("ytsearch"):
            info = await self.downloader.extract_info(
                self.loop,
                query,
                download=False,
                process=True,
                retry_on_error=True
            )

            if not info:
                raise ExtractorError("Couldn't extract info")

            if not info.get("entries", []):
                return None

            query = info["entries"][0]["webpage_url"]
            info = await self.downloader.extract_info(self.loop, query, download=False, process=False)

        if "entries" in info:
            return [entry["url"] for entry in info["entries"]]
        else:
            return await self.get_entry(info, **meta)

    async def get_entry_gen(self, url, **meta):
        info = await self.downloader.extract_info(self.loop, url, download=False, process=False)

        if "entries" in info:
            return self.get_entries_from_urls_gen(*[entry["url"] for entry in info["entries"]])
        else:
            async def _tuple_gen_creator(collection):
                for i, el in enumerate(collection):
                    yield i, el

            return _tuple_gen_creator([await self.get_entry(info, **meta)])

    async def get_entries_from_urls_gen(self, *urls, **meta):
        for ind, url in enumerate(urls):
            try:
                entry = await self.get_entry(url, **meta)
            except (ExtractionError, WrongEntryTypeError) as e:
                print("Error while dealing with url \"{}\":\n{}".format(url, e))
                yield ind, None
                continue

            yield ind, entry

    async def get_ytdl_data(self, song_url):
        try:
            info = await self.downloader.extract_info(self.loop, song_url, download=False)
        except Exception as e:
            raise ExtractionError(
                "Could not extract information from {}\n\n{}".format(song_url, e))

        if not info:
            raise ExtractionError(
                "Could not extract information from %s" % song_url)

        if info.get("_type", None) == "playlist":
            raise WrongEntryTypeError("This is a playlist.", True, info.get(
                "webpage_url", None) or info.get("url", None))

        if info["extractor"] in ["generic", "Dropbox"]:
            try:
                content_type = await get_header(self.bot.aiosession, info["url"], "CONTENT-TYPE")
                print("Got content type", content_type)

            except Exception as e:
                print("[Warning] Failed to get content type for url %s (%s)" % (
                    song_url, e))
                content_type = None

            if content_type:
                if content_type.startswith(("application/", "image/")):
                    if "/ogg" not in content_type:  # How does a server say `application/ogg` what the actual fuck
                        raise ExtractionError(
                            "Invalid content type \"%s\" for url %s" % (content_type, song_url))

                elif not content_type.startswith(("audio/", "video/")):
                    print("[Warning] Questionable content type \"%s\" for url %s" % (
                        content_type, song_url))

        return info

    async def get_entry(self, song_url, **meta):
        if isinstance(song_url, dict):
            info = song_url
        else:
            info = await self.get_ytdl_data(song_url)

        video_id = info.get("id")
        video_title = info.get("title")
        video_description = info.get("description")
        video_thumbnail = info.get("thumbnail")
        video_url = info.get("webpage_url")
        video_duration = info.get("duration", 0)

        clean_title = clean_songname(video_title) or video_title

        meta["expected_filename"] = self.downloader.ytdl.prepare_filename(info)

        base_arguments = (
            self,
            video_id,
            video_url,
            video_title,
            video_duration,
            video_thumbnail,
            video_description
        )

        spotify_searcher = asyncio.ensure_future(get_spotify_track(self.loop, clean_title))
        vgm_searcher = asyncio.ensure_future(get_vgm_track(self.loop, clean_title))
        discogs_searcher = asyncio.ensure_future(get_discogs_track(self.loop, clean_title))

        spotify_track = None
        vgm_track = None
        discogs_track = None

        pending = (spotify_searcher, vgm_searcher, discogs_searcher)

        while pending:
            done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED, timeout=3)
            done = next(iter(done), None)
            if not done:
                break

            result = done.result()
            if not result:
                continue
            if done is spotify_searcher:
                spotify_track = result
            elif done is vgm_searcher:
                vgm_track = result
            elif done is discogs_searcher:
                discogs_track = result
            else:
                log.error(f"Couldn't identify searcher? Dunno...")
            break

        if vgm_track:
            entry = VGMEntry(
                *base_arguments,
                **vgm_track,
                **meta
            )
        elif spotify_track and spotify_track.certainty > .6:
            entry = SpotifyEntry(
                *base_arguments,
                spotify_track,
                **meta
            )
        elif discogs_track:
            entry = DiscogsEntry(
                *base_arguments,
                **discogs_track,
                **meta
            )
        else:
            sub_queue = get_video_sub_queue(
                video_description, video_id, video_duration)

            if sub_queue:
                entry = TimestampEntry(
                    *base_arguments,
                    sub_queue,
                    **meta
                )
            else:
                entry = YoutubeEntry(
                    *base_arguments,
                    **meta
                )

        return entry

    def add_entries(self, entries, placement=None):
        entry = None
        for entry in entries:
            self._add_entry(entry, placement=placement, more_to_come=True)

        WebieselaServer.send_player_information(self.player.channel.guild.id)
        self.emit("entry-added", queue=self, entry=entry)

    def _add_entry(self, entry, placement=None, more_to_come=False):
        if placement is not None:
            if placement == "random":
                if len(self.entries) > 0:
                    placement = random.randrange(0, len(self.entries))
                else:
                    placement = 0

            self.entries.insert(placement, entry)
        else:
            self.entries.append(entry)

        if self.peek() is entry:
            entry.get_ready_future()

        if not more_to_come:
            WebieselaServer.send_player_information(entry.meta["channel"].guild.id)
            self.emit("entry-added", queue=self, entry=entry)

    def promote_position(self, position):
        if not 0 <= position < len(self.entries):
            return False

        self.entries.rotate(-position)
        entry = self.entries.popleft()

        self.entries.rotate(position)
        self.entries.appendleft(entry)
        self.emit("entry-added", queue=self, entry=entry)

        entry.get_ready_future()

        WebieselaServer.send_player_information(self.player.channel.guild.id)

        return entry

    def promote_last(self):
        entry = self.entries.pop()
        self.entries.appendleft(entry)
        self.emit("entry-added", queue=self, entry=entry)
        entry.get_ready_future()

        WebieselaServer.send_player_information(self.player.channel.guild.id)

        return entry

    def remove_position(self, position):
        if not 0 <= position < len(self.entries):
            return None

        self.entries.rotate(-position)
        entry = self.entries.popleft()

        self.emit("entry-removed", queue=self, entry=entry)
        self.entries.rotate(position)

        WebieselaServer.send_player_information(self.player.channel.guild.id)

        return entry

    async def get_next_entry(self, pre_download_next=True):
        """
            A coroutine which will return the next song or None if no songs left to play.

            Additionally, if pre_download_next is set to True, it will attempt to download the next
            song to be played - so that it's ready by the time we get to it.
        """
        if not self.entries:
            return None

        entry = self.entries.popleft()

        if pre_download_next:
            next_entry = self.peek()
            if next_entry:
                next_entry.get_ready_future()

        try:
            return await entry.get_ready_future()
        except ExtractionError:
            if "playlist" in entry.meta:
                playlist_name = entry.meta["playlist"]["name"]
                asyncio.ensure_future(self.bot.playlists.mark_entry_broken(self, playlist_name, entry))
                print("[PLAYER] {}'s {} is broken!".format(playlist_name, entry.title))
        except Exception:
            log.exception(f"Couldn't ready entry {entry}")

        return await self.get_next_entry(pre_download_next)

    def peek(self):
        """
            Returns the next entry that should be scheduled to be played.
        """
        if self.entries:
            return self.entries[0]

    async def estimate_time_until(self, position, player):
        estimated_time = sum([e.end_seconds for e in islice(self.entries, position - 1)])

        if not player.is_stopped and player.current_entry:
            estimated_time += player.current_entry.duration - player.progress

        return datetime.timedelta(seconds=estimated_time)
