"""
Screen and Resolution utility for SandeshLauncher.
Provides dynamic desktop display detection, responsive window fitting,
and resolution matching for game instances.
"""

import sys
import tkinter as tk
from typing import List, Tuple
from utils.logging import get_logger

logger = get_logger("screen")

_CACHED_DESKTOP_RES: Tuple[int, int] = (0, 0)


def get_desktop_resolution() -> Tuple[int, int]:
    """
    Detects the user's primary monitor desktop resolution.
    Returns (width, height), e.g. (1366, 768) or (1920, 1080).
    """
    global _CACHED_DESKTOP_RES
    if _CACHED_DESKTOP_RES != (0, 0):
        return _CACHED_DESKTOP_RES

    try:
        root = tk._default_root
        if root is not None and hasattr(root, "winfo_screenwidth"):
            w = root.winfo_screenwidth()
            h = root.winfo_screenheight()
            if w > 400 and h > 300:
                _CACHED_DESKTOP_RES = (w, h)
                return _CACHED_DESKTOP_RES

        temp = tk.Tk()
        temp.withdraw()
        w = temp.winfo_screenwidth()
        h = temp.winfo_screenheight()
        temp.destroy()
        if w > 400 and h > 300:
            _CACHED_DESKTOP_RES = (w, h)
            return _CACHED_DESKTOP_RES
    except Exception as e:
        logger.debug(f"Failed to query screen resolution via Tkinter: {e}")

    # Fallback to standard 1366x768 (common laptop display)
    _CACHED_DESKTOP_RES = (1366, 768)
    return _CACHED_DESKTOP_RES


def get_standard_resolutions() -> List[Tuple[int, int, str]]:
    """
    Returns a list of common resolutions formatted with the detected desktop resolution first.
    """
    desk_w, desk_h = get_desktop_resolution()
    resolutions = [
        (desk_w, desk_h, f"Desktop Native ({desk_w}x{desk_h})"),
        (1920, 1080, "1080p FHD (1920x1080)"),
        (1600, 900, "900p HD+ (1600x900)"),
        (1366, 768, "768p WXGA (1366x768)"),
        (1280, 720, "720p HD (1280x720)"),
        (1024, 768, "1024x768 (4:3)"),
        (854, 480, "480p Standard (854x480)"),
    ]
    # Deduplicate while preserving order
    seen = set()
    unique = []
    for w, h, label in resolutions:
        key = (w, h)
        if key not in seen:
            seen.add(key)
            unique.append((w, h, label))
    return unique


def apply_desktop_window_fit(window: tk.Tk, maximize: bool = True) -> None:
    """
    Applies desktop sizing and placement to a Tkinter / CustomTkinter window.
    Ensures adequate taskbar and panel clearance and runs maximized natively so
    there is zero clipping, titlebar overflow, or taskbar obscuration.
    """
    try:
        screen_w, screen_h = get_desktop_resolution()

        # Compute comfortable non-maximized fallback bounds
        fallback_w = min(1200, max(840, int(screen_w * 0.88)))
        fallback_h = min(780, max(520, int(screen_h * 0.84)))

        if fallback_h > screen_h - 60:
            fallback_h = max(500, screen_h - 60)
        if fallback_w > screen_w - 30:
            fallback_w = max(800, screen_w - 30)

        pos_x = max(0, (screen_w - fallback_w) // 2)
        pos_y = max(0, (screen_h - fallback_h) // 2 - 10)

        window.geometry(f"{fallback_w}x{fallback_h}+{pos_x}+{pos_y}")
        window.minsize(800, 480)

        if maximize:
            if sys.platform.startswith("win"):
                window.state("zoomed")
            else:
                # Linux X11 native maximized state
                window.attributes("-zoomed", True)
    except Exception as e:
        logger.debug(f"apply_desktop_window_fit exception: {e}")
