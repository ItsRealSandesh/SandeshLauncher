"""
Java runtime manager for SandeshLauncher.
Handles automatic Java matching, validation, and on-demand runtime installation.
"""

import os
import platform
import shutil
import sys
import tarfile
import zipfile
from pathlib import Path
from typing import Callable, List, Optional, Tuple

import requests

from instances.model import MinecraftInstance
from java.detector import (
    JavaInfo,
    detect_system_javas,
    get_required_java_version,
    parse_java_version,
)
from utils.logging import get_logger
from utils.paths import get_runtimes_dir
from utils.security import safe_extract_zip

logger = get_logger("java_manager")


class JavaManager:
    def __init__(self):
        self._cached_javas: List[JavaInfo] = []
        self.refresh()

    def refresh(self) -> List[JavaInfo]:
        self._cached_javas = detect_system_javas()
        return self._cached_javas

    def get_all(self) -> List[JavaInfo]:
        if not self._cached_javas:
            self.refresh()
        return self._cached_javas

    def find_matching_java(self, required_major: int) -> Optional[JavaInfo]:
        """Finds an installed 64-bit Java runtime with the matching major version."""
        for j in self.get_all():
            if j.major_version == required_major and j.is_64bit:
                return j
        # If no exact match, allow higher Java for newer versions or any compatible
        for j in self.get_all():
            if j.major_version >= required_major and j.is_64bit:
                return j
        return None

    def resolve_java_for_instance(
        self,
        instance: MinecraftInstance,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
        status_callback: Optional[Callable[[str], None]] = None,
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Returns (java_executable_path, error_message).
        Automatically resolves the exact required Java runtime from official version JSON
        and installed mod dependencies.
        If required Java is missing, automatically installs Eclipse Temurin without forcing user input.
        """
        from utils.paths import get_instances_dir
        game_dir = instance.get_game_dir(get_instances_dir())
        required_major = get_required_java_version(instance.minecraft_version, game_dir=game_dir)

        # 1. Custom Java override
        if instance.java_path and instance.java_path != "auto":
            info = parse_java_version(instance.java_path)
            if not info:
                return None, f"Specified Java executable '{instance.java_path}' is invalid or cannot be executed."
            if info.major_version < required_major:
                # If custom Java is incompatible, attempt auto-selection so game doesn't crash
                logger.warning(
                    f"Custom Java {info.major_version} is incompatible with Minecraft {instance.minecraft_version} "
                    f"(requires Java {required_major}). Attempting automatic resolution..."
                )
                matching = self.find_matching_java(required_major)
                if matching:
                    return matching.path, None
            else:
                return info.path, None

        # 2. Auto selection from discovered runtimes
        matching = self.find_matching_java(required_major)
        if matching:
            logger.info(f"Auto-selected {matching.display_name} for Minecraft {instance.minecraft_version} (Required: Java {required_major})")
            return matching.path, None

        # 3. Automatic on-demand Java installation ("make launcher always handle java itself no user force need")
        logger.info(f"Required Java {required_major} not found on system. Automatically installing Eclipse Temurin OpenJDK {required_major}...")
        if status_callback:
            status_callback(f"Auto-downloading Java {required_major} runtime...")
        try:
            installed = self.install_temurin_java(required_major, progress_callback=progress_callback)
            if installed and installed.path:
                logger.info(f"Successfully auto-installed and selected Java {required_major}: {installed.path}")
                return installed.path, None
        except Exception as e:
            logger.error(f"Failed to auto-install Java {required_major}: {e}")

        # 4. Fallback: If auto-install failed, try highest available 64-bit Java
        all_javas = self.get_all()
        if all_javas:
            best = all_javas[0]
            logger.warning(f"Using highest available fallback: {best.display_name}")
            return best.path, None

        return None, f"Java {required_major} is required for Minecraft {instance.minecraft_version}, but could not be detected or automatically installed."

    def install_temurin_java(
        self,
        major_version: int,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
    ) -> Optional[JavaInfo]:
        """
        Downloads and installs an official Eclipse Temurin OpenJDK runtime
        into the launcher runtimes directory.
        """
        runtimes_dir = get_runtimes_dir()
        target_dir = runtimes_dir / f"java-{major_version}"
        target_dir.mkdir(parents=True, exist_ok=True)

        # Determine OS and Arch for Adoptium API
        os_name = sys.platform
        if os_name.startswith("linux"):
            os_key = "linux"
        elif os_name == "win32":
            os_key = "windows"
        elif os_name == "darwin":
            os_key = "mac"
        else:
            raise RuntimeError(f"Unsupported operating system: {os_name}")

        machine = platform.machine().lower()
        if machine in ("x86_64", "amd64"):
            arch_key = "x64"
        elif machine in ("aarch64", "arm64"):
            arch_key = "aarch64"
        else:
            arch_key = "x64"

        api_url = (
            f"https://api.adoptium.net/v3/binary/latest/{major_version}/ga/"
            f"{os_key}/{arch_key}/jdk/hotspot/normal/eclipse"
        )

        logger.info(f"Downloading Temurin Java {major_version} from {api_url}...")
        archive_name = f"temurin_{major_version}.tar.gz" if os_key != "windows" else f"temurin_{major_version}.zip"
        archive_path = runtimes_dir / archive_name

        try:
            if progress_callback:
                progress_callback(0, 100, f"Requesting Java {major_version} from Eclipse Temurin...")

            resp = requests.get(api_url, stream=True, timeout=20)
            resp.raise_for_status()
            total_size = int(resp.headers.get("Content-Length", 0))
            downloaded = 0

            with open(archive_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=128 * 1024):
                    if not chunk:
                        continue
                    f.write(chunk)
                    downloaded += len(chunk)
                    if progress_callback and total_size > 0:
                        percent = int((downloaded / total_size) * 100)
                        progress_callback(downloaded, total_size, f"Downloading Java {major_version}... {percent}%")

            if progress_callback:
                progress_callback(total_size, total_size, f"Extracting Java {major_version}...")

            # Extract archive
            if archive_path.name.endswith(".zip"):
                safe_extract_zip(archive_path, target_dir, strip_top_dir=True)
            else:
                with tarfile.open(archive_path, "r:gz") as tar:
                    for member in tar.getmembers():
                        # Strip root folder inside tarball
                        if "/" in member.name:
                            member.name = member.name.split("/", 1)[1]
                            if member.name:
                                tar.extract(member, path=target_dir)

            archive_path.unlink(missing_ok=True)

            # Locate extracted java executable
            candidate = target_dir / "bin" / ("java.exe" if os_key == "windows" else "java")
            if candidate.exists():
                if os_key != "windows":
                    os.chmod(candidate, 0o755)
                self.refresh()
                return parse_java_version(str(candidate))

        except Exception as e:
            logger.error(f"Failed to auto-install Java {major_version}: {e}")
            if archive_path.exists():
                archive_path.unlink(missing_ok=True)
            raise

        return None
