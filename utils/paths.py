"""
Filesystem and path resolution utilities for SandeshLauncher.
Follows XDG standards on Linux and AppData on Windows.
"""

import os
import sys
from pathlib import Path
from typing import Union

from config import APP_NAME


def get_app_data_dir() -> Path:
    """
    Returns the root application data directory based on OS standards.
    Linux: ~/.local/share/SandeshLauncher
    Windows: %APPDATA%\\SandeshLauncher
    Darwin: ~/Library/Application Support/SandeshLauncher
    """
    custom_dir = os.environ.get("SANDESH_DATA_DIR")
    if custom_dir:
        path = Path(custom_dir).resolve()
        path.mkdir(parents=True, exist_ok=True)
        return path

    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        # Linux / Unix XDG_DATA_HOME
        xdg_data = os.environ.get("XDG_DATA_HOME")
        if xdg_data:
            base = Path(xdg_data)
        else:
            base = Path.home() / ".local" / "share"

    app_dir = base / APP_NAME
    app_dir.mkdir(parents=True, exist_ok=True)
    return app_dir


get_launcher_dir = get_app_data_dir


def get_shared_minecraft_dir() -> Path:
    """
    Directory where shared Minecraft assets, libraries, and versions are cached
    so that instances do not duplicate gigabytes of shared assets.
    """
    path = get_app_data_dir() / "minecraft_shared"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_instances_dir() -> Path:
    """Directory containing all user instances."""
    path = get_app_data_dir() / "instances"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_runtimes_dir() -> Path:
    """Directory containing managed Java runtimes."""
    path = get_app_data_dir() / "runtimes"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_cache_dir() -> Path:
    """Directory for temporary caching (skins, API responses, thumbnails)."""
    path = get_app_data_dir() / "cache"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_logs_dir() -> Path:
    """Directory where launcher and Minecraft session logs are stored."""
    path = get_app_data_dir() / "logs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_auth_dir() -> Path:
    """
    Directory where authentication tokens and account data are stored.
    On Unix systems, permissions are restricted to owner only (0700).
    """
    path = get_app_data_dir() / "auth"
    path.mkdir(parents=True, exist_ok=True)
    if sys.platform != "win32":
        try:
            os.chmod(path, 0o700)
        except OSError:
            pass
    return path


def get_settings_file() -> Path:
    """Path to the central settings JSON file."""
    return get_app_data_dir() / "settings.json"


def ensure_safe_path(base_dir: Union[str, Path], user_path: Union[str, Path]) -> Path:
    """
    Validates that user_path is strictly within base_dir.
    Raises ValueError if path traversal is detected.
    """
    base = Path(base_dir).resolve()
    target = (base / user_path).resolve() if not Path(user_path).is_absolute() else Path(user_path).resolve()
    try:
        target.relative_to(base)
    except ValueError:
        raise ValueError(f"Security Alert: Path traversal detected! '{user_path}' is outside '{base}'")
    return target


def get_assets_dir() -> Path:
    """
    Returns the application bundled assets directory.
    Handles development source checkout, PyInstaller --onefile, and PyInstaller --onedir.
    """
    if getattr(sys, "frozen", False):
        if hasattr(sys, "_MEIPASS"):
            meipass_assets = Path(sys._MEIPASS) / "assets"
            if meipass_assets.exists():
                return meipass_assets
        exe_assets = Path(sys.executable).parent / "assets"
        if exe_assets.exists():
            return exe_assets
        internal_assets = Path(sys.executable).parent / "_internal" / "assets"
        if internal_assets.exists():
            return internal_assets

    # Fallback to source directory layout
    return Path(__file__).resolve().parent.parent / "assets"

