"""
Network and HTTP utilities for SandeshLauncher.
Provides robust requests with timeout, retry backoff, caching, and hash checking.
"""

import hashlib
import time
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Union

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from config import DEFAULT_REQUEST_TIMEOUT, DEFAULT_USER_AGENT
from utils.logging import get_logger
from utils.paths import get_cache_dir

logger = get_logger("network")

# Global session with configured retries
_session: Optional[requests.Session] = None


def get_http_session() -> requests.Session:
    """Returns a pooled requests.Session with exponential retry configuration."""
    global _session
    if _session is None:
        _session = requests.Session()
        retries = Retry(
            total=3,
            backoff_factor=0.5,
            status_forcelist=[500, 502, 503, 504],
            raise_on_status=False
        )
        adapter = HTTPAdapter(max_retries=retries, pool_connections=10, pool_maxsize=20)
        _session.mount("http://", adapter)
        _session.mount("https://", adapter)
        _session.headers.update({"User-Agent": DEFAULT_USER_AGENT})
    return _session


def safe_get_json(url: str, params: Optional[Dict[str, Any]] = None, timeout: int = DEFAULT_REQUEST_TIMEOUT) -> Any:
    """Performs a GET request returning parsed JSON, raising friendly exceptions on failure."""
    session = get_http_session()
    try:
        response = session.get(url, params=params, timeout=timeout)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.Timeout:
        logger.warning(f"Network timeout reaching {url}")
        raise ConnectionError("Network connection timed out. Please verify your internet connection.")
    except requests.exceptions.ConnectionError:
        logger.warning(f"Connection error reaching {url}")
        raise ConnectionError("Unable to connect to the server. Check your network or firewall.")
    except requests.exceptions.HTTPError as e:
        status = e.response.status_code if e.response is not None else 0
        logger.warning(f"HTTP {status} from {url}")
        raise RuntimeError(f"Server responded with error code HTTP {status}.")
    except Exception as e:
        logger.error(f"Unexpected network error: {e}")
        raise RuntimeError(f"Network request failed: {e}")


def download_file_with_progress(
    url: str,
    destination: Union[str, Path],
    expected_sha1: Optional[str] = None,
    expected_sha512: Optional[str] = None,
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
    cancel_flag: Optional[Callable[[], bool]] = None,
    chunk_size: int = 64 * 1024,
) -> Path:
    """
    Downloads a file with atomic temporary write, live progress reporting,
    and optional cryptographic hash verification.
    """
    dest = Path(destination)
    dest.parent.mkdir(parents=True, exist_ok=True)
    temp_file = dest.with_suffix(dest.suffix + ".part")

    session = get_http_session()
    logger.info(f"Downloading {url} -> {dest.name}")

    response = session.get(url, stream=True, timeout=DEFAULT_REQUEST_TIMEOUT)
    response.raise_for_status()

    total_bytes = int(response.headers.get("Content-Length", 0))
    downloaded_bytes = 0

    hasher_sha1 = hashlib.sha1() if expected_sha1 else None
    hasher_sha512 = hashlib.sha512() if expected_sha512 else None

    start_time = time.time()
    last_update = 0.0

    try:
        with open(temp_file, "wb") as f:
            for chunk in response.iter_content(chunk_size=chunk_size):
                if cancel_flag and cancel_flag():
                    raise InterruptedError("Download was cancelled by user.")
                if not chunk:
                    continue

                f.write(chunk)
                downloaded_bytes += len(chunk)

                if hasher_sha1:
                    hasher_sha1.update(chunk)
                if hasher_sha512:
                    hasher_sha512.update(chunk)

                # Report progress throttled to 10 FPS
                now = time.time()
                if progress_callback and (now - last_update > 0.1 or downloaded_bytes == total_bytes):
                    speed_mb = (downloaded_bytes / (1024 * 1024)) / max(0.001, (now - start_time))
                    status_text = f"{speed_mb:.1f} MB/s"
                    progress_callback(downloaded_bytes, total_bytes, status_text)
                    last_update = now

        # Verify hashes if provided
        if expected_sha1:
            computed_sha1 = hasher_sha1.hexdigest()
            if computed_sha1.lower() != expected_sha1.lower():
                raise ValueError(f"SHA-1 hash mismatch! Expected {expected_sha1}, got {computed_sha1}")

        if expected_sha512:
            computed_sha512 = hasher_sha512.hexdigest()
            if computed_sha512.lower() != expected_sha512.lower():
                raise ValueError(f"SHA-512 hash mismatch! Expected {expected_sha512}, got {computed_sha512}")

        # Atomic rename
        if temp_file.exists():
            temp_file.replace(dest)

        logger.info(f"Successfully downloaded {dest.name} ({downloaded_bytes} bytes)")
        return dest

    except Exception:
        if temp_file.exists():
            try:
                temp_file.unlink()
            except OSError:
                pass
        raise
