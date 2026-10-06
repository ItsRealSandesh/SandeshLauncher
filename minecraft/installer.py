"""
Unified Minecraft and Loader installation pipeline for SandeshLauncher.
Coordinates base Minecraft version installation and mod loader setups.
"""

from pathlib import Path
from typing import Callable, Optional

import minecraft_launcher_lib as mll

from instances.model import MinecraftInstance
from loaders.fabric import install_fabric, is_fabric_installed
from loaders.forge import install_forge, is_forge_installed
from loaders.neoforge import install_neoforge, is_neoforge_installed
from loaders.quilt import install_quilt, is_quilt_installed
from utils.logging import get_logger
from utils.paths import get_shared_minecraft_dir

logger = get_logger("mc_installer")


def is_version_installed(version_id: str) -> bool:
    """Checks if a version JSON file exists in the shared versions directory."""
    mc_dir = get_shared_minecraft_dir()
    v_json = mc_dir / "versions" / version_id / f"{version_id}.json"
    return v_json.exists()


def install_base_minecraft(
    version: str,
    progress_callback: Optional[Callable[[str, int, int], None]] = None
) -> None:
    """Installs the vanilla Minecraft base version, libraries, and assets."""
    mc_dir = get_shared_minecraft_dir()
    if is_version_installed(version):
        logger.info(f"Vanilla Minecraft {version} is already installed.")
        return

    logger.info(f"Installing base Minecraft {version}...")
    current_status = ["Downloading Minecraft..."]
    current_prog = [0]
    current_max = [100]

    def set_status(s: str) -> None:
        current_status[0] = s
        if progress_callback:
            progress_callback(s, current_prog[0], current_max[0])

    def set_progress(p: int) -> None:
        current_prog[0] = p
        if progress_callback:
            progress_callback(current_status[0], p, current_max[0])

    def set_max(m: int) -> None:
        current_max[0] = m
        if progress_callback:
            progress_callback(current_status[0], current_prog[0], m)

    callback_dict = {
        "setStatus": set_status,
        "setProgress": set_progress,
        "setMax": set_max,
    }

    try:
        mll.install.install_minecraft_version(
            version=version,
            minecraft_directory=str(mc_dir),
            callback=callback_dict
        )
        logger.info(f"Base Minecraft {version} installed successfully.")
    except Exception as e:
        logger.error(f"Failed to install base Minecraft {version}: {e}")
        raise RuntimeError(f"Minecraft installation failed: {e}")


def prepare_instance_environment(
    instance: MinecraftInstance,
    progress_callback: Optional[Callable[[str, int, int], None]] = None,
    java_path: Optional[str] = None
) -> str:
    """
    Ensures all required game files and loader for the instance are installed.
    Returns the launchable version ID (e.g. '1.21.1' or 'fabric-loader-0.16.5-1.21.1').
    """
    mc_ver = instance.minecraft_version
    loader = (instance.loader or "vanilla").lower()

    # 1. Base Minecraft
    if not is_version_installed(mc_ver):
        if progress_callback:
            progress_callback(f"Installing Minecraft {mc_ver}...", 0, 100)
        install_base_minecraft(mc_ver, progress_callback=progress_callback)

    # 2. Loader
    if loader == "vanilla":
        return mc_ver

    elif loader == "fabric":
        existing = is_fabric_installed(mc_ver, instance.loader_version if instance.loader_version != "latest" else None)
        if existing:
            return existing
        return install_fabric(
            minecraft_version=mc_ver,
            loader_version=instance.loader_version,
            progress_callback=progress_callback,
            java_path=java_path
        )

    elif loader == "quilt":
        existing = is_quilt_installed(mc_ver, instance.loader_version if instance.loader_version != "latest" else None)
        if existing:
            return existing
        return install_quilt(
            minecraft_version=mc_ver,
            loader_version=instance.loader_version,
            progress_callback=progress_callback,
            java_path=java_path
        )

    elif loader == "forge":
        existing = is_forge_installed(mc_ver, instance.loader_version if instance.loader_version != "latest" else None)
        if existing:
            return existing
        return install_forge(
            minecraft_version=mc_ver,
            forge_version=instance.loader_version,
            progress_callback=progress_callback,
            java_path=java_path
        )

    elif loader == "neoforge":
        existing = is_neoforge_installed(mc_ver, instance.loader_version if instance.loader_version != "latest" else None)
        if existing:
            return existing
        return install_neoforge(
            minecraft_version=mc_ver,
            neoforge_version=instance.loader_version,
            progress_callback=progress_callback,
            java_path=java_path
        )

    else:
        logger.warning(f"Unknown loader '{loader}', launching as vanilla.")
        return mc_ver
