"""
Minecraft Process Launcher and Execution Engine for SandeshLauncher.
Builds JVM options, executes subprocess, captures output asynchronously,
and monitors game lifecycle with token redaction.
"""

import os
import shlex
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Callable, List, Optional

import minecraft_launcher_lib as mll

from auth.token_store import Account
from config import APP_NAME, APP_VERSION
from instances.model import MinecraftInstance
from java.manager import JavaManager
from minecraft.installer import prepare_instance_environment
from utils.logging import get_logger, log_minecraft_output
from utils.paths import get_shared_minecraft_dir, get_instances_dir

logger = get_logger("launcher")


class MinecraftLauncher:
    def __init__(self, java_manager: Optional[JavaManager] = None):
        self.java_manager = java_manager or JavaManager()
        self.active_process: Optional[subprocess.Popen] = None
        self.is_running: bool = False
        self.launch_start_time: Optional[float] = None

    def launch(
        self,
        instance: MinecraftInstance,
        account: Account,
        status_callback: Optional[Callable[[str], None]] = None,
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
        on_start: Optional[Callable[[], None]] = None,
        on_exit: Optional[Callable[[int], None]] = None,
    ) -> subprocess.Popen:
        """
        Executes full launch sequence:
        1. Validate account & instance
        2. Resolve Java
        3. Install / prepare game files & loader
        4. Assemble launch arguments
        5. Spawn subprocess & monitor in background
        """
        if self.is_running:
            raise RuntimeError("A Minecraft instance is already running!")

        logger.info(f"Initiating launch for '{instance.name}' with player '{account.username}'")

        # 1. Resolve Java
        if status_callback:
            status_callback("Checking Java runtime...")

        java_path, java_err = self.java_manager.resolve_java_for_instance(
            instance,
            progress_callback=progress_callback,
            status_callback=status_callback
        )
        if not java_path:
            raise RuntimeError(java_err or "Incompatible or missing Java runtime.")
        if java_err:
            logger.warning(java_err)

        # 2. Prepare Game & Loader
        if status_callback:
            status_callback("Checking Minecraft files and loader...")

        launch_version_id = prepare_instance_environment(
            instance=instance,
            progress_callback=progress_callback,
            java_path=java_path
        )

        # 3. Assemble JVM & Launch Options
        if status_callback:
            status_callback("Assembling launch command...")

        shared_mc_dir = get_shared_minecraft_dir()
        game_dir = instance.get_game_dir(get_instances_dir())

        from utils.screen import get_desktop_resolution
        from utils.settings import SettingsManager
        settings = SettingsManager.get_instance().settings
        desk_w, desk_h = get_desktop_resolution()

        # Resolve screen resolution: automatically match desktop size
        res_w = instance.resolution_width
        res_h = instance.resolution_height
        if not res_w or not res_h or (res_w == 854 and res_h == 480) or settings.match_desktop_resolution:
            res_w = desk_w
            res_h = desk_h

        jvm_args = [
            f"-Xmx{instance.max_ram_mb}M",
            f"-Xms{instance.min_ram_mb}M",
        ]
        if instance.jvm_args:
            jvm_args.extend(shlex.split(instance.jvm_args))

        options = {
            "username": account.username,
            "uuid": account.uuid,
            "token": account.access_token if account.account_type == "microsoft" else "offline_token",
            "executablePath": java_path,
            "jvmArguments": jvm_args,
            "launcherName": APP_NAME,
            "launcherVersion": APP_VERSION,
            "gameDirectory": str(game_dir),
            "customResolution": True,
            "resolutionWidth": str(res_w),
            "resolutionHeight": str(res_h),
            "demo": False,
        }

        command = mll.command.get_minecraft_command(
            version=launch_version_id,
            minecraft_directory=str(shared_mc_dir),
            options=options
        )

        # Fullscreen handling
        if instance.fullscreen or settings.fullscreen:
            if "--fullscreen" not in command:
                command.append("--fullscreen")

        # Filter out flags incompatible with installed Java runtime
        from java.detector import parse_java_version
        java_info = parse_java_version(java_path)
        java_major = java_info.major_version if java_info else 21

        # --sun-misc-unsafe-memory-access was added in Java 24; Java 21 and older fail with 'Unrecognized option'
        if java_major < 24:
            command = [arg for arg in command if not arg.startswith("--sun-misc-unsafe-memory-access")]

        logger.info(f"Starting Minecraft for version {launch_version_id} (Resolution: {res_w}x{res_h}, Fullscreen: {instance.fullscreen or settings.fullscreen})...")
        if status_callback:
            status_callback("Starting Minecraft...")

        # 4. Prepare Environment & Execute Subprocess
        env = os.environ.copy()
        if settings.mesa_glthread:
            env["mesa_glthread"] = "true"
        if "DRI_PRIME" not in env:
            env["DRI_PRIME"] = "1"

        self.launch_start_time = time.time()
        self.active_process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=subprocess.PIPE,
            text=True,
            bufsize=1,
            cwd=str(game_dir),
            env=env,
            universal_newlines=True
        )
        self.is_running = True

        if on_start:
            on_start()

        # Update last played on instance
        instance.last_played = datetime.now().isoformat()

        # 5. Background Output Monitor
        def monitor_process() -> None:
            try:
                assert self.active_process is not None
                for line in iter(self.active_process.stdout.readline, ""):
                    if not line:
                        break
                    log_minecraft_output(line)

                return_code = self.active_process.wait()
                duration = int(time.time() - (self.launch_start_time or time.time()))
                instance.playtime_seconds += duration

                logger.info(f"Minecraft process exited with code {return_code} (played {duration}s)")
            except Exception as e:
                logger.error(f"Error while monitoring Minecraft process: {e}")
                return_code = -1
            finally:
                self.is_running = False
                self.active_process = None
                if on_exit:
                    on_exit(return_code)

        monitor_thread = threading.Thread(target=monitor_process, daemon=True)
        monitor_thread.start()

        return self.active_process

    def terminate(self) -> None:
        """Gracefully asks Minecraft to close or terminates if stuck."""
        if self.active_process and self.is_running:
            logger.info("Terminating running Minecraft process...")
            self.active_process.terminate()
            try:
                self.active_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.active_process.kill()
            self.is_running = False
            self.active_process = None
