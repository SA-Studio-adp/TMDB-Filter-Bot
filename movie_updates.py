from __future__ import annotations

import logging
import re
import secrets
from typing import Dict, Optional, Tuple
from urllib.parse import quote_plus

import aiohttp
from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from info import ADMINS, ANNOUNCE_MOVIE_UPDATES, LOG_CHANNEL, MOVIE_UPDATES_CHANNEL, TMDB_API_KEY
from sanitizers import (
    USERNAME_HANDLE_PATTERN,
    USERNAME_LINK_PATTERN,
    clean_caption,
    clean_file_name,
)
from utils import temp

from collections import deque
import time

logger = logging.getLogger(__name__)

# Cache for TMDB results: {movie_name: (timestamp, result)}
tmdb_cache: Dict[str, Tuple[float, Optional[dict]]] = {}
CACHE_TTL = 3600  # 1 hour

processed_movies: set[str] = set()
processed_movies_deque: deque = deque(maxlen=5000)
manual_requests: Dict[str, Tuple[str, Optional[dict], Optional[str], str]] = {}

language_map = {
    "tel": "Telugu",
    "tam": "Tamil",
    "kan": "Kannada",
    "mal": "Malayalam",
    "hin": "Hindi",
    "eng": "English",
    "hindi": "Hindi",
    "tamil": "Tamil",
    "kannada": "Kannada",
    "malayalam": "Malayalam",
    "telugu": "Telugu",
    "english": "English",
    "Kor": "Korean",
    "Jap": "Japanese",
}

quality_map = {
    "org": "Original",
    "hdrip": "HDRip",
    "bluray": "BluRay",
    "web-dl": "WEB-DL",
    "webdl": "WEB-DL",
    "webrip": "WEBRip",
    "web-rip": "WEB-Rip",
}

_YEAR_PATTERN = re.compile(r"\b(19|20)\d{2}\b")
_SEASON_PATTERN = re.compile(r"(?i)(?:s|season)0*(\d{1,2})")
_QUALITY_CALLBACK = re.compile(r"^movie-quality\|(?P<token>[A-Za-z0-9_-]{4,16})\|(?P<quality>[\w-]{2,20})$")

DEFAULT_POSTER = "https://i.postimg.cc/zvY2B53T/20251110-220149.jpg"


async def movie_name_format(file_name: str) -> str:
    """Normalize a raw file name or caption into a clean movie title."""

    cleaned = re.sub(r"http\S+", " ", file_name)
    cleaned = USERNAME_LINK_PATTERN.sub(" ", cleaned)
    cleaned = USERNAME_HANDLE_PATTERN.sub(" ", cleaned)
    cleaned = re.sub(r"[@#]\w+", " ", cleaned)
    cleaned = cleaned.translate(
        str.maketrans({
            "_": " ",
            "[": " ",
            "]": " ",
            "(": " ",
            ")": " ",
            "{": " ",
            "}": " ",
            ".": " ",
            "-": " ",
            ":": " ",
            ";": " ",
            "'": " ",
            "!": " ",
        })
    )

    tokens = []
    for token in re.split(r"\s+", cleaned):
        if not token:
            continue
        lowered = token.lower()
        if lowered in quality_map:
            continue
        if lowered in language_map:
            continue
        if re.fullmatch(r"\d{3,4}p", lowered):
            continue
        if re.fullmatch(r"\d+x\d+", lowered):
            continue
        if re.fullmatch(r"\d+(?:gb|mb)", lowered):
            continue
        if _YEAR_PATTERN.fullmatch(token):
            continue    
        if USERNAME_HANDLE_PATTERN.fullmatch(token):
            continue
        tokens.append(token)

    result = " ".join(tokens).strip()
    return result or file_name.strip()


TMDB_API_BASE_URL = "https://api.themoviedb.org/3"
TMDB_IMAGE_BASE_URL = "https://image.tmdb.org/t/p/w780"


async def get_tmdb(name: str, *, file_hint: Optional[str] = None) -> Optional[dict]:
    if not TMDB_API_KEY:
        logger.warning("TMDB API key is not configured")
        return None

    try:
        tmdb_name = await movie_name_format(name)
        
        # Check cache
        if tmdb_name in tmdb_cache:
            timestamp, cached_result = tmdb_cache[tmdb_name]
            if time.time() - timestamp < CACHE_TTL:
                logger.info("Serving TMDb result from cache for: %s", tmdb_name)
                return cached_result

        logger.info("Searching TMDb for: %s", tmdb_name)

        year_hint_match = _YEAR_PATTERN.search(name)
        if not year_hint_match and file_hint:
            year_hint_match = _YEAR_PATTERN.search(file_hint)
        year_hint = year_hint_match.group(0) if year_hint_match else None

        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            search_params = {
                "api_key": TMDB_API_KEY,
                "query": tmdb_name,
                "include_adult": "false",
                "language": "en-US",
            }
            async with session.get(
                f"{TMDB_API_BASE_URL}/search/multi", params=search_params
            ) as response:
                if response.status != 200:
                    logger.warning("TMDb search failed with status %s", response.status)
                    return None
                search_payload = await response.json()

            results = [
                result
                for result in search_payload.get("results", [])
                if result.get("media_type") in {"movie", "tv"}
            ]

            if not results:
                logger.warning("No TMDb results found for: %s", tmdb_name)
                return None

            def _result_year(result: dict) -> Optional[str]:
                if result.get("media_type") == "movie":
                    date_value = result.get("release_date") or ""
                else:
                    date_value = result.get("first_air_date") or ""
                return date_value[:4] if date_value else None

            results.sort(
                key=lambda item: (
                    1 if year_hint and _result_year(item) == year_hint else 0,
                    item.get("popularity") or 0,
                ),
                reverse=True,
            )

            selected = results[0]
            media_type = selected.get("media_type")
            tmdb_id = selected.get("id")
            if not (media_type and tmdb_id):
                logger.warning("Invalid TMDb result structure for: %s", tmdb_name)
                return None

            detail_params = {
                "api_key": TMDB_API_KEY,
                "language": "en-US",
            }
            async with session.get(
                f"{TMDB_API_BASE_URL}/{media_type}/{tmdb_id}", params=detail_params
            ) as response:
                if response.status != 200:
                    logger.warning(
                        "TMDb details fetch failed with status %s for %s", response.status, tmdb_name
                    )
                    return None
                details = await response.json()

        title = (
            details.get("title")
            or details.get("name")
            or selected.get("title")
            or selected.get("name")
            or tmdb_name
        )

        poster_path = details.get("poster_path") or selected.get("poster_path")
        poster = f"{TMDB_IMAGE_BASE_URL}{poster_path}" if poster_path else None

        vote_average = details.get("vote_average")
        rating = f"{float(vote_average):.1f}" if isinstance(vote_average, (int, float)) else "N/A"

        if media_type == "movie":
            runtime_value = details.get("runtime")
            date_value = details.get("release_date") or selected.get("release_date")
        else:
            runtime_candidates = details.get("episode_run_time") or []
            runtime_value = runtime_candidates[0] if runtime_candidates else None
            date_value = details.get("first_air_date") or selected.get("first_air_date")

        runtime = f"{runtime_value} min" if runtime_value else "N/A"
        year = date_value[:4] if date_value else "N/A"

        spoken_languages = details.get("spoken_languages") or []
        languages = ", ".join(
            filter(
                None,
                (
                    language.get("english_name")
                    or language.get("name")
                    for language in spoken_languages
                ),
            )
        )
        languages = languages or "Unknown"

        tmdb_url = f"https://www.themoviedb.org/{media_type}/{tmdb_id}"

        result = {
            "title": title,
            "poster": poster,
            "rating": rating,
            "runtime": runtime,
            "year": year,
            "languages": languages,
            "url": tmdb_url,
        }
        
        # Update cache
        tmdb_cache[tmdb_name] = (time.time(), result)
        # Clean old cache entries if too big
        if len(tmdb_cache) > 1000:
            # Remove oldest 200 entries
            sorted_keys = sorted(tmdb_cache.keys(), key=lambda k: tmdb_cache[k][0])
            for k in sorted_keys[:200]:
                del tmdb_cache[k]
                
        return result
    except aiohttp.ClientError as exc:
        logger.error("Network error in get_tmdb: %s", exc)
        return None
    except Exception as exc:  # noqa: BLE001 - best effort logging
        logger.error("Error in get_tmdb: %s", exc)
        return None


async def detect_quality_and_language(*captions: Optional[str]) -> Tuple[str, str]:
    detected_quality = None
    detected_languages = set()

    combined = " ".join(part or "" for part in captions)
    lowered = combined.lower()

    for short, full in quality_map.items():
        if short.lower() in lowered:
            detected_quality = full
            break

    for short, full in language_map.items():
        if short.lower() in lowered:
            detected_languages.add(full)

    quality = detected_quality or "HDRip"
    language = ", ".join(sorted(detected_languages)) or "Not Known"
    return quality, language


def _extract_year_and_season(*sources: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    year = None
    season = None
    for source in sources:
        if not source:
            continue
        year_match = _YEAR_PATTERN.search(source)
        if year_match and not year:
            year = year_match.group(0)
        season_match = _SEASON_PATTERN.search(source)
        if season_match and not season:
            season = season_match.group(1)
    return year, season


def _trim_to_identifier(text: str, *, year: Optional[str], season: Optional[str]) -> str:
    lowered = text.lower()
    if year:
        idx = lowered.find(year.lower())
        if idx != -1:
            return text[: idx + len(year)]
    if season:
        idx = lowered.find(season.lower())
        if idx != -1:
            return text[: idx + len(season)]
    return text


def _build_buttons(movie_name: str, tmdb_url: Optional[str]) -> InlineKeyboardMarkup:
    slug = quote_plus(movie_name.strip())
    bot_username = temp.U_NAME or ""
    bot_label = temp.B_NAME or "the bot"

    buttons = []
    if bot_username:
        buttons.append(
            [
                InlineKeyboardButton(
                    "REQUEST GROUP",
                    url=f"https://t.me/Telegram",
                )
            ]
        )

    if tmdb_url:
        if buttons:
            buttons[0].append(InlineKeyboardButton("TMDb", url=tmdb_url))
        else:
            buttons.append([InlineKeyboardButton("TMDb", url=tmdb_url)])

    if isinstance(MOVIE_UPDATES_CHANNEL, str) and MOVIE_UPDATES_CHANNEL.startswith("@"):
        channel_username = MOVIE_UPDATES_CHANNEL[1:]
        channel_url = f"https://t.me/{channel_username}"
    else:
        channel_url = "https://t.me/Telegram/JackBulwark"

    buttons.append([InlineKeyboardButton('MAIN CHANNEL', url=channel_url)])
    return InlineKeyboardMarkup(buttons)

async def send_movie_updates(
    bot: Client,
    *,
    file_name: Optional[str],
    caption: Optional[str],
    file_id: str,
    quality: str,
    language: str,
    force: bool = False,
    tmdb_data_override: Optional[dict] = None,
    year_hint: Optional[str] = None,
) -> None:
    if not (ANNOUNCE_MOVIE_UPDATES and MOVIE_UPDATES_CHANNEL):
        return

    global processed_movies

    raw_source = file_name or caption or ""
    if not raw_source:
        logger.debug("No suitable text to derive movie name for update")
        return

    year, season = _extract_year_and_season(file_name, caption)
    trimmed = _trim_to_identifier(raw_source, year=year, season=season)
    movie_name = await movie_name_format(trimmed)
    if not movie_name:
        logger.debug("Failed to normalize movie name from '%s'", raw_source)
        return

    key = movie_name.lower()
    if not force and key in processed_movies:
        logger.debug("Skipping duplicate movie announcement for %s", movie_name)
        return

    processed_movies.add(key)
    processed_movies_deque.append(key)
    
    # Sync set with deque if needed (deque handles maxlen automatically)
    if len(processed_movies) > 5000:
        # Rebuild set from deque to ensure consistency and remove old items
        processed_movies = set(processed_movies_deque)

    tmdb_data = tmdb_data_override or await get_tmdb(movie_name, file_hint=file_name)
    poster_url = tmdb_data.get("poster") if tmdb_data else None
    rating = tmdb_data.get("rating") if tmdb_data else "N/A"
    runtime = tmdb_data.get("runtime") if tmdb_data else "N/A"
    tmdb_year = tmdb_data.get("year") if tmdb_data else None
    tmdb_languages = tmdb_data.get("languages") if tmdb_data else None
    tmdb_url = tmdb_data.get("url") if tmdb_data else None

    display_year = tmdb_year or year or year_hint or "N/A"
    display_languages = language
    if (not language or language in {"Unknown", "Not Known"}) and tmdb_languages:
        display_languages = tmdb_languages

    rating_display = f"{rating}/10" if rating not in {"N/A"} else "N/A"

    caption_lines = [
        f"<code>{movie_name}</code>",
        "<b>[Copy The Text And Paste In REQUEST GROUP To Get Files.!]</b>",
        "",
        "<b>Files Added To Bot📌</b>",
        "",
        f"<b>📅 Year:</b> {display_year}",
        f"<b>📀 Quality:</b> {quality}",
        f"<b>🌐 Languages:</b> {display_languages}",
        f"<b>⭐ TMDb Rating:</b> {rating_display}",
    ]

    if runtime and runtime not in {"N/A", "Unknown", "None"}:
        caption_lines.append(f"<b>⏳ Runtime:</b> {runtime}")

    channel_reference = None
    if isinstance(MOVIE_UPDATES_CHANNEL, str) and MOVIE_UPDATES_CHANNEL.startswith("@"):
        channel_reference = MOVIE_UPDATES_CHANNEL
    if channel_reference:
        caption_lines.extend(["", f"<b>Join our Channel :- {channel_reference}</b>"])

    caption_message = "\n".join(caption_lines)

    reply_markup = _build_buttons(movie_name, tmdb_url)
    target_channel = MOVIE_UPDATES_CHANNEL

    try:
        if poster_url:
            await bot.send_photo(
                target_channel,
                photo=poster_url,
                caption=caption_message,
                reply_markup=reply_markup,
            )
        else:
            await bot.send_photo(
                target_channel,
                photo=DEFAULT_POSTER,
                caption=caption_message,
                reply_markup=reply_markup,
            )
    except Exception as exc:  # noqa: BLE001 - best effort logging
        logger.error("Failed to send movie update: %s", exc)
        if LOG_CHANNEL:
            await bot.send_message(LOG_CHANNEL, f"Failed to send movie update. Error - {exc}")
        try:
            await bot.send_message(
                target_channel,
                caption_message,
                reply_markup=reply_markup,
                disable_web_page_preview=True,
            )
        except Exception as send_exc:  # noqa: BLE001 - secondary fallback
            logger.error("Fallback text movie update also failed: %s", send_exc)
            if LOG_CHANNEL:
                await bot.send_message(
                    LOG_CHANNEL,
                    f"Fallback movie update send failed. Error - {send_exc}",
                )


async def publish_movie_update(bot: Client, *, media, file_id: str) -> None:
    """Entry point used by plugins after indexing a new media file."""

    if not (ANNOUNCE_MOVIE_UPDATES and MOVIE_UPDATES_CHANNEL):
        return

    mime_type = getattr(media, "mime_type", "") or ""
    if mime_type not in {"video/mp4", "video/x-matroska"}:
        return

    raw_caption = getattr(media, "caption", None)
    caption = clean_caption(raw_caption)

    raw_file_name = getattr(media, "file_name", None)
    file_name = clean_file_name(raw_file_name) or None

    quality, language = await detect_quality_and_language(caption, file_name)
    await send_movie_updates(
        bot,
        file_name=file_name,
        caption=caption,
        file_id=file_id,
        quality=quality,
        language=language,
    )


@Client.on_message(filters.command("post") & filters.user(ADMINS))
async def post_movie(bot: Client, message: Message) -> None:
    try:
        if not (ANNOUNCE_MOVIE_UPDATES and MOVIE_UPDATES_CHANNEL):
            await message.reply_text("Movie updates are currently disabled in the configuration.")
            return

        if len(message.command or []) < 2:
            await message.reply_text("Usage: /post <Movie Name>")
            return

        movie_name = " ".join(message.command[1:])
        tmdb_data = await get_tmdb(movie_name)

        if not tmdb_data:
            await message.reply_text(
                "Could not fetch TMDb data for the given movie name. Please check the name and try again.",
            )
            return

        poster_url = tmdb_data.get("poster", DEFAULT_POSTER)
        movie_rating = tmdb_data.get("rating", "N/A")
        runtime = tmdb_data.get("runtime", "N/A")
        year = tmdb_data.get("year", "N/A")
        languages = tmdb_data.get("languages", "Unknown")
        movie_rating_display = f"{movie_rating}/10" if movie_rating not in {"N/A"} else "N/A"

        qualities = [
            "HDRip",
            "PreDVD",
            "WEB-DL",
            "BluRay",
            "HDTC",
            "WEB-Rip",
            "WEBRip",
            "HDTS",
            "DVDScr",
            "S-Print",
        ]

        token = secrets.token_urlsafe(6)
        manual_requests[token] = (movie_name, tmdb_data, year, languages)
        if len(manual_requests) > 100:
            # Prevent the dictionary from growing indefinitely.
            manual_requests.pop(next(iter(manual_requests)))

        quality_buttons = [
            [InlineKeyboardButton(quality, callback_data=f"movie-quality|{token}|{quality}")]
            for quality in qualities
        ]

        await message.reply_photo(
            photo=poster_url or DEFAULT_POSTER,
            caption=(
                "Fetched TMDb Data:\n\n"
                f"🎬 Movie: {movie_name}\n"
                f"📅 Year: {year}\n"
                f"🌐 Languages: {languages}\n"
                f"⭐ TMDb Rating: {movie_rating_display}\n"
                f"⏳ Runtime: {runtime}\n\n"
                "Please select the quality below:"
            ),
            reply_markup=InlineKeyboardMarkup(quality_buttons),
        )
    except Exception as exc:  # noqa: BLE001 - best effort logging
        logger.error("Failed to process /post command: %s", exc)
        await message.reply_text(f"An error occurred: {exc}")


@Client.on_callback_query(filters.regex(_QUALITY_CALLBACK))
async def quality_selected(bot: Client, callback_query: CallbackQuery) -> None:
    try:
        match = _QUALITY_CALLBACK.match(callback_query.data or "")
        if not match:
            await callback_query.answer("Invalid selection", show_alert=True)
            return

        token = match.group("token")
        selected_quality = match.group("quality")

        request = manual_requests.pop(token, None)
        if not request:
            await callback_query.answer("This request has expired.", show_alert=True)
            return

        movie_name, tmdb_data, year, languages = request

        await send_movie_updates(
            bot,
            file_name=movie_name,
            caption=f"Quality: {selected_quality}",
            file_id="",
            quality=selected_quality,
            language=languages,
            force=True,
            tmdb_data_override=tmdb_data,
            year_hint=year,
        )

        await callback_query.message.delete()
        await bot.send_message(
            callback_query.message.chat.id,
            f"{movie_name} Movie posted successfully in Updates Channel",
        )

        if LOG_CHANNEL:
            await bot.send_message(
                LOG_CHANNEL,
                f"#Posted \n\n{movie_name} Movie posted successfully in Updates Channel",
            )

        await callback_query.answer("Movie posted successfully!")
    except Exception as exc:  # noqa: BLE001 - best effort logging
        logger.error("Error in quality selection: %s", exc)
        await callback_query.answer(f"An error occurred: {exc}")
