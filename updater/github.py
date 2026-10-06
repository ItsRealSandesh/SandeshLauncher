"""
GitHub Releases & Raw Version update engine for SandeshLauncher.
Checks for newer application releases on every launch, downloads update files
from GitHub, and seamlessly replaces project files while protecting user data.
"""

import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional, Tuple

import requests
from packaging import version

from config import (
    APP_VERSION,
    DEFAULT_USER_AGENT,
    GITHUB_ARCHIVE_URL,
    GITHUB_RAW_VERSION_URL,
    GITHUB_REPO_NAME,
    GITHUB_REPO_OWNER,
)
from utils.logging import get_logger

logger = get_logger("updater")

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Files and folders that should NEVER be wiped during an update
PROTECTED_ENTRIES = {
    ".git",
    ".venv",
    "instances",
    "minecraft_shared",
    "logs",
    "cache",
    "settings.json",
    "__pycache__",
    "build",
    "dist",
}


@dataclass
class UpdateInfo:
    available: bool
    current_version: str
    latest_version: str
    release_name: str
    changelog: str
    download_url: str
    zip_url: str


def check_for_updates(
    owner: str = GITHUB_REPO_OWNER,
    repo: str = GITHUB_REPO_NAME,
    current_ver: str = APP_VERSION,
) -> UpdateInfo:
    """
    Checks for updates against GitHub.
    Examines both the raw version.txt and the latest GitHub Release.
    """
    latest_ver_str = current_ver
    changelog = "Updated version available on GitHub."
    release_name = ""
    html_url = f"https://github.com/{owner}/{repo}"
    zip_url = f"https://github.com/{owner}/{repo}/archive/refs/heads/main.zip"

    # 1. Check raw version.txt from main branch
    raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/main/version.txt"
    try:
        r_ver = requests.get(
            raw_url,
            headers={"User-Agent": DEFAULT_USER_AGENT},
            timeout=6
        )
        if r_ver.status_code == 200:
            online_ver = r_ver.text.strip().lstrip("v")
            if online_ver:
                try:
                    if version.parse(online_ver) > version.parse(latest_ver_str):
                        latest_ver_str = online_ver
                except Exception:
                    if online_ver != current_ver:
                        latest_ver_str = online_ver
    except Exception as e:
        logger.debug(f"Could not fetch raw version.txt: {e}")

    # 2. Check GitHub Releases API
    api_url = f"https://api.github.com/repos/{owner}/{repo}/releases/latest"
    try:
        r_rel = requests.get(
            api_url,
            headers={
                "User-Agent": DEFAULT_USER_AGENT,
                "Accept": "application/vnd.github.v3+json"
            },
            timeout=6
        )
        if r_rel.status_code == 200:
            rel_data = r_rel.json()
            rel_tag = rel_data.get("tag_name", "").lstrip("v")
            if rel_tag:
                try:
                    if version.parse(rel_tag) >= version.parse(latest_ver_str):
                        latest_ver_str = rel_tag
                        release_name = rel_data.get("name", f"Version {rel_tag}")
                        changelog = rel_data.get("body", changelog)
                        html_url = rel_data.get("html_url", html_url)
                        # Check if a zip asset is attached
                        for asset in rel_data.get("assets", []):
                            if asset.get("name", "").endswith(".zip"):
                                zip_url = asset.get("browser_download_url", zip_url)
                                break
                except Exception:
                    pass
    except Exception as e:
        logger.debug(f"Could not fetch GitHub releases API: {e}")

    is_newer = False
    try:
        is_newer = version.parse(latest_ver_str) > version.parse(current_ver)
    except Exception:
        is_newer = (latest_ver_str != current_ver and latest_ver_str != "")

    return UpdateInfo(
        available=is_newer,
        current_version=current_ver,
        latest_version=latest_ver_str,
        release_name=release_name or f"Version {latest_ver_str}",
        changelog=changelog,
        download_url=html_url,
        zip_url=zip_url,
    )


def download_and_apply_update(
    info: UpdateInfo,
    progress_callback: Optional[Callable[[float, str], None]] = None,
) -> Tuple[bool, str]:
    """
    Downloads update zip archive from GitHub and replaces launcher files.
    Preserves all user data and settings.
    """
    logger.info(f"Starting auto-update to v{info.latest_version} from {info.zip_url}...")

    if progress_callback:
        progress_callback(0.05, "Connecting to GitHub...")

    temp_dir = tempfile.mkdtemp(prefix="sandesh_update_")
    zip_path = Path(temp_dir) / "update.zip"

    try:
        # 1. Download Zip Archive
        resp = requests.get(
            info.zip_url,
            headers={"User-Agent": DEFAULT_USER_AGENT},
            stream=True,
            timeout=30
        )
        resp.raise_for_status()

        total_size = int(resp.headers.get("content-length", 0))
        downloaded = 0

        with open(zip_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=64 * 1024):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size > 0 and progress_callback:
                        frac = min(0.70, 0.05 + (downloaded / total_size) * 0.65)
                        progress_callback(frac, f"Downloading update ({downloaded // 1024} KB)...")

        if progress_callback:
            progress_callback(0.75, "Extracting update archive...")

        extract_dir = Path(temp_dir) / "extracted"
        extract_dir.mkdir(parents=True, exist_ok=True)

        with zipfile.ZipFile(zip_path, "r") as zf:
            # Defensive check: ensure no path traversal in zip
            for member in zf.namelist():
                norm = os.path.normpath(member)
                if norm.startswith("..") or os.path.isabs(norm):
                    raise ValueError(f"Malicious path in update zip: {member}")
            zf.extractall(extract_dir)

        # Find the root folder inside zip
        extracted_items = list(extract_dir.iterdir())
        if len(extracted_items) == 1 and extracted_items[0].is_dir():
            source_root = extracted_items[0]
        else:
            source_root = extract_dir

        if progress_callback:
            progress_callback(0.85, "Updating application files...")

        # 2. Copy/Replace files in PROJECT_ROOT
        for src_item in source_root.iterdir():
            item_name = src_item.name
            if item_name in PROTECTED_ENTRIES:
                continue

            dest_target = PROJECT_ROOT / item_name

            if src_item.is_dir():
                # Recursive directory copy and replace
                _copy_tree_replace(src_item, dest_target)
            else:
                shutil.copy2(src_item, dest_target)

        # 3. Update local version.txt
        version_txt_path = PROJECT_ROOT / "version.txt"
        with open(version_txt_path, "w", encoding="utf-8") as f:
            f.write(f"{info.latest_version}\n")

        if progress_callback:
            progress_callback(1.0, f"Successfully updated to v{info.latest_version}!")

        logger.info(f"Update successfully installed. New version: {info.latest_version}")
        return True, f"Successfully updated to v{info.latest_version}!"

    except Exception as e:
        logger.error(f"Failed to apply update: {e}", exc_info=True)
        return False, f"Update failed: {e}"

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def _copy_tree_replace(src: Path, dst: Path) -> None:
    """Recursively copies files from src to dst, replacing existing files while preserving untracked local files."""
    dst.mkdir(parents=True, exist_ok=True)
    for item in src.iterdir():
        if item.name in PROTECTED_ENTRIES:
            continue
        dest_item = dst / item.name
        if item.is_dir():
            _copy_tree_replace(item, dest_item)
        else:
            shutil.copy2(item, dest_item)


def restart_application() -> None:
    """Restarts the launcher process cleanly with the new code."""
    logger.info("Restarting application...")
    executable = sys.executable
    script = PROJECT_ROOT / "launcher.py"

    args = [executable, str(script)] + sys.argv[1:]
    subprocess.Popen(args, cwd=str(PROJECT_ROOT))
    sys.exit(0)
