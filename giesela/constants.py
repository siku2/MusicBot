import os.path

MAIN_VERSION = "5.0.1"
SUB_VERSION = "refreshed"
VERSION = MAIN_VERSION + "_" + SUB_VERSION

maj_versions = {
    "5": "Refreshed",
    "4": "Webiesela",
    "3": "Giesenesis"
}

AUDIO_CACHE_PATH = "cache/audio_cache"
ABS_AUDIO_CACHE_PATH = os.path.join(os.getcwd(), AUDIO_CACHE_PATH)
DISCORD_MSG_CHAR_LIMIT = 2000
