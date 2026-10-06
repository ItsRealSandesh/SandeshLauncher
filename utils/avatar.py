"""
Player avatar rendering and caching utility for SandeshLauncher.
Downloads player head avatars from Mojang or generates standard Steve head.
"""

from pathlib import Path
from typing import Optional

import requests
from PIL import Image

from utils.logging import get_logger
from utils.paths import get_cache_dir

logger = get_logger("avatar")


def get_default_steve_avatar(target_size: int = 64) -> Path:
    """Creates a local pixelated Steve avatar image if no skin is available."""
    cache_file = get_cache_dir() / f"steve_{target_size}.png"
    if cache_file.exists():
        return cache_file

    steve_colors = [
        ["#271a11", "#271a11", "#271a11", "#271a11", "#271a11", "#271a11", "#271a11", "#271a11"],
        ["#271a11", "#271a11", "#271a11", "#271a11", "#271a11", "#271a11", "#271a11", "#271a11"],
        ["#271a11", "#b98561", "#b98561", "#b98561", "#b98561", "#b98561", "#b98561", "#271a11"],
        ["#b98561", "#b98561", "#b98561", "#b98561", "#b98561", "#b98561", "#b98561", "#b98561"],
        ["#b98561", "#ffffff", "#3b3887", "#b98561", "#b98561", "#3b3887", "#ffffff", "#b98561"],
        ["#b98561", "#b98561", "#b98561", "#7a462b", "#7a462b", "#b98561", "#b98561", "#b98561"],
        ["#b98561", "#b98561", "#4f2b1c", "#4f2b1c", "#4f2b1c", "#4f2b1c", "#b98561", "#b98561"],
        ["#b98561", "#b98561", "#4f2b1c", "#b98561", "#b98561", "#4f2b1c", "#b98561", "#b98561"],
    ]

    img = Image.new("RGBA", (8, 8))
    for y in range(8):
        for x in range(8):
            hex_color = steve_colors[y][x]
            rgb = tuple(int(hex_color.lstrip("#")[i:i+2], 16) for i in (0, 2, 4)) + (255,)
            img.putpixel((x, y), rgb)

    scaled = img.resize((target_size, target_size), resample=Image.Resampling.NEAREST)
    scaled.save(cache_file, "PNG")
    return cache_file


def get_player_avatar(
    player_uuid: str,
    skin_url: Optional[str] = None,
    size: int = 64,
    force_refresh: bool = False
) -> Path:
    """
    Downloads or restores cached player head avatar.
    """
    clean_uuid = player_uuid.replace("-", "").lower()
    cache_file = get_cache_dir() / f"avatar_{clean_uuid}_{size}.png"

    if cache_file.exists() and not force_refresh:
        return cache_file

    # Try downloading avatar from Minotar or Crafatar
    endpoints = [
        f"https://minotar.net/helm/{clean_uuid}/{size}.png",
        f"https://crafatar.com/avatars/{clean_uuid}?size={size}&overlay=true"
    ]

    for ep in endpoints:
        try:
            r = requests.get(ep, timeout=3)
            if r.status_code == 200 and len(r.content) > 100:
                with open(cache_file, "wb") as f:
                    f.write(r.content)
                return cache_file
        except Exception:
            continue

    return get_default_steve_avatar(target_size=size)
