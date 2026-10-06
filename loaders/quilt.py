"""
Quilt mod loader integration for SandeshLauncher.
Handles loader version queries and automated installation.
"""

from pathlib import Path
from typing import Callable, List, Optional

import minecraft_launcher_lib as mll

from utils.logging import get_logger
from utils.paths import get_shared_minecraft_dir

logger = get_logger("quilt_loader")


def get_quilt_loader_versions(minecraft_version: Optional[str] = None) -> List[str]:
    """Retrieves available Quilt loader versions."""
    try:
        loaders = mll.quilt.get_all_loader_versions()
        return [l["version"] for l in loaders]
    except Exception as e:
        logger.warning(f"Failed to fetch Quilt loader versions: {e}")
        return ["0.26.1", "0.26.0", "0.25.0"]


def is_quilt_installed(minecraft_version: str, loader_version: Optional[str] = None) -> Optional[str]:
    """Checks if a matching Quilt version is already installed in versions/."""
    mc_dir = get_shared_minecraft_dir()
    versions_dir = mc_dir / "versions"
    if not versions_dir.exists():
        return None

    prefix = "quilt-loader-"
    for v_folder in versions_dir.iterdir():
        if v_folder.is_dir() and v_folder.name.startswith(prefix) and minecraft_version in v_folder.name:
            if loader_version and loader_version not in v_folder.name:
                continue
            json_file = v_folder / f"{v_folder.name}.json"
            if json_file.exists():
                return v_folder.name
    return None


def install_quilt(
    minecraft_version: str,
    loader_version: Optional[str] = None,
    progress_callback: Optional[Callable[[str, int, int], None]] = None,
    java_path: Optional[str] = None,
) -> str:
    mc_dir = get_shared_minecraft_dir()
    logger.info(f"Installing Quilt for Minecraft {minecraft_version} (Loader: {loader_version or 'latest'})...")

    if not loader_version or loader_version == "latest":
        available = get_quilt_loader_versions(minecraft_version)
        loader_version = available[0] if available else None

    existing = is_quilt_installed(minecraft_version, loader_version)
    if existing:
        logger.info(f"Quilt is already installed: {existing}")
        return existing

    callback_dict = {}
    current_status = ["Installing Quilt..."]
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
        mll.quilt.install_quilt(
            minecraft_version=minecraft_version,
            minecraft_directory=str(mc_dir),
            loader_version=loader_version,
            callback=callback_dict,
            java=java_path
        )
    except Exception as e:
        logger.error(f"Quilt installation error: {e}")
        raise RuntimeError(f"Quilt installation failed: {e}")

    installed_id = is_quilt_installed(minecraft_version, loader_version)
    if not installed_id:
        installed_id = f"quilt-loader-{loader_version}-{minecraft_version}"

    logger.info(f"Quilt successfully installed: {installed_id}")
    return installed_id
