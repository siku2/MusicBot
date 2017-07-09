import asyncio
import datetime
import decimal
import json
import random
import re
import time
import unicodedata
from datetime import timedelta
from difflib import SequenceMatcher
from hashlib import md5
from io import BytesIO
from threading import Thread

import aiohttp
import requests
from bs4 import BeautifulSoup
from PIL import Image, ImageStat

from .constants import DISCORD_MSG_CHAR_LIMIT


class run_function_every:

    def __init__(self, function, timeout):
        self.thread = Thread(target=self._sender, args=(function, timeout))
        self.stop = False

    def _sender(self, function, timeout):
        while True:
            if self.stop:
                return
            function()
            time.sleep(timeout)

    def __enter__(self):
        self.thread.start()

    def __exit__(self, type, value, traceback):
        self.stop = True


def similarity(a, b):
    return SequenceMatcher(None, a, b).ratio()


def nice_cut(s, max_length, ending="..."):
    if len(s) <= max_length:
        return s

    parts = s.split()
    chunk = ""
    for part in parts:
        # if there's enough space to fit in EVERYTHING
        if len(chunk) + len(part) + len(ending) <= max_length:
            chunk += part + " "
        else:
            chunk = chunk.rstrip() + ending
            return chunk

    return chunk  # this really shouldn't happen...


def load_file(filename, skip_commented_lines=True, comment_char='#'):
    try:
        with open(filename, encoding='utf8') as f:
            results = []
            for line in f:
                line = line.strip()

                if line and not (skip_commented_lines and
                                 line.startswith(comment_char)):
                    results.append(line)

            return results

    except IOError as e:
        print("Error loading", filename, e)
        return []


def write_file(filename, contents):
    with open(filename, 'w', encoding='utf8') as f:
        for item in contents:
            f.write(str(item))
            f.write('\n')


def create_bar(progress, length=10, full_char="■", half_char=None, empty_char="□"):
    use_halves = half_char is not None
    fill_to = 2 * round(length * progress)
    residue = fill_to % 2
    chrs = []
    for i in range(1, length + 1):
        if i <= fill_to / 2:
            chrs.append(full_char)
        else:
            break

    if residue > 0 and use_halves:
        chrs.append(half_char)

    return ("***REMOVED***0:" + empty_char + "<" + str(length) + "***REMOVED***").format("".join(chrs))


def get_image_brightness(**kwargs):
    """
    Keyword Arguments:
    image -- A Pillow Image object
    location -- a file path to the image
    url -- the online location of the image
    """
    if "image" in kwargs:
        im = kwargs["image"]
    elif "location" in kwargs:
        im = Image.open(kwargs["location"])
    elif "url" in kwargs:
        resp = requests.get(kwargs["url"])
        content = BytesIO(resp.content)
        im = Image.open(content)
    else:
        raise AttributeError("No image provided")

    im = im.convert("L")
    stat = ImageStat.Stat(im)

    r, g, b = stat.mean
    return math.sqrt(0.241 * (r**2) + 0.691 * (g**2) + 0.068 * (b**2))


def prettydate(d):
    diff = datetime.datetime.now() - d
    s = diff.seconds
    if diff.days > 7 or diff.days < 0:
        return d.strftime('%d %b %y')
    elif diff.days == 1:
        return '1 day ago'
    elif diff.days > 1:
        return '***REMOVED******REMOVED*** days ago'.format(diff.days)
    elif s <= 1:
        return 'just now'
    elif s < 60:
        return '***REMOVED******REMOVED*** seconds ago'.format(round_to_interval(s))
    elif s < 120:
        return '1 minute ago'
    elif s < 3600:
        return '***REMOVED******REMOVED*** minutes ago'.format(round_to_interval(s / 60))
    elif s < 7200:
        return '1 hour ago'
    else:
        return '***REMOVED******REMOVED*** hours ago'.format(round_to_interval(s / 3600))


def ordinal(n, combine=False):
    """
    Return the ordinal of the number n.

    If combine then return the number concatenated with the ordinal
    """
    number_string = str(n) if combine else ""
    special_cases = ***REMOVED***1: "st", 2: "nd", 3: "rd"***REMOVED***
    if not 10 <= n % 100 <= 20 and n % 10 in special_cases:
        return number_string + special_cases[n % 10]
    return number_string + "th"


def clean_songname(query):
    """Clean a Youtube video title so it's shorter and easier to read."""
    to_remove = (
        "1080", "1080p", "4k", "720", "720p", "album", "amv", "audio", "avi",
        "creditless", "dvd", "edition", "eng", "english", "from", "full", "hd",
        "jap", "japanese", "lyrics", "mix", "mp3", "mp4", "music", "new",
        "official", "original", "original sound track", "original soundtrack",
        "ost", "raw", "size", "soundtrack", "special", "textless", "theme",
        "tv", "ver", "version", "video", "with lyrics"
    )

    replacers = (
        # replace common indicators for the artist with a simple dash
        ((r"[\|:]", r"(^|\W)by(\W|$)"), " - "),
        # remove all parentheses and their content and remove "opening 5" stuff
        ((r"\(.*\)", r"(?:^|\b)op(?:ening)?(?:\s+\d***REMOVED***1,2***REMOVED***)?(?:\b|$)"), " "),
        # replace several artist things with &
        ((r"(?:^|\b)(?:feat|ft)(?:\b|$)", ), " & ")
    )

    special_regex = (
        # (r"\b([\w\s]***REMOVED***3,***REMOVED***)\b(?=.*\1)", ""),
        # (r"\(f(?:ea)?t\.?\s?([\w\s\&\-\']***REMOVED***2,***REMOVED***)\)", r" & \1"),
    )
    special_regex_after = (
        # make sure that everything apart from [',] has space ("test -test"
        # converts to "test - test")
        (r"(\s)([^\w\s\',])(\w)", r"\1 \2 \3"),
        (r"(\w)([^\w\s\',])(\s)", r"\1 \2 \3"),
    )

    for target, replacement in special_regex:
        query = re.sub(target, replacement, query, flags=re.IGNORECASE)

    for targets, replacement in replacers:
        for target in targets:
            query = re.sub(target, replacement, query, flags=re.IGNORECASE)

    for key in to_remove:
        # mainly using \W over \b because I want to match [HD] too
        query = re.sub(r"(^|\W)" + key + r"(\W|$)",
                       " ", query, flags=re.IGNORECASE)

    for target, replacement in special_regex_after:
        query = re.sub(target, replacement, query, flags=re.IGNORECASE)

    # remove everything apart from the few allowed characters
    query = re.sub(r"[^\w\s\-\&\',]", " ", query)
    # remove unnecessary whitespaces
    query = re.sub(r"\s+", " ", query)

    no_capitalisation = ("a", "an", "and", "but", "for", "his",
                         "my", "nor", "of", "or", "s", "t", "the", "to", "your", "re", "my")

    # title everything except if it's already UPPER because then it's probably
    # by design. Also don't title no-title words (I guess) if they're not in
    # first place
    word_elements = []
    parts = re.split(r"(\W+)", query)
    for sub_ind, part in enumerate(parts):
        word_elements.append(part if (part.isupper() and len(part) > 2) or (
            part.lower() in no_capitalisation and sub_ind != 0) else part.title())

    query = "".join(word_elements)

    return query.strip(" -&,")


def _run_timestamp_matcher(text):
    songs = ***REMOVED******REMOVED***
    for match in re.finditer(
            r"^(?:(\d***REMOVED***1,2***REMOVED***):)?(\d***REMOVED***1,2***REMOVED***):(\d***REMOVED***2***REMOVED***)(?:\s?.?\s?(?:\d***REMOVED***1,2***REMOVED***:)?(?:\d***REMOVED***1,2***REMOVED***):(?:\d***REMOVED***2***REMOVED***))?\W+(.+?)$",
            text,
            flags=re.MULTILINE):
        timestamp = int(match.group(3))
        timestamp += (
            int(match.group(2)) * 60) if match.group(2) is not None else 0
        timestamp += (
            int(match.group(1)) * 3600) if match.group(1) is not None else 0
        songs[timestamp] = match.group(4)

    if len(songs) < 1:
        for match in re.finditer(
                r"^(.+)\s[\(]?(?:(\d***REMOVED***1,2***REMOVED***):)?(\d***REMOVED***1,2***REMOVED***):(\d***REMOVED***2***REMOVED***)(?:\s?.?\s?(?:\d***REMOVED***1,2***REMOVED***:)?(?:\d***REMOVED***1,2***REMOVED***):(?:\d***REMOVED***2***REMOVED***))?[\)]?$",
                text,
                flags=re.MULTILINE):
            timestamp = int(match.group(4))
            timestamp += (
                int(match.group(3)) * 60) if match.group(3) is not None else 0
            timestamp += (int(match.group(2)) *
                          3600) if match.group(2) is not None else 0
            songs[timestamp] = match.group(1)

    if len(songs) > 0:
        return songs

    return None


def get_video_sub_queue(description, video_id, song_dur):
    timestamps = get_video_timestamps(description, video_id, song_dur)
    if not timestamps:
        return None

    queue = []
    entries = sorted(list(timestamps.keys()))
    for index, key in enumerate(entries):
        start = int(key)
        next_start = int(entries[index + 1]) if index + \
            1 < len(entries) else song_dur

        dur = next_start - start
        sub_entry = ***REMOVED***
            "name": timestamps[key],
            "duration": dur,
            "start": start,
            "index": index,
            "end": next_start
        ***REMOVED***
        queue.append(sub_entry)

    return queue


def get_video_timestamps(description, video_id, song_dur=None):
    if song_dur:
        song_dur += 5  # I'm not that harsh, one second more or less ain't that bad

    if description:
        songs = _run_timestamp_matcher(description)

        if songs is not None:
            # probably for the best to trust the description. Even if not all
            # of them are as reliable as they should be.
            return songs

    if not video_id:
        return None

    try:
        if song_dur and song_dur < 200:  # I don't trust comments when the song is only about 3 mins loading
            return None

        params = ***REMOVED***
            "key": "AIzaSyCvvKzdz-bVJUUyIzKMAYmHZ0FKVLGSJlo",
            "part": "snippet",
            "order": "relevance",
            "textFormat": "plainText",
            "videoId": video_id
        ***REMOVED***
        resp = requests.get(
            "https://www.googleapis.com/youtube/v3/commentThreads", params=params)
        data = resp.json()
        for comment in data["items"]:
            songs = _run_timestamp_matcher(comment["snippet"][
                "topLevelComment"]["snippet"]["textDisplay"])
            if songs is not None and len(songs) > 2:
                if song_dur:  # If we know the song duration I don't want ANY of those duckers to be out of bounds. That's the amount of distrust I have
                    for ts in songs.keys():
                        if ts > song_dur:
                            print(
                                "[TIMESTAMPS] Won't use comment-timestamps because at least one of them is totally out of bounds"
                            )
                            return None  # Yes **NONE**!
                return songs
    except:
        pass

    return None


def _choose_best_thumbnail(thumbnails):
    ranks = ["maxres", "high", "medium", "standard", "default"]
    for res in ranks:
        if res in thumbnails:
            return thumbnails[res]["url"]


def get_related_videos(videoId):
    params = ***REMOVED***
        "part": "snippet",
        "relatedToVideoId": videoId,
        "topicId": "/m/04rlf",
        "type": "video",
        "key": "AIzaSyCvvKzdz-bVJUUyIzKMAYmHZ0FKVLGSJlo"
    ***REMOVED***
    resp = requests.get(
        "https://www.googleapis.com/youtube/v3/search", params=params)
    data = resp.json()
    videos = data["items"]
    if not videos:
        return None
    video_list = []
    for vid in videos:
        video = ***REMOVED***
            "id": vid["id"]["videoId"],
            "title": vid["snippet"]["title"],
            "channel": vid["snippet"]["channelTitle"],
            "thumbnail": _choose_best_thumbnail(vid["snippet"]["thumbnails"]),
            "url": "https://www.youtube.com/watch?v=" + vid["id"]["videoId"]
        ***REMOVED***

        video_list.append(video)

    return video_list


def parse_timestamp(timestamp):
    parts = timestamp.split(":")
    if len(parts) < 1:  # Shouldn't occur, but who knows?
        return None

    # seconds, minutes, hours, days
    values = (1, 60, 60 * 60, 60 * 60 * 24)

    secs = 0
    for i in range(len(parts)):
        try:
            v = int(parts[i])
        except:
            continue

        j = len(parts) - i - 1
        if j >= len(
                values):  # If I don't have a conversion from this to seconds
            continue
        secs += v * values[j]

    return secs


def hex_to_dec(hex_code):
    return int(hex_code.lstrip("#"), 16)


def dec_to_hex(dec_colour):
    return "#***REMOVED***:0>6***REMOVED***".format(hex(dec_colour)[2:]).upper()


def to_timestamp(seconds):
    sec = int(seconds)
    s = "***REMOVED***0:0>2***REMOVED***".format(sec % 60)
    m = (sec // 60) % 60
    h = (sec // 60 // 60) % 24
    d = (sec // 60 // 60 // 24)

    work_string = ""
    if d > 0:
        return ":".join(
            str(x) for x in (d, "***REMOVED***0:0>2***REMOVED***".format(h), "***REMOVED***0:0>2***REMOVED***".format(m), s))
    elif h > 0:
        return ":".join(str(x) for x in (h, "***REMOVED***0:0>2***REMOVED***".format(m), s))
    else:
        return ":".join(str(x) for x in (m, s))


def slugify(value):
    value = unicodedata.normalize('NFKD', value).encode(
        'ascii', 'ignore').decode('ascii')
    value = re.sub('[^\w\s-]', '', value).strip().lower()
    return re.sub('[-\s]+', '-', value)


def format_time_ffmpeg(s):
    total_msec = s * 1000
    total_seconds = s
    total_minutes = s / 60
    total_hours = s / 3600
    msec = int(total_msec % 1000)
    sec = int(total_seconds % 60 - (msec / 3600000))
    mins = int(total_minutes % 60 - (sec / 3600) - (msec / 3600000))
    hours = int(total_hours - (mins / 60) - (sec / 3600) - (msec / 3600000))

    return "***REMOVED***:02d***REMOVED***:***REMOVED***:02d***REMOVED***:***REMOVED***:02d***REMOVED***".format(hours, mins, sec)


def round_to_interval(num, interval=5):
    return int(interval * round(float(num) / interval))


def format_time(s, round_seconds=True, round_base=1, max_specifications=3, combine_with_and=False, replace_one=False, unit_length=2):
    if round_seconds:
        s = round_to_interval(s, round_base)

    minutes, seconds = divmod(s, 60)
    hours, minutes = divmod(minutes, 60)
    days, hours = divmod(hours, 24)

    return_list = []
    if days > 0:
        return_list.append(
            "***REMOVED******REMOVED*** ***REMOVED******REMOVED******REMOVED******REMOVED***".format("a" if days == 1 and replace_one else days, ["d", "day", "day"][unit_length], "s"
                             if days is not 1 and unit_length != 0 else ""))
    if hours > 0:
        return_list.append(
            "***REMOVED******REMOVED*** ***REMOVED******REMOVED******REMOVED******REMOVED***".format("an" if hours == 1 and replace_one else hours, ["h", "hr", "hour"][unit_length],
                             "s" if hours is not 1 and unit_length != 0 else ""))
    if minutes > 0:
        return_list.append(
            "***REMOVED******REMOVED*** ***REMOVED******REMOVED******REMOVED******REMOVED***".format("a" if minutes == 1 and replace_one else
                             minutes, ["m", "min", "minute"][unit_length], "s" if minutes is not 1 and unit_length != 0 else ""))
    if seconds > 0 or s is 0:
        return_list.append(
            "***REMOVED******REMOVED*** ***REMOVED******REMOVED******REMOVED******REMOVED***".format("a" if seconds == 1 and replace_one else
                             seconds, ["s", "sec", "second"][unit_length], "s" if seconds is not 1 and unit_length != 0 else ""))

    if max_specifications is not None:
        return_list = return_list[:max_specifications]

    if combine_with_and and len(return_list) > 1:
        return_list.insert(-1, "and")

    return " ".join(return_list)


def escape_dis(s):
    escape_char = "\\"
    escape_list = ["_", "*"]
    for c in escape_list:
        s = re.sub(re.escape(c), escape_char + c, s)

    return s


def random_line(afile):
    with open(afile) as myfile:
        line = next(myfile)
        for num, aline in enumerate(myfile):
            if random.randrange(num + 2):
                continue
            line = aline
        return line


def paginate(content, *, length=DISCORD_MSG_CHAR_LIMIT, reserve=0):
    """
    Split up a large string or list of strings into chunks for sending to discord.
    """
    if type(content) == str:
        contentlist = content.split('\n')
    elif type(content) == list:
        contentlist = content
    else:
        raise ValueError("Content must be str or list, not %s" % type(content))

    chunks = []
    currentchunk = ''

    for line in contentlist:
        if len(currentchunk) + len(line) < length - reserve:
            currentchunk += line + '\n'
        else:
            chunks.append(currentchunk)
            currentchunk = line + "\n"

    if currentchunk:
        chunks.append(currentchunk)

    return chunks


async def get_header(session, url, headerfield=None, *, timeout=5):
    with aiohttp.Timeout(timeout):
        async with session.head(url) as response:
            if headerfield:
                return response.headers.get(headerfield)
            else:
                return response.headers


def md5sum(filename, limit=0):
    fhash = md5()
    with open(filename, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            fhash.update(chunk)
    return fhash.hexdigest()[-limit:]
