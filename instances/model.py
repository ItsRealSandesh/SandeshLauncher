"""
Instance data model for SandeshLauncher.
Defines instance properties, directory structures, and serialization.
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

from config import (
    DEFAULT_MIN_RAM_MB,
    DEFAULT_MAX_RAM_MB,
    DEFAULT_JVM_ARGS,
    DEFAULT_RESOLUTION_WIDTH,
    DEFAULT_RESOLUTION_HEIGHT,
)


@dataclass
class MinecraftInstance:
    id: str
    name: str
    minecraft_version: str
    loader: str = "vanilla"  # vanilla, fabric, forge, neoforge, quilt
    loader_version: str = "latest"
    java_path: str = "auto"
    min_ram_mb: int = DEFAULT_MIN_RAM_MB
    max_ram_mb: int = DEFAULT_MAX_RAM_MB
    jvm_args: str = DEFAULT_JVM_ARGS
    resolution_width: int = DEFAULT_RESOLUTION_WIDTH
    resolution_height: int = DEFAULT_RESOLUTION_HEIGHT
    fullscreen: bool = False
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    last_played: Optional[str] = None
    playtime_seconds: int = 0
    icon_name: str = "grass_block"
    instance_dir: Optional[str] = None  # Absolute path to instance folder

    def get_dir(self, root_instances_dir: Path) -> Path:
        """Returns the instance root directory."""
        if self.instance_dir:
            return Path(self.instance_dir)
        return root_instances_dir / self.id

    def get_game_dir(self, root_instances_dir: Path) -> Path:
        """
        Returns the game directory where instance-specific data
        (mods, saves, config, etc.) resides.
        """
        return self.get_dir(root_instances_dir)

    def get_mods_dir(self, root_instances_dir: Path) -> Path:
        mods_path = self.get_game_dir(root_instances_dir) / "mods"
        mods_path.mkdir(parents=True, exist_ok=True)
        return mods_path

    def get_resourcepacks_dir(self, root_instances_dir: Path) -> Path:
        rp_path = self.get_game_dir(root_instances_dir) / "resourcepacks"
        rp_path.mkdir(parents=True, exist_ok=True)
        return rp_path

    def get_shaderpacks_dir(self, root_instances_dir: Path) -> Path:
        sp_path = self.get_game_dir(root_instances_dir) / "shaderpacks"
        sp_path.mkdir(parents=True, exist_ok=True)
        return sp_path

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MinecraftInstance":
        valid_keys = cls.__dataclass_fields__.keys()
        filtered = {k: v for k, v in data.items() if k in valid_keys}
        return cls(**filtered)
