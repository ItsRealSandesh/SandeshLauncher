"""
Fabric mod loader integration for SandeshLauncher.
Handles loader version queries and automated installation.
"""

from pathlib import Path
from typing import Callable, List, Optional

import minecraft_launcher_lib as mll

from utils.logging import get_logger
from utils.paths import get_shared_minecraft_dir

logger = get_logger("fabric_loader")


def get_fabric_loader_versions(minecraft_version: Optional[str] = None) -> List[str]:
    """Retrieves available Fabric loader versions."""
    try:
        loaders = mll.fabric.get_all_loader_versions()
        versions = [loader["version"] for loader in loaders if loader.get("stable", True)]
        if not versions:
            versions = [loader["version"] for loader in loaders]
        return versions
    except Exception as e:
        logger.warning(f"Failed to fetch Fabric loader versions: {e}")
        return ["0.16.5", "0.16.4", "0.16.0", "0.15.11"]


def is_fabric_installed(minecraft_version: str, loader_version: Optional[str] = None) -> Optional[str]:
    """
    Checks if a matching Fabric version is already installed in versions/.
    Returns installed version ID (e.g. 'fabric-loader-0.16.5-1.21.1') or None.
    """
    mc_dir = get_shared_minecraft_dir()
    versions_dir = mc_dir / "versions"
    if not versions_dir.exists():
        return None

    prefix = f"fabric-loader-"
    for v_folder in versions_dir.iterdir():
        if v_folder.is_dir() and v_folder.name.startswith(prefix) and minecraft_version in v_folder.name:
            if loader_version and loader_version not in v_folder.name:
                continue
            json_file = v_folder / f"{v_folder.name}.json"
            if json_file.exists():
                return v_folder.name
    return None


def install_fabric(
    minecraft_version: str,
    loader_version: Optional[str] = None,
    progress_callback: Optional[Callable[[str, int, int], None]] = None,
    java_path: Optional[str] = None,
) -> str:
    """
    Installs Fabric loader for the specified Minecraft version.
    Returns the installed version ID string.
    """
    mc_dir = get_shared_minecraft_dir()
    logger.info(f"Installing Fabric for Minecraft {minecraft_version} (Loader: {loader_version or 'latest'})...")

    # Resolve loader version if "latest"
    if not loader_version or loader_version == "latest":
        available = get_fabric_loader_versions(minecraft_version)
        loader_version = available[0] if available else None

    # Check if already installed
    existing = is_fabric_installed(minecraft_version, loader_version)
    if existing:
        logger.info(f"Fabric is already installed: {existing}")
        return existing

    callback_dict = {}
    current_status = ["Installing Fabric..."]
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
        mll.fabric.install_fabric(
            minecraft_version=minecraft_version,
            minecraft_directory=str(mc_dir),
            loader_version=loader_version,
            callback=callback_dict,
            java=java_path
        )
    except Exception as e:
        logger.error(f"Fabric installation error: {e}")
        raise RuntimeError(f"Fabric installation failed: {e}")

    # Determine installed version ID
    installed_id = is_fabric_installed(minecraft_version, loader_version)
    if not installed_id:
        installed_id = f"fabric-loader-{loader_version}-{minecraft_version}"

    logger.info(f"Fabric successfully installed: {installed_id}")
    return installed_id
