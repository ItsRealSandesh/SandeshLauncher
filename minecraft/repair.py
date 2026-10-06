"""
Minecraft installation integrity check and repair utility for SandeshLauncher.
Verifies essential game files and re-triggers targeted asset/library repair.
"""

from pathlib import Path
from typing import Callable, Optional

import minecraft_launcher_lib as mll

from utils.logging import get_logger
from utils.paths import get_shared_minecraft_dir

logger = get_logger("mc_repair")


def verify_and_repair_version(
    version_id: str,
    progress_callback: Optional[Callable[[str, int, int], None]] = None
) -> bool:
    """
    Checks if client.jar and essential version metadata exist.
    If missing or corrupt, repairs the installation via Mojang servers.
    """
    mc_dir = get_shared_minecraft_dir()
    v_folder = mc_dir / "versions" / version_id
    v_json = v_folder / f"{version_id}.json"
    v_jar = v_folder / f"{version_id}.jar"

    needs_repair = False
    if not v_json.exists():
        needs_repair = True
    elif not v_jar.exists() and not ("fabric" in version_id or "quilt" in version_id or "forge" in version_id):
        needs_repair = True

    if needs_repair:
        logger.warning(f"Integrity check failed for {version_id}, repairing...")
        if progress_callback:
            progress_callback("Repairing missing Minecraft files...", 0, 100)

        callback_dict = {
            "setStatus": lambda s: progress_callback(s, 0, 100) if progress_callback else None,
            "setProgress": lambda p: progress_callback("Repairing files...", p, 100) if progress_callback else None,
            "setMax": lambda m: None,
        }

        try:
            mll.install.install_minecraft_version(
                version=version_id,
                minecraft_directory=str(mc_dir),
                callback=callback_dict
            )
            logger.info(f"Version {version_id} successfully repaired.")
            return True
        except Exception as e:
            logger.error(f"Repair failed: {e}")
            raise RuntimeError(f"Unable to repair Minecraft installation: {e}")

    return True
