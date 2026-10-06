"""
Instance Manager for SandeshLauncher.
Handles creation, listing, cloning, deletion, and configuration of instances.
"""

import json
import re
import shutil
import uuid
from pathlib import Path
from typing import Dict, List, Optional

from instances.model import MinecraftInstance
from utils.logging import get_logger
from utils.paths import get_instances_dir, ensure_safe_path
from utils.security import safe_extract_zip

logger = get_logger("instance_manager")


class InstanceManager:
    def __init__(self, instances_dir: Optional[Path] = None):
        self.root_dir = instances_dir or get_instances_dir()
        self.root_dir.mkdir(parents=True, exist_ok=True)
        self._instances: Dict[str, MinecraftInstance] = {}
        self.reload_all()

    def reload_all(self) -> List[MinecraftInstance]:
        """Scans the instances directory and reloads all valid instance models."""
        self._instances.clear()
        if not self.root_dir.exists():
            return []

        for folder in self.root_dir.iterdir():
            if folder.is_dir():
                meta_file = folder / "instance.json"
                if meta_file.exists():
                    try:
                        with open(meta_file, "r", encoding="utf-8") as f:
                            data = json.load(f)
                        inst = MinecraftInstance.from_dict(data)
                        inst.instance_dir = str(folder)
                        self._instances[inst.id] = inst
                    except Exception as e:
                        logger.warning(f"Failed to load instance from {folder}: {e}")

        logger.info(f"Loaded {len(self._instances)} instance(s).")
        return list(self._instances.values())

    def get_all(self) -> List[MinecraftInstance]:
        """Returns all loaded instances."""
        return list(self._instances.values())

    def get(self, instance_id: str) -> Optional[MinecraftInstance]:
        return self._instances.get(instance_id)

    def get_by_name(self, name: str) -> Optional[MinecraftInstance]:
        """Finds instance by human-readable name."""
        for inst in self._instances.values():
            if inst.name == name:
                return inst
        return None

    def get_preferred_instance(self, preferred_id: Optional[str] = None) -> Optional[MinecraftInstance]:
        """
        Resolves the preferred instance:
        1. Matching preferred_id / last_selected_instance_id
        2. Most recently played instance
        3. First instance available
        """
        if preferred_id and preferred_id in self._instances:
            return self._instances[preferred_id]

        all_insts = list(self._instances.values())
        if not all_insts:
            return None

        # Sort by last_played timestamp descending
        played = [i for i in all_insts if i.last_played]
        if played:
            played.sort(key=lambda x: x.last_played or "", reverse=True)
            return played[0]

        return all_insts[0]

    def create(
        self,
        name: str,
        minecraft_version: str,
        loader: str = "vanilla",
        loader_version: str = "latest",
        min_ram_mb: int = 1024,
        max_ram_mb: int = 4096,
        jvm_args: str = "",
        custom_id: Optional[str] = None,
    ) -> MinecraftInstance:
        """Creates a new instance with standard directories."""
        slug = re.sub(r"[^a-zA-Z0-9_\-]", "_", name.lower().strip())
        inst_id = custom_id or f"{slug}_{uuid.uuid4().hex[:6]}"
        inst_dir = self.root_dir / inst_id
        inst_dir.mkdir(parents=True, exist_ok=True)

        # Standard Minecraft directories
        (inst_dir / "mods").mkdir(parents=True, exist_ok=True)
        (inst_dir / "saves").mkdir(parents=True, exist_ok=True)
        (inst_dir / "resourcepacks").mkdir(parents=True, exist_ok=True)
        (inst_dir / "shaderpacks").mkdir(parents=True, exist_ok=True)
        (inst_dir / "config").mkdir(parents=True, exist_ok=True)
        (inst_dir / "logs").mkdir(parents=True, exist_ok=True)
        (inst_dir / "screenshots").mkdir(parents=True, exist_ok=True)

        inst = MinecraftInstance(
            id=inst_id,
            name=name,
            minecraft_version=minecraft_version,
            loader=loader.lower(),
            loader_version=loader_version,
            min_ram_mb=min_ram_mb,
            max_ram_mb=max_ram_mb,
            jvm_args=jvm_args,
            instance_dir=str(inst_dir),
        )

        self.save(inst)
        self._instances[inst.id] = inst
        logger.info(f"Created new instance '{name}' (ID: {inst.id})")
        return inst

    def save(self, instance: MinecraftInstance) -> None:
        """Persists the instance metadata to instance.json."""
        inst_dir = instance.get_dir(self.root_dir)
        inst_dir.mkdir(parents=True, exist_ok=True)
        meta_file = inst_dir / "instance.json"
        with open(meta_file, "w", encoding="utf-8") as f:
            json.dump(instance.to_dict(), f, indent=2)

    def rename(self, instance_id: str, new_name: str) -> bool:
        inst = self.get(instance_id)
        if not inst:
            return False
        inst.name = new_name
        self.save(inst)
        return True

    def duplicate(self, instance_id: str, new_name: str) -> Optional[MinecraftInstance]:
        """Clones an entire instance folder to a new instance."""
        source = self.get(instance_id)
        if not source:
            return None

        source_dir = source.get_dir(self.root_dir)
        new_inst = self.create(
            name=new_name,
            minecraft_version=source.minecraft_version,
            loader=source.loader,
            loader_version=source.loader_version,
            min_ram_mb=source.min_ram_mb,
            max_ram_mb=source.max_ram_mb,
            jvm_args=source.jvm_args,
        )
        dest_dir = new_inst.get_dir(self.root_dir)

        # Copy mods, configs, resourcepacks, shaderpacks (omit saves/logs/screenshots to keep it clean)
        for folder_name in ["mods", "config", "resourcepacks", "shaderpacks"]:
            src_sub = source_dir / folder_name
            if src_sub.exists():
                dst_sub = dest_dir / folder_name
                if dst_sub.exists():
                    shutil.rmtree(dst_sub)
                shutil.copytree(src_sub, dst_sub)

        return new_inst

    def delete(self, instance_id: str) -> bool:
        """Completely removes an instance and its directory."""
        inst = self.get(instance_id)
        if not inst:
            return False

        inst_dir = inst.get_dir(self.root_dir)
        try:
            # Check safety
            ensure_safe_path(self.root_dir, inst_dir)
            if inst_dir.exists():
                shutil.rmtree(inst_dir)
            self._instances.pop(instance_id, None)
            logger.info(f"Deleted instance {instance_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete instance {instance_id}: {e}")
            return False

    def export_instance_zip(self, instance_id: str, target_zip_path: Path) -> Path:
        """Exports the instance configuration, mods, and resourcepacks to a zip file."""
        inst = self.get(instance_id)
        if not inst:
            raise ValueError(f"Instance {instance_id} not found")

        inst_dir = inst.get_dir(self.root_dir)
        target_zip = Path(target_zip_path)
        target_zip.parent.mkdir(parents=True, exist_ok=True)

        shutil.make_archive(
            base_name=str(target_zip.with_suffix("")),
            format="zip",
            root_dir=str(inst_dir),
        )
        return target_zip
