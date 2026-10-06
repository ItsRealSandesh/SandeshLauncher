"""
Launcher settings management for SandeshLauncher.
Loads and saves persistent user preferences to settings.json.
"""

import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, Any, Optional

from config import (
    DEFAULT_MIN_RAM_MB,
    DEFAULT_MAX_RAM_MB,
    DEFAULT_JVM_ARGS,
    DEFAULT_MAX_CONCURRENT_DOWNLOADS,
    THEME_MODE,
)
from utils.logging import get_logger
from utils.paths import get_settings_file, get_instances_dir

logger = get_logger("settings")


@dataclass
class LauncherSettings:
    # General / Launch
    launch_directory: str = ""
    default_instance_id: str = ""
    last_selected_instance_id: str = ""
    close_on_launch: str = "minimize"  # "keep_open", "minimize", "close"
    
    # Minecraft & Versions
    enable_snapshots: bool = False
    enable_old_releases: bool = False
    
    # Java & Memory
    java_management: str = "auto"  # "auto", "manual"
    custom_java_path: str = ""
    default_min_ram_mb: int = DEFAULT_MIN_RAM_MB
    default_max_ram_mb: int = DEFAULT_MAX_RAM_MB
    custom_jvm_args: str = DEFAULT_JVM_ARGS
    # Window & Display
    window_mode: str = "maximized"  # "maximized", "fit_desktop", "windowed"
    match_desktop_resolution: bool = True
    resolution_width: int = 0
    resolution_height: int = 0
    fullscreen: bool = False
    fast_launch_optimization: bool = True
    mesa_glthread: bool = True

    # Downloads & Network
    concurrent_downloads: int = DEFAULT_MAX_CONCURRENT_DOWNLOADS
    check_launcher_updates: bool = True
    
    # Appearance & Accounts
    theme: str = THEME_MODE
    active_account_id: str = ""
    first_run_completed: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LauncherSettings":
        valid_keys = cls.__dataclass_fields__.keys()
        filtered = {k: v for k, v in data.items() if k in valid_keys}
        return cls(**filtered)


class SettingsManager:
    _instance: Optional["SettingsManager"] = None

    def __init__(self, filepath: Optional[Path] = None):
        self.file_path = filepath or get_settings_file()
        self.settings = LauncherSettings()
        self.load()

    @classmethod
    def get_instance(cls) -> "SettingsManager":
        if cls._instance is None:
            cls._instance = SettingsManager()
        return cls._instance

    def load(self) -> LauncherSettings:
        if self.file_path.exists():
            try:
                with open(self.file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.settings = LauncherSettings.from_dict(data)
            except Exception as e:
                logger.warning(f"Could not load settings file {self.file_path}: {e}")
                self.settings = LauncherSettings()
        else:
            self.settings = LauncherSettings()
            self.settings.launch_directory = str(get_instances_dir())
            self.save()
        return self.settings

    def save(self) -> None:
        try:
            self.file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump(self.settings.to_dict(), f, indent=2)
            logger.info("Settings saved successfully.")
        except Exception as e:
            logger.error(f"Failed to save settings: {e}")

    def update(self, **kwargs) -> None:
        for k, v in kwargs.items():
            if hasattr(self.settings, k):
                setattr(self.settings, k, v)
        self.save()
