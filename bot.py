import logging
import logging.config
import os
import sys
import asyncio
from pathlib import Path
from typing import AsyncGenerator, Optional, Union

from aiohttp import web
from pyrogram import Client, __version__, types
from pyrogram.raw.all import layer

from database.ia_filterdb import Media
from database.users_chats_db import db
from database.link_cache_db import link_cache_db
from info import API_HASH, API_ID, BOT_TOKEN, LOG_STR, LOG_CHANNEL, SESSION
from plugins import web_server
from utils import temp


DEFAULT_BIND_ADDRESS = "0.0.0.0"
DEFAULT_PORT = int(os.environ.get("PORT", "8080"))


def configure_logging(config_path: str = "logging.conf") -> None:
    """Configure logging for the application."""

    config_file = Path(config_path)
    if config_file.exists():
        logging.config.fileConfig(str(config_file))
    else:
        logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")

    logging.getLogger().setLevel(logging.INFO)
    logging.getLogger("pyrogram").setLevel(logging.ERROR)
    logging.getLogger("imdbpy").setLevel(logging.ERROR)


configure_logging()


class Bot(Client):
    def __init__(self) -> None:
        super().__init__(
            name=SESSION,
            api_id=API_ID,
            api_hash=API_HASH,
            bot_token=BOT_TOKEN,
            workers=50,
            plugins={"root": "plugins"},
            sleep_threshold=5,
        )
        self._web_app_runner: Optional[web.AppRunner] = None
        self._restart_task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        b_users, b_chats = await db.get_banned()
        temp.BANNED_USERS = b_users
        temp.BANNED_CHATS = b_chats
        await super().start()
        try:
            await Media.ensure_indexes()
        except Exception as e:
            logging.error(f"Failed to create Media indexes (quota?): {e}")
        await link_cache_db.create_indexes()
        me = await self.get_me()
        temp.ME = me.id
        temp.U_NAME = me.username or ""
        temp.B_NAME = me.first_name
        self.username = f"@{me.username}" if me.username else me.first_name

        await self._start_web_server()

        logging.info(
            "%s with Pyrogram v%s (Layer %s) started as %s.",
            me.first_name,
            __version__,
            layer,
            me.username,
        )
        logging.info(LOG_STR)
        self._restart_task = asyncio.get_event_loop().create_task(self._hourly_restart_task())
        logging.info("⏱️ Daily restart scheduler started.")

    async def stop(self, *args) -> None:
        if self._restart_task is not None:
            self._restart_task.cancel()
        await self._stop_web_server()
        await super().stop()
        logging.info("Bot stopped. Bye.")

    async def _hourly_restart_task(self) -> None:
        """Background task: restart the process every hour."""
        await asyncio.sleep(86400)  # wait 24 hours
        logging.info("🔄 Hourly restart initiated...")
        try:
            await self.send_message(LOG_CHANNEL, "🔄 <b>Hourly restart initiated.</b> Bot will be back in a moment...", parse_mode="html")
        except Exception:
            pass
        try:
            os.execv(sys.executable, [sys.executable] + sys.argv)
        except Exception as e:
            logging.error(f"os.execv failed: {e}. Falling back to sys.exit(0).")
            sys.exit(0)

    async def iter_messages(
        self,
        chat_id: Union[int, str],
        limit: int,
        offset: int = 0,
    ) -> AsyncGenerator["types.Message", None]:
        """Iterate sequentially through messages in a chat."""

        if limit <= offset:
            return

        current = max(offset, 1)
        last_message_id = max(limit, current)

        while current <= last_message_id:
            chunk_end = min(current + 199, last_message_id)
            message_ids = list(range(current, chunk_end + 1))
            messages = await self.get_messages(chat_id, message_ids)

            for message in sorted(filter(None, messages), key=lambda msg: msg.id):
                yield message

            current = chunk_end + 1

    async def _start_web_server(self) -> None:
        """Initialize and start the aiohttp web server."""

        if self._web_app_runner is not None:
            return

        app_runner = web.AppRunner(await web_server())
        await app_runner.setup()
        site = web.TCPSite(app_runner, DEFAULT_BIND_ADDRESS, DEFAULT_PORT)
        await site.start()
        self._web_app_runner = app_runner

    async def _stop_web_server(self) -> None:
        """Shutdown the aiohttp web server if it is running."""

        if self._web_app_runner is None:
            return

        await self._web_app_runner.cleanup()
        self._web_app_runner = None


app = Bot()

try:
    app.run()
except AttributeError as exc:
    if "The API key is required for new authorizations." in str(exc):
        raise SystemExit(
            "Startup failed: Telegram credentials are missing or invalid. "
            "Please verify Koyeb environment variables API_ID, API_HASH, and BOT_TOKEN. "
            "API_ID must be a real numeric value from my.telegram.org, not 0 or blank."
        ) from exc
    raise
