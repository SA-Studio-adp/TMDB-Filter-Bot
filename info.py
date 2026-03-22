import re
from os import environ

id_pattern = re.compile(r'^.\d+$')


def is_enabled(value, default):
    if value.lower() in ["true", "yes", "1", "enable", "y"]:
        return True
    elif value.lower() in ["false", "no", "0", "disable", "n"]:
        return False
    else:
        return default


def get_env(name, default=None, *, required=False):
    value = environ.get(name, default)
    if isinstance(value, str):
        value = value.strip()

    if required and (value is None or value == ""):
        raise RuntimeError(
            f"Missing required environment variable: {name}. "
            "Set it in your deployment provider (for example Koyeb service settings) before starting the bot."
        )

    return value


def get_int_env(name, default=None, *, required=False, min_value=None):
    value = get_env(name, default, required=required)
    if value in (None, ""):
        return 0 if default in (None, "") else int(default)

    try:
        parsed_value = int(value)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(
            f"Environment variable {name} must be an integer, got: {value!r}."
        ) from exc

    if min_value is not None and parsed_value < min_value:
        raise RuntimeError(
            f"Environment variable {name} must be >= {min_value}, got: {parsed_value}."
        )

    return parsed_value


# Bot information
SESSION = get_env('SESSION', 'JACK_ROBOT')
API_ID = get_int_env('API_ID', '27425401')
API_HASH = get_env('API_HASH', '36150e358dd8bc2040dc8decd5250bcd')
BOT_TOKEN = get_env('BOT_TOKEN', '8760557440:AAFFERm3sSQguLmIxqEmWIqtCJUFNATIkOs')

# Bot settings
CACHE_TIME = get_int_env('CACHE_TIME', 300)
USE_CAPTION_FILTER = bool(get_env('USE_CAPTION_FILTER', True))
PICS = (get_env('PICS', '')).split()

# Admins, Channels & Users
ADMINS = [int(admin) if id_pattern.search(admin) else admin for admin in get_env('ADMINS', '7990681306').split()]
CHANNELS = [int(ch) if id_pattern.search(ch) else ch for ch in get_env('CHANNELS', '-1003280201887').split()]
auth_users = [int(user) if id_pattern.search(user) else user for user in get_env('AUTH_USERS', '').split()]

AUTH_USERS = (auth_users + ADMINS) if auth_users else []
auth_channel = get_env('AUTH_CHANNEL', '')
AUTH_CHANNEL = int(auth_channel) if auth_channel and id_pattern.search(auth_channel) else auth_channel
AUTH_GROUPS = [int(admin) for admin in get_env('AUTH_GROUPS', '').split()]
auth_channel_2 = get_env('AUTH_CHANNEL_2', '')
AUTH_CHANNEL_2 = int(auth_channel_2) if auth_channel_2 and id_pattern.search(auth_channel_2) else None
MULTI_FORCESUB = is_enabled((get_env('MULTI_FORCESUB', 'False')), False)

# MongoDB information
DATABASE_URI = get_env('DATABASE_URI', 'mongodb+srv://scleechadp:scstream@sc-stream.wptwpvt.mongodb.net/?retryWrites=true&w=majority&appName=sc-stream')
DATABASE_NAME = get_env('DATABASE_NAME', 'jack')
COLLECTION_NAME = get_env('COLLECTION_NAME', 'bulwark')
# Secondary MongoDB (optional — leave empty to disable dual-DB)
DATABASE_URI_2 = get_env('DATABASE_URI_2', '')
DATABASE_NAME_2 = get_env('DATABASE_NAME_2', 'jack2')
COLLECTION_NAME_2 = get_env('COLLECTION_NAME_2', COLLECTION_NAME)

LOG_CHANNEL = get_int_env('LOG_CHANNEL', '-1003875681466')
SUPPORT_CHAT = get_env('SUPPORT_CHAT', '')

movie_updates_channel = get_env('MOVIE_UPDATES_CHANNEL', '').strip()
if movie_updates_channel and id_pattern.search(movie_updates_channel):
    MOVIE_UPDATES_CHANNEL = int(movie_updates_channel)
else:
    MOVIE_UPDATES_CHANNEL = movie_updates_channel or None

ANNOUNCE_MOVIE_UPDATES = is_enabled(get_env('ANNOUNCE_MOVIE_UPDATES', 'False'), False)

CUSTOM_FILE_CAPTION = get_env('CUSTOM_FILE_CAPTION', '<b>{file_caption} \n Size :- <i>{file_size}</b>')
P_TTI_SHOW_OFF = is_enabled((get_env('P_TTI_SHOW_OFF', 'True')), True)
IMDB = is_enabled((get_env('IMDB', 'True')), True)
SINGLE_BUTTON = is_enabled((get_env('SINGLE_BUTTON', 'True')), True)
CUSTOM_FILE_CAPTION = get_env('CUSTOM_FILE_CAPTION', '<b>{file_caption}</b>')
BATCH_FILE_CAPTION = get_env('BATCH_FILE_CAPTION', CUSTOM_FILE_CAPTION)
IMDB_TEMPLATE = get_env('IMDB_TEMPLATE', 'Hey {message.from_user.mention}, \n Here is the result for your {query} \n <b>🏷 Title</b>: <a href={url}>{title}</a> \n 📆 Year: <a href={url}/releaseinfo>{year}</a> \n 🌟 Rating: <a href={url}/ratings>{rating}</a> / 10 (based on {votes} user ratings.) \n ☀️ Languages : <code>{languages}</code> \n 📀 RunTime: {runtime} Minutes \n 📆 Release Info : {release_date} \n 🎛 Countries : <code>{countries}</code> \n \n Requested by : {message.from_user.mention} \n Powered By ANON')
LONG_IMDB_DESCRIPTION = is_enabled(get_env('LONG_IMDB_DESCRIPTION', 'False'), False)
SPELL_CHECK_REPLY = is_enabled(get_env('SPELL_CHECK_REPLY', 'True'), False)
MAX_LIST_ELM = get_env('MAX_LIST_ELM', None)
INDEX_REQ_CHANNEL = get_int_env('INDEX_REQ_CHANNEL', LOG_CHANNEL)
FILE_STORE_CHANNEL = [int(ch) for ch in (get_env('FILE_STORE_CHANNEL', '')).split()]
MELCOW_NEW_USERS = is_enabled((get_env('MELCOW_NEW_USERS', 'True')), False)

PROTECT_CONTENT = is_enabled((get_env('PROTECT_CONTENT', 'False')), False)
PUBLIC_FILE_STORE = is_enabled((get_env('PUBLIC_FILE_STORE', 'True')), True)

TMDB_API_KEY = get_env('TMDB_API_KEY', 'd67317159cbc25bdad2a79e81f06265d')

# Fast Download / Streaming Configuration
BIN_CHANNEL = get_int_env('BIN_CHANNEL', LOG_CHANNEL)  # Channel to store files for streaming
STREAM_URL = get_env('STREAM_URL', 'https://sabot-ten.vercel.app/')  # Your streaming server URL
ENABLE_STREAM_LINK = is_enabled(get_env('ENABLE_STREAM_LINK', 'True'), True)

# GoFile Upload Configuration
GOFILE_TOKEN = get_env('GOFILE_TOKEN', '')  # GoFile API token for authenticated uploads
STREAM_THROTTLE_MS = get_int_env('STREAM_THROTTLE_MS', '0')  # Throttle for streaming in milliseconds
ENABLE_GOFILE_LINK = is_enabled(get_env('ENABLE_GOFILE_LINK', 'False'), False)

# Missing Constants fix
SELF_DELETE = is_enabled(get_env('SELF_DELETE', 'True'), True)
SELF_DELETE_SECONDS = get_int_env('SELF_DELETE_SECONDS', 300)

LOG_STR = "Current Cusomized Configurations are:-\n"
LOG_STR += ("IMDB Results are enabled, Bot will be showing imdb details for you queries.\n" if IMDB else "IMBD Results are disabled.\n")
LOG_STR += ("P_TTI_SHOW_OFF found , Users will be redirected to send /start to Bot PM instead of sending file file directly\n" if P_TTI_SHOW_OFF else "P_TTI_SHOW_OFF is disabled files will be send in PM, instead of sending start.\n")
LOG_STR += ("SINGLE_BUTTON is Found, filename and files size will be shown in a single button instead of two separate buttons\n" if SINGLE_BUTTON else "SINGLE_BUTTON is disabled , filename and file_sixe will be shown as different buttons\n")
LOG_STR += (f"CUSTOM_FILE_CAPTION enabled with value {CUSTOM_FILE_CAPTION}, your files will be send along with this customized caption.\n" if CUSTOM_FILE_CAPTION else "No CUSTOM_FILE_CAPTION Found, Default captions of file will be used.\n")
LOG_STR += ("Long IMDB storyline enabled." if LONG_IMDB_DESCRIPTION else "LONG_IMDB_DESCRIPTION is disabled , Plot will be shorter.\n")
LOG_STR += ("Spell Check Mode Is Enabled, bot will be suggesting related movies if movie not found\n" if SPELL_CHECK_REPLY else "SPELL_CHECK_REPLY Mode disabled\n")
LOG_STR += (f"MAX_LIST_ELM Found, long list will be shortened to first {MAX_LIST_ELM} elements\n" if MAX_LIST_ELM else "Full List of casts and crew will be shown in imdb template, restrict them by adding a value to MAX_LIST_ELM\n")
if ANNOUNCE_MOVIE_UPDATES and MOVIE_UPDATES_CHANNEL:
    LOG_STR += f"Movie update announcements are enabled for {MOVIE_UPDATES_CHANNEL}.\n"
else:
    LOG_STR += "Movie update announcements are disabled.\n"
LOG_STR += f"Your current IMDB template is {IMDB_TEMPLATE}"
