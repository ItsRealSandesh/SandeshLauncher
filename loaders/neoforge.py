"""
NeoForge mod loader integration for SandeshLauncher.
Handles NeoForge version discovery via official maven metadata and automated installer execution.
"""

import subprocess
from pathlib import Path
from typing import Callable, List, Optional

import requests

from utils.logging import get_logger
from utils.network import download_file_with_progress
from utils.paths import get_shared_minecraft_dir, get_cache_dir

logger = get_logger("neoforge_loader")

NEOFORGE_MAVEN_VERSIONS_URL = "https://maven.neoforged.net/api/maven/versions/releases/net/neoforged/neoforge"
NEOFORGE_MAVEN_DOWNLOAD_URL = "https://maven.neoforged.net/releases/net/neoforged/neoforge/{version}/neoforge-{version}-installer.jar"


def get_neoforge_versions(minecraft_version: str) -> List[str]:
    """Retrieves available NeoForge versions matching a Minecraft version."""
    try:
        resp = requests.get(NEOFORGE_MAVEN_VERSIONS_URL, timeout=8)
        resp.raise_for_status()
        all_versions = resp.json().get("versions", [])

        # Match prefix
        # e.g. 1.21.1 -> 21.1.
        # e.g. 1.20.4 -> 20.4.
        parts = minecraft_version.split(".")
        if len(parts) >= 2 and parts[0] == "1":
            minor = parts[1]
            patch = parts[2] if len(parts) > 2 else "0"
            prefix1 = f"{minor}.{patch}."
            prefix2 = f"1.{minor}.{patch}-"
        else:
            prefix1 = minecraft_version
            prefix2 = minecraft_version

        matched = [
            v for v in all_versions
            if v.startswith(prefix1) or v.startswith(prefix2)
        ]
        matched.reverse()  # Latest first
        return matched
    except Exception as e:
        logger.warning(f"Could not fetch NeoForge versions: {e}")
        return []


def is_neoforge_installed(minecraft_version: str, neoforge_version: Optional[str] = None) -> Optional[str]:
    """Checks if NeoForge is already installed in versions/ directory."""
    mc_dir = get_shared_minecraft_dir()
    versions_dir = mc_dir / "versions"
    if not versions_dir.exists():
        return None

    for v_folder in versions_dir.iterdir():
        if v_folder.is_dir() and "neoforge" in v_folder.name.lower():
            if neoforge_version and neoforge_version in v_folder.name:
                return v_folder.name
            if minecraft_version in v_folder.name:
                return v_folder.name
    return None


def install_neoforge(
    minecraft_version: str,
    neoforge_version: Optional[str] = None,
    progress_callback: Optional[Callable[[str, int, int], None]] = None,
    java_path: Optional[str] = None,
) -> str:
    mc_dir = get_shared_minecraft_dir()
    logger.info(f"Installing NeoForge for Minecraft {minecraft_version}...")

    # Determine version
    target_ver = neoforge_version
    if not target_ver or target_ver == "latest":
        available = get_neoforge_versions(minecraft_version)
        if not available:
            raise ValueError(f"No compatible NeoForge versions found for Minecraft {minecraft_version}")
        target_ver = available[0]

    existing = is_neoforge_installed(minecraft_version, target_ver)
    if existing:
        logger.info(f"NeoForge is already installed: {existing}")
        return existing

    installer_url = NEOFORGE_MAVEN_DOWNLOAD_URL.format(version=target_ver)
    cache_dir = get_cache_dir() / "installers"
    cache_dir.mkdir(parents=True, exist_ok=True)
    installer_jar = cache_dir / f"neoforge-{target_ver}-installer.jar"

    if progress_callback:
        progress_callback("Downloading NeoForge installer...", 10, 100)

    download_file_with_progress(
        url=installer_url,
        destination=installer_jar,
        progress_callback=lambda cur, tot, sp: progress_callback(f"Downloading NeoForge installer ({sp})...", cur, tot) if progress_callback else None
    )

    if progress_callback:
        progress_callback("Running NeoForge installer (this may take a minute)...", 60, 100)

    # Run installer with client flag
    java_exec = java_path or "java"
    cmd = [java_exec, "-jar", str(installer_jar), "--installClient", str(mc_dir)]

    logger.info(f"Running NeoForge installer: {' '.join(cmd)}")
    proc = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False
    )

    if proc.returncode != 0:
        logger.error(f"NeoForge installer failed with code {proc.returncode}: {proc.stderr}")
        raise RuntimeError(f"NeoForge installer failed: {proc.stderr or proc.stdout}")

    installed_id = is_neoforge_installed(minecraft_version, target_ver)
    if not installed_id:
        installed_id = f"neoforge-{target_ver}"

    logger.info(f"NeoForge successfully installed: {installed_id}")
    return installed_id
