"""
Installed mods management system for SandeshLauncher instances.
Parses mod metadata directly from JAR archives, enables/disables mods,
and handles mod removal.
"""

import json
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from instances.model import MinecraftInstance
from utils.logging import get_logger
from utils.paths import get_instances_dir

logger = get_logger("mod_manager")


@dataclass
class InstalledMod:
    filename: str
    filepath: Path
    enabled: bool
    name: str
    version: str
    description: str
    mod_id: str
    authors: List[str]
    loader_type: str  # fabric, quilt, forge, unknown


class ModManager:
    def __init__(self, instance: MinecraftInstance):
        self.instance = instance
        self.mods_dir = instance.get_mods_dir(get_instances_dir())

    def list_installed_mods(self) -> List[InstalledMod]:
        """Scans the instance mods directory for .jar and .jar.disabled files."""
        mods: List[InstalledMod] = []
        if not self.mods_dir.exists():
            return mods

        for file in self.mods_dir.iterdir():
            if not file.is_file():
                continue

            is_jar = file.name.endswith(".jar")
            is_disabled = file.name.endswith(".jar.disabled")

            if not (is_jar or is_disabled):
                continue

            enabled = is_jar
            metadata = self._parse_mod_metadata(file)

            mods.append(InstalledMod(
                filename=file.name,
                filepath=file,
                enabled=enabled,
                name=metadata.get("name", file.stem.replace(".jar", "")),
                version=metadata.get("version", "Unknown"),
                description=metadata.get("description", ""),
                mod_id=metadata.get("id", file.stem),
                authors=metadata.get("authors", []),
                loader_type=metadata.get("loader_type", "unknown")
            ))

        # Sort alphabetically
        mods.sort(key=lambda m: m.name.lower())
        return mods

    def _parse_mod_metadata(self, jar_path: Path) -> Dict[str, Any]:
        """Extracts mod info from fabric.mod.json, quilt.mod.json, or mods.toml."""
        result: Dict[str, Any] = {
            "name": jar_path.name,
            "version": "",
            "description": "",
            "id": "",
            "authors": [],
            "loader_type": "unknown"
        }

        try:
            with zipfile.ZipFile(jar_path, "r") as z:
                # 1. Fabric mod
                if "fabric.mod.json" in z.namelist():
                    with z.open("fabric.mod.json") as f:
                        data = json.load(f)
                    result["name"] = data.get("name", jar_path.stem)
                    result["version"] = data.get("version", "")
                    result["description"] = data.get("description", "")
                    result["id"] = data.get("id", "")
                    result["authors"] = [a.get("name", str(a)) if isinstance(a, dict) else str(a) for a in data.get("authors", [])]
                    result["loader_type"] = "fabric"
                    return result

                # 2. Quilt mod
                if "quilt.mod.json" in z.namelist():
                    with z.open("quilt.mod.json") as f:
                        data = json.load(f)
                    q_mod = data.get("quilt_loader", {})
                    meta = q_mod.get("metadata", {})
                    result["name"] = meta.get("name", jar_path.stem)
                    result["version"] = q_mod.get("version", "")
                    result["description"] = meta.get("description", "")
                    result["id"] = q_mod.get("id", "")
                    result["loader_type"] = "quilt"
                    return result

                # 3. Forge / NeoForge mod (mods.toml)
                if "META-INF/mods.toml" in z.namelist():
                    result["loader_type"] = "forge"
                    # Read simple key-values
                    with z.open("META-INF/mods.toml") as f:
                        content = f.read().decode("utf-8", errors="ignore")
                    for line in content.splitlines():
                        if line.strip().startswith("displayName"):
                            result["name"] = line.split("=", 1)[1].strip().strip('"').strip("'")
                        elif line.strip().startswith("version") and not result["version"]:
                            result["version"] = line.split("=", 1)[1].strip().strip('"').strip("'")
                        elif line.strip().startswith("description") and not result["description"]:
                            result["description"] = line.split("=", 1)[1].strip().strip('"').strip("'")
                    return result

        except Exception as e:
            logger.debug(f"Could not read metadata from {jar_path.name}: {e}")

        return result

    def toggle_mod(self, filename: str) -> bool:
        """Toggles a mod between enabled (.jar) and disabled (.jar.disabled)."""
        target = self.mods_dir / filename
        if not target.exists():
            return False

        if target.name.endswith(".jar"):
            new_path = target.with_name(target.name + ".disabled")
        elif target.name.endswith(".jar.disabled"):
            new_path = target.with_name(target.name.replace(".jar.disabled", ".jar"))
        else:
            return False

        target.rename(new_path)
        logger.info(f"Toggled mod: {target.name} -> {new_path.name}")
        return True

    def delete_mod(self, filename: str) -> bool:
        """Permanently deletes a mod file from disk."""
        target = self.mods_dir / filename
        if target.exists() and target.is_file():
            target.unlink()
            logger.info(f"Deleted mod: {filename}")
            return True
        return False
