import json
import os
import re
import time

import configparser
from musicbot.entry import Entry
from musicbot.exceptions import BrokenEntryError, OutdatedEntryError
from musicbot.utils import clean_songname, similarity
from musicbot.web_author import WebAuthor


class Playlists:

    def __init__(self, playlists_file):
        self.playlists_file = playlists_file
        self.update_playlists()
        self.playlist_save_location = "data/playlists/"

    def update_playlists(self):
        with open(self.playlists_file, "r+") as f:
            self.playlists = json.load(f)

    def save_playlists(self):
        with open(self.playlists_file, "w+") as f:
            json.dump(self.playlists, f, indent=4)

    def get_all_web_playlists(self, queue):
        return [self.get_web_playlist(name, queue) for name, data in self.playlists.items() if data.get("entries") and data.get("cover")]

    def get_web_playlist(self, playlist_name, queue):
        data = self.get_playlist(playlist_name, queue)

        playlist_info = {
            "name":         data["name"],
            "id":           data["id"],
            "cover":        data["cover_url"],
            "description":  data["description"],
            "author":       data["author"].to_dict(),
            "replay_count": data["replay_count"],
            "entries":      [entry.to_web_dict(skip_calc=True) for entry in data["entries"]]
        }

        return playlist_info

    def get_playlist(self, playlistname, playlist, load_entries=True, channel=None):
        playlistname = playlistname.lower().strip().replace(" ", "_")
        if playlistname not in self.playlists:
            return None

        plsection = self.playlists[playlistname]

        playlist_author = plsection["author"]

        if isinstance(playlist_author, dict):
            playlist_author = WebAuthor.from_dict(playlist_author)
        else:
            playlist_author = WebAuthor.from_id(playlist_author)

        playlist_information = {
            "id":           playlistname,
            "name":         playlistname.replace("_", " ").title(),
            "location":     plsection["location"],
            "author":       playlist_author,
            "replay_count": int(plsection["replays"]),
            "description":  None if plsection.get("description") == "None" else plsection.get("description"),
            "cover_url":    None if plsection.get("cover_url") == "None" else plsection.get("cover_url")
        }

        entries = []
        # this is gonna be a list of serialised entries populated with the broken or outdated
        # entries
        broken_entries = []
        if load_entries and not os.stat(playlist_information["location"]).st_size == 0:
            with open(playlist_information["location"], "r") as f:
                serialized_json = json.loads(f.read())

            for ind, ser_entry in enumerate(serialized_json):
                try:
                    entry = Entry.from_dict(playlist, ser_entry)
                    entry.meta["channel"] = channel
                    if "playlist" not in entry.meta:
                        entry.meta["playlist"] = {
                            "cover": playlist_information["cover_url"],
                            "name": playlistname,
                            "index": ind,
                            "timestamp": round(time.time())
                        }
                except (BrokenEntryError, OutdatedEntryError, TypeError, KeyError):
                    entry = None

                if not entry:
                    broken_entries.append(ser_entry)
                else:
                    entries.append(entry)

        playlist_information["entries"] = sorted(entries, key=lambda entry: entry.title)
        playlist_information["broken_entries"] = broken_entries

        return playlist_information

    def set_playlist(self, entries, name, author, description=None, cover_url=None, replays=0):
        name = name.lower().strip().replace(" ", "_")

        serialized_entries = []
        for index, entry in enumerate(entries):
            entry.start_seconds = 0

            added_timestamp = entry.meta.get("playlist", {}).get("timestamp", round(time.time()))

            entry.meta["playlist"] = {
                "cover": cover_url,
                "name": name,
                "index": index,
                "timestamp": added_timestamp
            }

            serialized_entries.append(entry.to_dict())

        json.dump(serialized_entries, open(self.playlist_save_location + str(name) + ".gpl", "w+"), indent=4)

        playlist_data = self.playlists.get(name, {})

        if not isinstance(author, WebAuthor):
            author = WebAuthor.from_id(author)

        playlist_data.update({
            "location": "{}{}.gpl".format(self.playlist_save_location, name),
            "author": author.to_dict(),
            "replays": replays,
            "description": description,
            "cover_url": cover_url
        })

        self.playlists[name] = playlist_data

        self.save_playlists()
        return True

    def bump_replay_count(self, playlist_name):
        playlist_name = playlist_name.lower().strip().replace(" ", "_")

        if playlist_name in self.playlists:
            prev_count = self.playlists[playlist_name].get("replays", 0)

            self.playlists[playlist_name].update(replays=prev_count + 1)
            self.save_playlists()
            return True

        return False

    def in_playlist(self, queue, playlist, query, certainty_threshold=.6):
        results = self.search_entries_in_playlist(
            queue, playlist, query
        )
        result = results[0]
        if result[0] > certainty_threshold:
            return result[1]
        else:
            return False

    def search_entries_in_playlist(self, queue, playlist, query, certainty_threshold=None):
        if isinstance(playlist, str):
            playlist = self.get_playlist(playlist, queue)

        if isinstance(query, str):
            query_title = query_url = query
        else:
            query_title = query.title
            query_url = query.url

        entries = playlist["entries"]

        def get_similarity(entry):
            s1 = similarity(query_title, entry.title)
            s2 = 1 if query_url == entry.url else 0

            words_in_query = [re.sub(r"\W", "", w)
                              for w in query_title.lower().split()]
            words_in_query = [w for w in words_in_query if w]

            words_in_title = [re.sub(r"\W", "", w)
                              for w in entry.title.lower().split()]
            words_in_title = [w for w in words_in_title if w]

            s3 = sum(len(w) for w in words_in_query if w in entry.title.lower(
            )) / len(re.sub(r"\W", "", query_title))
            s4 = sum(len(w) for w in words_in_title if w in query_title.lower(
            )) / len(re.sub(r"\W", "", entry.title))
            s5 = (s3 + s4) / 2

            return max(s1, s2, s5)

        matched_entries = [(get_similarity(entry), entry) for entry in entries]
        if certainty_threshold:
            matched_entries = [
                el for el in matched_entries if el[0] > certainty_threshold]
        ranked_entries = sorted(
            matched_entries,
            key=lambda el: el[0],
            reverse=True
        )

        return ranked_entries

    def remove_playlist(self, name):
        name = name.lower().strip().replace(" ", "_")

        if name in self.playlists:
            os.remove(self.playlists[name]["location"])
            self.playlists.pop(name)
            self.save_playlists()

    def edit_playlist(self, name, playlist, all_entries=None, remove_entries=None, remove_entries_indexes=None, new_entries=None, new_name=None, new_description=None, new_cover=None, edit_entries=None):
        name = name.lower().strip().replace(" ", "_")
        old_playlist = self.get_playlist(name, playlist)

        if all_entries:
            next_entries = all_entries
        else:
            old_entries = old_playlist[
                "entries"] if old_playlist is not None else []

            if remove_entries_indexes is not None:
                old_entries = [old_entries[x] for x in range(
                    len(old_entries)) if x not in remove_entries_indexes]

            if remove_entries is not None:
                urls = [x.url for x in remove_entries]
                for entry in old_entries:
                    if entry.url in urls:
                        old_entries.remove(entry)

            if new_entries is not None:
                old_entries.extend(new_entries)
            next_entries = old_entries

            if edit_entries:
                for old, new in edit_entries:
                    if all((new, old)) and old != new:
                        index = next(ind for ind, entry in enumerate(next_entries) if entry.url == old.url)
                        next_entries.pop(index)
                        next_entries.insert(index, new)

        next_name = new_name if new_name is not None else name
        next_author = old_playlist["author"]
        next_description = new_description or old_playlist["description"]
        next_cover = new_cover or old_playlist["cover_url"]

        if len(next_entries) < 1:
            self.remove_playlist(name)
            return

        if next_name != name:
            self.remove_playlist(name)

        self.set_playlist(next_entries, next_name, next_author, next_description,
                          next_cover, replays=old_playlist["replay_count"])

    async def mark_entry_broken(self, queue, playlist_name, entry):
        playlist = self.get_playlist(playlist_name, queue)

        entries = playlist["entries"]

        index = next(ind for ind, e in enumerate(entries) if e.url == entry.url)

        serialized_entries = []
        for index, entry in enumerate(entries):
            entry.start_seconds = 0

            entry.meta["playlist"] = {
                "cover": playlist["cover_url"],
                "name": playlist_name,
                "index": index
            }

            serialized_entries.append(entry.to_dict())

        serialized_entries[index]["broken"] = True

        json.dump(serialized_entries, open(self.playlist_save_location + str(playlist_name) + ".gpl", "w"), indent=4)
        print("marked {} from {} as broken".format(entry.title, playlist_name))
