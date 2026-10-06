"""
Forge mod loader integration for SandeshLauncher.
Handles Forge version discovery and automated installation.
"""

from pathlib import Path
from typing import Callable, List, Optional

import minecraft_launcher_lib as mll

from utils.logging import get_logger
from utils.paths import get_shared_minecraft_dir

logger = get_logger("forge_loader")


def get_forge_versions(minecraft_version: str) -> List[str]:
    """Returns compatible Forge versions for the given Minecraft version."""
    try:
        found = mll.forge.find_forge_version(minecraft_version)
        if found:
            return [found]
    except Exception as e:
        logger.warning(f"Failed to find Forge version for {minecraft_version}: {e}")
    return []


def is_forge_installed(minecraft_version: str, forge_version: Optional[str] = None) -> Optional[str]:
    """Checks if Forge is already installed in versions/ directory."""
    mc_dir = get_shared_minecraft_dir()
    versions_dir = mc_dir / "versions"
    if not versions_dir.exists():
        return None

    for v_folder in versions_dir.iterdir():
        if v_folder.is_dir() and "forge" in v_folder.name.lower() and minecraft_version in v_folder.name:
            if forge_version and forge_version not in v_folder.name:
                continue
            json_file = v_folder / f"{v_folder.name}.json"
            if json_file.exists():
                return v_folder.name
    return None


def install_forge(
    minecraft_version: str,
    forge_version: Optional[str] = None,
    progress_callback: Optional[Callable[[str, int, int], None]] = None,
    java_path: Optional[str] = None,
) -> str:
    mc_dir = get_shared_minecraft_dir()
    logger.info(f"Installing Forge for Minecraft {minecraft_version}...")

    # Determine Forge version
    target_forge_ver = forge_version
    if not target_forge_ver or target_forge_ver == "latest":
        target_forge_ver = mll.forge.find_forge_version(minecraft_version)
        if not target_forge_ver:
            raise ValueError(f"No compatible Forge release found for Minecraft {minecraft_version}.")

    # Check if already installed
    existing = is_forge_installed(minecraft_version, target_forge_ver)
    if existing:
        logger.info(f"Forge is already installed: {existing}")
        return existing

    callback_dict = {}
    current_status = ["Installing Forge..."]
    current_progress = [0]
    current_max = [100]

    def set_status(status: str) -> None:
        current_status[0] = status
        if progress_callback:
            progress_callback(status, current_progress[0], current_max[0])

    def set_progress(val: int) -> None:
        current_progress[0] = val
        if progress_callback:
            progress_callback(current_status[0], val, current_max[0])

    def set_max(val: int) -> None:
        current_max[0] = val
        if progress_callback:
            progress_callback(current_status[0], current_progress[0], val)

    callback_dict = {
        "setStatus": set_status,
        "setProgress": set_progress,
        "setMax": set_max,
    }

    try:
        mll.forge.install_forge_version(
            versionid=target_forge_ver,
            path=str(mc_dir),
            callback=callback_dict,
            java=java_path
        )
    except Exception as e:
        logger.error(f"Forge installation error: {e}")
        raise RuntimeError(f"Forge installation failed: {e}")

    installed_id = is_forge_installed(minecraft_version, target_forge_ver)
    if not installed_id:
        installed_id = f"{minecraft_version}-forge-{target_forge_ver}"

    logger.info(f"Forge successfully installed: {installed_id}")
    return installed_id
