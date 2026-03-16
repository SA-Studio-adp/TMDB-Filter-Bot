import os
import aiohttp
import httpx
import asyncio
import logging
import mimetypes
import urllib.parse
from info import GOFILE_TOKEN, STREAM_THROTTLE_MS
from utils import USAGE

# Replicate behavior from bot.py
async def _maybe_call_progress(cb, current, total):
    if not cb:
        return
    try:
        if asyncio.iscoroutinefunction(cb):
            await cb(current, total)
        else:
            cb(current, total)
    except Exception:
        pass

def _filename_from_cd(cd):
    """
    Get filename from content-disposition header.
    """
    if not cd:
        return None
    fname = None
    if 'filename=' in cd:
        try:
            fname = cd.split('filename=')[1].split(';')[0].strip().strip('"').strip("'")
        except Exception:
            pass
    if 'filename*=' in cd:
        try:
            # Handle filename*=UTF-8''...
            part = cd.split('filename*=')[1].split(';')[0].strip()
            if "''" in part:
                 # Minimal parsing for UTF-8''...
                 encoding, _, value = part.partition("''")
                 if encoding.lower() == 'utf-8':
                     fname = urllib.parse.unquote(value)
        except Exception:
            pass
    return fname

def _safe_filename(name):
    """Clean filename by replacing symbols with spaces and decoding URL encoding."""
    if not name:
        return "file"
    
    # First, decode URL-encoded characters
    import urllib.parse
    decoded = urllib.parse.unquote(name)
    
    # Replace common separators and symbols with spaces
    # Keep only alphanumeric, spaces, dots, underscores, and hyphens
    cleaned = ""
    for c in decoded:
        if c.isalnum() or c in (' ', '.', '_', '-'):
            cleaned += c
        else:
            # Replace symbols with spaces
            cleaned += ' '
    
    # Clean up multiple consecutive spaces
    import re
    cleaned = re.sub(r' +', ' ', cleaned)
    
    # Remove leading/trailing spaces and limit length
    cleaned = cleaned.strip()[:200]
    
    return cleaned if cleaned else "file"

async def get_valid_gofile_server(session):
    """Fetch the best available GoFile server, trying the 'servers' endpoint first (best practice),
    then falling back to the legacy 'getServer' logic if needed."""
    
    # 1. Try fetching all servers and picking the first one (preferred method)
    try:
        async with session.get("https://api.gofile.io/servers") as resp:
            if resp.status == 200:
                data = await resp.json()
                if data.get("status") == "ok":
                    servers = data.get("data", {}).get("servers", [])
                    if servers:
                        # Return just the name, e.g. "store1"
                        return servers[0]["name"]
    except Exception as e:
        logging.warning(f"Failed to fetch servers list: {e}")

    # 2. Fallback to legacy getServer (often returns store3 or specific assigned)
    try:
        async with session.get("https://api.gofile.io/getServer") as resp:
            if resp.status == 200:
                data = await resp.json()
                if data.get("status") == "ok":
                    return data["data"]["server"]
    except Exception as e:
        logging.warning(f"Failed to fetch legacy server: {e}")

    # 3. Last resort fallback
    return "store1"

async def _get_gofile_upload_url_async(session):
    server = await get_valid_gofile_server(session)
    return f"https://{server}.gofile.io/contents/uploadfile"

async def upload_to_gofile_streaming(
    client,
    message,
    file_name: str,
    download_progress_cb=None,
    upload_progress_cb=None,
    cancel_check=None,
) -> str | None:
    """Stream media from Telegram directly to GoFile without saving to disk.
    Returns download page URL or None.
    """
    # Best-effort total size from message
    total_size = None
    try:
        if getattr(message, "document", None):
            total_size = getattr(message.document, "file_size", None)
        elif getattr(message, "video", None):
            total_size = getattr(message.video, "file_size", None)
        elif getattr(message, "audio", None):
            total_size = getattr(message.audio, "file_size", None)
        elif getattr(message, "photo", None):
             # Photo handling might be list or single object depending on Pyrogram version/context
            if isinstance(message.photo, list):
                 total_size = message.photo[-1].file_size
            else:
                 total_size = getattr(message.photo, "file_size", None)
    except Exception:
        total_size = None

    # Ensure filename has an extension for better content-type detection
    if not os.path.splitext(file_name)[1]:
        if getattr(message, "photo", None):
            file_name = f"{file_name}.jpg"

    # Timeout config: No total timeout (unlimited), but keep connection/read timeouts
    timeout = aiohttp.ClientTimeout(
        total=None,
        connect=30,
        sock_read=300
    )
    
    # Retry logic
    max_retries = 3
    retry_delay = 5
    
    for attempt in range(max_retries):
        try:
            connector = aiohttp.TCPConnector(
                ttl_dns_cache=300,
                keepalive_timeout=300,
                force_close=False,
                enable_cleanup_closed=True
            )
            async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
                upload_url = await _get_gofile_upload_url_async(session)
                bytes_sent = 0

                async def tg_stream_gen():
                    nonlocal bytes_sent
                    # Prefer chunk size around 1MB
                    async for chunk in client.stream_media(message):
                        if cancel_check and cancel_check():
                            raise asyncio.CancelledError("Upload cancelled by user")
                        if not chunk:
                            continue
                        bytes_sent += len(chunk)
                        
                        # Report progress
                        # For Telegram stream, "download" (tg->bot) and "upload" (bot->gofile) happen simultaneously
                        if download_progress_cb and total_size:
                            try:
                                await _maybe_call_progress(download_progress_cb, bytes_sent, total_size)
                            except Exception:
                                pass
                        if upload_progress_cb:
                            try:
                                upload_progress_cb(bytes_sent, total_size or 1)
                            except Exception:
                                pass
                        
                        yield chunk
                        
                        # Optional throttle
                        if STREAM_THROTTLE_MS:
                            try:
                                await asyncio.sleep(STREAM_THROTTLE_MS / 1000.0)
                            except Exception:
                                pass

                form = aiohttp.FormData()
                if GOFILE_TOKEN:
                    form.add_field("token", GOFILE_TOKEN)
                form.add_field(
                    "file",
                    tg_stream_gen(),
                    filename=file_name,
                    content_type=mimetypes.guess_type(file_name)[0] or "application/octet-stream"
                )

                async with session.post(upload_url, data=form) as resp:
                    resp.raise_for_status()
                    data = await resp.json(content_type=None)

                if isinstance(data, dict) and data.get("status") == "ok":
                    try:
                        USAGE["bytes_uploaded"] += bytes_sent
                        USAGE["completed_uploads"] += 1
                        USAGE["tg_stream_uploads"] += 1
                    except Exception:
                        pass
                    return data["data"].get("downloadPage")
                
                logging.error(f"GoFile returned error: {data}")
                break # Don't retry if API returned error like invalid token
                    
        except (aiohttp.ClientError, asyncio.TimeoutError, ConnectionError) as e:
            if attempt < max_retries - 1:
                logging.warning(f"Upload attempt {attempt + 1}/{max_retries} failed: {e}")
                logging.info(f"Retrying in {retry_delay} seconds...")
                await asyncio.sleep(retry_delay)
                retry_delay *= 2
                continue
            else:
                logging.error(f"Upload attempt {attempt + 1}/{max_retries} failed: {e}")
                raise
    
    try:
        USAGE["failed_uploads"] += 1
    except Exception:
        pass
    return None

async def upload_url_to_gofile_streaming(
    url: str,
    suggested_name: str | None,
    download_progress_cb=None,
    upload_progress_cb=None,
    cancel_check=None,
) -> tuple[str | None, str | None, int | None]:
    """Stream from direct URL to GoFile. Uses aria2c if available for faster downloads."""
    
    # Try aria2c first for faster downloads
    try:
        from aria2_downloader import check_aria2c_installed, download_with_aria2c
        import tempfile
        import shutil
        
        if await check_aria2c_installed():
            logging.info("Using aria2c for fast URL download")
            temp_dir = tempfile.mkdtemp()
            
            try:
                # Download with aria2c
                file_path, file_name, file_size = await download_with_aria2c(
                    url, temp_dir, suggested_name,
                    progress_cb=download_progress_cb,
                    cancel_check=cancel_check
                )
                
                # Upload the downloaded file to GoFile
                timeout = aiohttp.ClientTimeout(total=None, connect=30, sock_read=300)
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    upload_url = await _get_gofile_upload_url_async(session)
                    bytes_sent = 0
                    
                    # Read file and upload
                    with open(file_path, 'rb') as f:
                        async def file_stream_gen():
                            nonlocal bytes_sent
                            while True:
                                chunk = f.read(1024 * 1024)  # 1MB chunks
                                if not chunk:
                                    break
                                if cancel_check and cancel_check():
                                    raise asyncio.CancelledError("Upload cancelled")
                                bytes_sent += len(chunk)
                                if upload_progress_cb:
                                    try:
                                        upload_progress_cb(bytes_sent, file_size or 1)
                                    except Exception:
                                        pass
                                yield chunk
                        
                        form = aiohttp.FormData()
                        if GOFILE_TOKEN:
                            form.add_field("token", GOFILE_TOKEN)
                        form.add_field(
                            "file",
                            file_stream_gen(),
                            filename=file_name,
                            content_type=mimetypes.guess_type(file_name)[0] or "application/octet-stream"
                        )
                        
                        async with session.post(upload_url, data=form) as resp:
                            resp.raise_for_status()
                            data = await resp.json(content_type=None)
                    
                    if isinstance(data, dict) and data.get("status") == "ok":
                        try:
                            USAGE["bytes_downloaded"] += file_size
                            USAGE["bytes_uploaded"] += file_size
                            USAGE["completed_uploads"] += 1
                            USAGE["url_stream_uploads"] += 1
                        except Exception:
                            pass
                        return data["data"].get("downloadPage"), file_name, file_size
                
            finally:
                # Cleanup temp directory
                try:
                    shutil.rmtree(temp_dir, ignore_errors=True)
                except Exception:
                    pass
    
    except Exception as e:
        logging.warning(f"aria2c download failed, falling back to httpx: {e}")
    
    # Fallback to original httpx streaming method
    logging.info("Using httpx streaming for URL download")
    timeout_httpx = httpx.Timeout(None, connect=30)
    async with httpx.AsyncClient(timeout=timeout_httpx, follow_redirects=True) as hc:
        async with hc.stream("GET", url) as resp:
            resp.raise_for_status()
            cd = resp.headers.get("content-disposition")
            name_from_cd = _filename_from_cd(cd)
            name_from_url = os.path.basename(urllib.parse.urlparse(str(resp.url)).path)
            if name_from_url:
                name_from_url = urllib.parse.unquote(name_from_url)
            file_name = suggested_name or name_from_cd or name_from_url or "file.bin"
            file_name = _safe_filename(file_name)
            total_size = int(resp.headers.get("content-length", "0")) or None

            timeout_aiohttp = aiohttp.ClientTimeout(
                total=None,
                connect=30,
                sock_read=300
            )
            async with aiohttp.ClientSession(timeout=timeout_aiohttp) as session:
                upload_url = await _get_gofile_upload_url_async(session)
                bytes_moved = 0

                async def url_stream_gen():
                    nonlocal bytes_moved
                    async for chunk in resp.aiter_bytes(chunk_size=1024 * 1024):
                        if cancel_check and cancel_check():
                            raise asyncio.CancelledError("Upload cancelled by user")
                        if not chunk:
                            continue
                        bytes_moved += len(chunk)
                        if download_progress_cb and total_size:
                            try:
                                await _maybe_call_progress(download_progress_cb, bytes_moved, total_size)
                            except Exception:
                                pass
                        if upload_progress_cb:
                            try:
                                upload_progress_cb(bytes_moved, total_size or 1)
                            except Exception:
                                pass
                        yield chunk
                        if STREAM_THROTTLE_MS:
                            try:
                                await asyncio.sleep(STREAM_THROTTLE_MS / 1000.0)
                            except Exception:
                                pass

                form = aiohttp.FormData()
                if GOFILE_TOKEN:
                    form.add_field("token", GOFILE_TOKEN)
                form.add_field(
                    "file",
                    url_stream_gen(),
                    filename=file_name,
                    content_type=mimetypes.guess_type(file_name)[0] or "application/octet-stream",
                )

                async with session.post(upload_url, data=form) as up_resp:
                    up_resp.raise_for_status()
                    data = await up_resp.json(content_type=None)

            if isinstance(data, dict) and data.get("status") == "ok":
                try:
                    if total_size:
                        USAGE["bytes_downloaded"] += total_size
                        USAGE["bytes_uploaded"] += total_size
                    USAGE["completed_uploads"] += 1
                    USAGE["url_stream_uploads"] += 1
                except Exception:
                    pass
                return data["data"].get("downloadPage"), file_name, total_size
    
    return None, None, None
