"""
Offline Mode profile authentication handler for SandeshLauncher.
Generates compliant offline player profiles without impersonating Microsoft accounts.
"""

import hashlib
import uuid
from datetime import datetime
from typing import Optional

from auth.token_store import Account
from utils.logging import get_logger

logger = get_logger("auth_offline")

OFFLINE_DISCLAIMER = (
    "Offline Mode does not authenticate with Microsoft and does not verify "
    "Minecraft ownership. It is intended for offline/local use, development/testing, "
    "or servers intentionally configured to permit offline-mode clients."
)


def generate_offline_uuid(username: str) -> str:
    """
    Generates standard offline player UUID compliant with Minecraft Java conventions:
    UUID.nameUUIDFromBytes(("OfflinePlayer:" + username).getBytes(StandardCharsets.UTF_8))
    """
    # MD5 hash version 3 namespace UUID
    hash_bytes = hashlib.md5(f"OfflinePlayer:{username}".encode("utf-8")).digest()
    # Format standard UUID version 3
    byte_array = bytearray(hash_bytes)
    byte_array[6] = (byte_array[6] & 0x0F) | 0x30  # set version 3
    byte_array[8] = (byte_array[8] & 0x3F) | 0x80  # set variant
    return str(uuid.UUID(bytes=bytes(byte_array)))


def create_offline_profile(username: str) -> Account:
    """Creates a distinct offline player profile."""
    clean_username = username.strip()
    if not clean_username:
        raise ValueError("Username cannot be empty.")
    if len(clean_username) > 16 or len(clean_username) < 3:
        raise ValueError("Minecraft username must be between 3 and 16 characters.")

    player_uuid = generate_offline_uuid(clean_username)
    account_id = f"offline_{player_uuid[:12]}"

    account = Account(
        id=account_id,
        account_type="offline",
        username=clean_username,
        uuid=player_uuid,
        skin_url=None,
        avatar_path=None,
        access_token="offline_token",
        refresh_token=None,
        token_expires_at=None,
        is_active=True,
        created_at=datetime.now().isoformat(),
    )

    logger.info(f"Created Offline Profile: {clean_username} (UUID: {player_uuid})")
    return account
