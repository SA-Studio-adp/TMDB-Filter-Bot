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
# Bot information
SESSION = environ.get('SESSION', 'JACK_ROBOT')
API_ID = int(environ.get('API_ID', 0))
API_HASH = environ.get('API_HASH', '')
BOT_TOKEN = environ.get('BOT_TOKEN', '')

# Bot settings
CACHE_TIME = int(environ.get('CACHE_TIME', 300))
USE_CAPTION_FILTER = bool(environ.get('USE_CAPTION_FILTER', True))
PICS = (environ.get('PICS', '')).split()

# Admins, Channels & Users
ADMINS = [int(admin) if id_pattern.search(admin) else admin for admin in environ.get('ADMINS', '').split()]
CHANNELS = [int(ch) if id_pattern.search(ch) else ch for ch in environ.get('CHANNELS', "").split()]
auth_users = [int(user) if id_pattern.search(user) else user for user in environ.get('AUTH_USERS', '').split()]

AUTH_USERS = (auth_users + ADMINS) if auth_users else []
auth_channel = environ.get('AUTH_CHANNEL','')
AUTH_CHANNEL = int(auth_channel) if auth_channel and id_pattern.search(auth_channel) else auth_channel
AUTH_GROUPS = [int(admin) for admin in environ.get("AUTH_GROUPS", "").split()]
auth_channel_2 = environ.get('AUTH_CHANNEL_2', '')
AUTH_CHANNEL_2 = int(auth_channel_2) if auth_channel_2 and id_pattern.search(auth_channel_2) else None
MULTI_FORCESUB = is_enabled((environ.get('MULTI_FORCESUB', "False")), False)

# MongoDB information
DATABASE_URI = environ.get('DATABASE_URI', "")
DATABASE_NAME = environ.get('DATABASE_NAME', 'jack')
COLLECTION_NAME = environ.get('COLLECTION_NAME', 'bulwark')
# Secondary MongoDB (optional — leave empty to disable dual-DB)
DATABASE_URI_2 = environ.get('DATABASE_URI_2', '')
DATABASE_NAME_2 = environ.get('DATABASE_NAME_2', 'jack2')
COLLECTION_NAME_2 = environ.get('COLLECTION_NAME_2', COLLECTION_NAME)

LOG_CHANNEL = int(environ.get('LOG_CHANNEL', ''))
SUPPORT_CHAT = environ.get('SUPPORT_CHAT', '')

movie_updates_channel = environ.get('MOVIE_UPDATES_CHANNEL', '').strip()
if movie_updates_channel and id_pattern.search(movie_updates_channel):
    MOVIE_UPDATES_CHANNEL = int(movie_updates_channel)
else:
    MOVIE_UPDATES_CHANNEL = movie_updates_channel or None

ANNOUNCE_MOVIE_UPDATES = is_enabled(environ.get('ANNOUNCE_MOVIE_UPDATES', 'False'), False)

CUSTOM_FILE_CAPTION = environ.get("CUSTOM_FILE_CAPTION", "<b>{file_caption} \n Size :- <i>{file_size}</b>")
P_TTI_SHOW_OFF = is_enabled((environ.get('P_TTI_SHOW_OFF', "True")), False)
IMDB = is_enabled((environ.get('IMDB', "False")), False)
SINGLE_BUTTON = is_enabled((environ.get('SINGLE_BUTTON', "True")), True)
CUSTOM_FILE_CAPTION = environ.get("CUSTOM_FILE_CAPTION", "<b>{file_caption}</b>")
BATCH_FILE_CAPTION = environ.get("BATCH_FILE_CAPTION", CUSTOM_FILE_CAPTION)
IMDB_TEMPLATE = environ.get("IMDB_TEMPLATE", "Hey {message.from_user.mention}, \n Here is the result for your {query} \n <b>🏷 Title</b>: <a href={url}>{title}</a> \n 📆 Year: <a href={url}/releaseinfo>{year}</a> \n 🌟 Rating: <a href={url}/ratings>{rating}</a> / 10 (based on {votes} user ratings.) \n ☀️ Languages : <code>{languages}</code> \n 📀 RunTime: {runtime} Minutes \n 📆 Release Info : {release_date} \n 🎛 Countries : <code>{countries}</code> \n \n Requested by : {message.from_user.mention} \n Powered By ANON")
LONG_IMDB_DESCRIPTION = is_enabled(environ.get("LONG_IMDB_DESCRIPTION", "False"), False)
SPELL_CHECK_REPLY = is_enabled(environ.get("SPELL_CHECK_REPLY", "True"), False)
MAX_LIST_ELM = environ.get("MAX_LIST_ELM", None)
INDEX_REQ_CHANNEL = int(environ.get('INDEX_REQ_CHANNEL', LOG_CHANNEL))
FILE_STORE_CHANNEL = [int(ch) for ch in (environ.get('FILE_STORE_CHANNEL', '')).split()]
MELCOW_NEW_USERS = is_enabled((environ.get('MELCOW_NEW_USERS', "True")), False)

PROTECT_CONTENT = is_enabled((environ.get('PROTECT_CONTENT', "False")), False)
PUBLIC_FILE_STORE = is_enabled((environ.get('PUBLIC_FILE_STORE', "True")), True)

TMDB_API_KEY = environ.get("TMDB_API_KEY", "4dc2518125041d4f904c0ce0ae23b0a2")

# Fast Download / Streaming Configuration
BIN_CHANNEL = int(environ.get('BIN_CHANNEL', LOG_CHANNEL))  # Channel to store files for streaming
STREAM_URL = environ.get('STREAM_URL', '')  # Your streaming server URL
ENABLE_STREAM_LINK = is_enabled(environ.get('ENABLE_STREAM_LINK', "False"), False)

# GoFile Upload Configuration
GOFILE_TOKEN = environ.get('GOFILE_TOKEN', '')  # GoFile API token for authenticated uploads
STREAM_THROTTLE_MS = int(environ.get('STREAM_THROTTLE_MS', '0'))  # Throttle for streaming in milliseconds
ENABLE_GOFILE_LINK = is_enabled(environ.get('ENABLE_GOFILE_LINK', "False"), False)

# Missing Constants fix
SELF_DELETE = is_enabled(environ.get('SELF_DELETE', "False"), False)
SELF_DELETE_SECONDS = int(environ.get('SELF_DELETE_SECONDS', 300))

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
