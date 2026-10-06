"""
Minecraft Version management for SandeshLauncher.
Retrieves and caches version manifests from Mojang.
"""

import json
import time
from pathlib import Path
from typing import Dict, List, Any, Optional

import requests

from utils.logging import get_logger
from utils.paths import get_cache_dir

logger = get_logger("versions")

MOJANG_MANIFEST_URL = "https://launchermeta.mojang.com/mc/game/version_manifest_v2.json"
MANIFEST_CACHE_TTL = 3600 * 6  # 6 hours cache


def get_version_manifest(force_refresh: bool = False) -> Dict[str, Any]:
    """Fetches the Mojang version manifest, using disk cache when fresh."""
    cache_file = get_cache_dir() / "mojang_manifest.json"

    if not force_refresh and cache_file.exists():
        try:
            mtime = cache_file.stat().st_mtime
            if time.time() - mtime < MANIFEST_CACHE_TTL:
                with open(cache_file, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to read version manifest cache: {e}")

    logger.info("Fetching fresh Minecraft version manifest from Mojang...")
    try:
        resp = requests.get(MOJANG_MANIFEST_URL, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(data, f)
        return data
    except Exception as e:
        logger.error(f"Error fetching version manifest: {e}")
        # If cache exists even if old, return it
        if cache_file.exists():
            with open(cache_file, "r", encoding="utf-8") as f:
                return json.load(f)
        raise ConnectionError("Unable to retrieve Minecraft versions list from Mojang.")


def get_available_versions(
    include_snapshots: bool = False,
    include_old: bool = False,
    force_refresh: bool = False
) -> List[Dict[str, str]]:
    """
    Returns list of version dicts: [{'id': '1.21.1', 'type': 'release', 'releaseTime': '...'}]
    Sorted latest to oldest.
    """
    manifest = get_version_manifest(force_refresh=force_refresh)
    versions = manifest.get("versions", [])

    results = []
    for v in versions:
        v_type = v.get("type", "release")
        if v_type == "release":
            results.append(v)
        elif v_type == "snapshot" and include_snapshots:
            results.append(v)
        elif v_type in ("old_alpha", "old_beta") and include_old:
            results.append(v)

    return results


def get_latest_release_version() -> str:
    """Returns the latest stable Minecraft release version string (e.g. '1.21.1')."""
    try:
        manifest = get_version_manifest()
        return manifest.get("latest", {}).get("release", "1.21.1")
    except Exception:
        return "1.21.1"
