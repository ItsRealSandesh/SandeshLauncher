"""
SandeshLauncher Configuration Module
Centralized, non-secret configuration constants and defaults.
"""

import os
from typing import Dict, Any

def _load_app_version() -> str:
    """Reads application version from version.txt if available."""
    try:
        v_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "version.txt")
        if os.path.isfile(v_file):
            with open(v_file, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if content:
                    return content
    except Exception:
        pass
    return "1.0.0"


APP_NAME = "SandeshLauncher"
APP_VERSION = _load_app_version()
APP_DESCRIPTION = "Modern, Fast & Lightweight Minecraft Java Edition Launcher"
APP_AUTHOR = "SandeshLauncher Team"

# Microsoft OAuth Application Configuration
# Registered as Public Client (Desktop application)
MICROSOFT_CLIENT_ID = "4bc2d5f5-05c1-4377-893d-8a11da7567f5"
MICROSOFT_REDIRECT_URI = "http://localhost"
MICROSOFT_AUTH_SCOPE = "XboxLive.signin offline_access"

# Modrinth API Configuration
MODRINTH_API_URL = "https://api.modrinth.com/v2"
DEFAULT_USER_AGENT = f"{APP_NAME}/{APP_VERSION} (desktop; contact: support@sandeshlauncher.local)"

# GitHub Update Check & Auto-Updater
GITHUB_REPO_OWNER = "ItsRealSandesh"
GITHUB_REPO_NAME = "SandeshLauncher"
GITHUB_RAW_VERSION_URL = f"https://raw.githubusercontent.com/{GITHUB_REPO_OWNER}/{GITHUB_REPO_NAME}/main/version.txt"
GITHUB_ARCHIVE_URL = f"https://github.com/{GITHUB_REPO_OWNER}/{GITHUB_REPO_NAME}/archive/refs/heads/main.zip"

# UI Defaults & Theme
THEME_MODE = "dark"
ACCENT_COLOR = "#10b981"  # Emerald Green
ACCENT_HOVER_COLOR = "#059669"
BG_COLOR = "#0f172a"  # Slate 900
SURFACE_COLOR = "#1e293b"  # Slate 800
SURFACE_LIGHT_COLOR = "#334155"  # Slate 700
TEXT_COLOR = "#f8fafc"
TEXT_MUTED_COLOR = "#94a3b8"

# Memory and Launch Defaults
DEFAULT_MIN_RAM_MB = 1024
DEFAULT_MAX_RAM_MB = 4096
# Tuned G1GC flags for fast game launch, high FPS, and micro-stutter elimination
DEFAULT_JVM_ARGS = "-XX:+UseG1GC -XX:+ParallelRefProcEnabled -XX:MaxGCPauseMillis=50 -XX:+UnlockExperimentalVMOptions -XX:+DisableExplicitGC -XX:G1NewSizePercent=20 -XX:G1MaxNewSizePercent=35 -XX:G1ReservePercent=15 -XX:G1HeapRegionSize=16M -Djava.net.preferIPv4Stack=true -Dfile.encoding=UTF-8 -XX:+UseStringDeduplication"
# 0 indicates dynamic auto-match to current primary desktop display resolution
DEFAULT_RESOLUTION_WIDTH = 0
DEFAULT_RESOLUTION_HEIGHT = 0

# Network Settings
DEFAULT_REQUEST_TIMEOUT = 15  # seconds
DEFAULT_MAX_CONCURRENT_DOWNLOADS = 4
DEFAULT_DOWNLOAD_CHUNK_SIZE = 64 * 1024  # 64 KB

# Legal / Disclaimer
DISCLAIMER = (
    "SandeshLauncher is an independent Minecraft launcher and is not "
    "affiliated with or endorsed by Mojang Studios or Microsoft."
)
