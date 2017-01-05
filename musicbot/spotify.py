import re
from difflib import SequenceMatcher

import spotipy


class SpotifyTrack:

    def __init__(self, artist, song_name, cover_url, certainty=1):
        self.artist = artist
        self.song_name = song_name
        self.cover_url = cover_url
        self.certainty = certainty

    @classmethod
    def from_query(cls, query, strip_query=True):
        for chr in ["()", "[]", "<>"]:
            query = re.sub("\{0[0]}.+\{0[1]}".format(chr), "", query)

        query = re.sub("'", "", query)

        index = query.find("|")
        query = query[:index if index > 3 else len(query)]

        index = query.lower().find("download")
        query = query[:index if index > 3 else len(query)]

        index = query.lower().find("ft")
        query = query[:index if index > 3 else len(query)]
        index = query.lower().find("feat")
        query = query[:index if index > 3 else len(query)]

        index = query.lower().find("lyric")
        query = query[:index if index > 3 else len(query)]

        index = query.lower().find("&") if query.lower().find(
            "&") != -1 else query.lower().find("x")
        dash = query.find("-")
        if dash == -1:
            query = query[index + 1 if index > 0 else 0:]
        else:
            query = query[:index if index > 0 else len(query)] + query[dash:]

        query = query.replace("-", " ", 1)
        index = query.find("-")
        query = query[:index if index > 3 else len(query)]
        query = query.strip()
        query = " ".join(query.split())

        spotify = spotipy.Spotify()
        search_result = spotify.search(query, limit=1, type="track")
        if len(search_result) < 1:
            return cls("", query.upper(), "", 0)
        if len(search_result["tracks"]["items"]) < 1:
            return cls("", query.upper(), "", 0)

        track = search_result["tracks"]["items"][0]
        try:
            album = track["album"]
            cover = album["images"][0]["url"]
        except:
            cover = None

        song_name = track["name"]
        artists = track["artists"][:2]
        artist_text = " & ".join([x["name"] for x in artists])

        song_name_edited = re.sub(
            "\{0[0]}.+\{0[1]}".format("()"), "", song_name)

        return cls(artist_text.upper(), song_name.upper(), cover, max(similar(query, "{0} {1}".format(artists[0]["name"], song_name_edited)), similar(query, "{1} {0}".format(artists[0]["name"], song_name_edited))))


def similar(a, b):
    return SequenceMatcher(None, a, b).ratio()
