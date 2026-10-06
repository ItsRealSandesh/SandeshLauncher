#!/usr/bin/env python3
"""
SANDESHLAUNCHER
Modern, Fast & Lightweight Minecraft Java Edition Launcher.

Main application entry point.
"""

import os
import platform
import sys

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Automatic Virtual Environment Detection & Re-exec
# If user runs 'python3 launcher.py' directly, automatically use .venv (only in source/non-frozen mode)
if not getattr(sys, "frozen", False):
    if sys.platform == "win32":
        venv_python = os.path.join(PROJECT_ROOT, ".venv", "Scripts", "python.exe")
    else:
        venv_python = os.path.join(PROJECT_ROOT, ".venv", "bin", "python")

    if os.path.isfile(venv_python) and os.path.abspath(sys.executable) != os.path.abspath(venv_python):
        if not os.environ.get("SANDESH_VENV_ACTIVE"):
            os.environ["SANDESH_VENV_ACTIVE"] = "1"
            try:
                os.execv(venv_python, [venv_python] + sys.argv)
            except OSError:
                pass

from config import APP_NAME, APP_VERSION
from ui.main_window import MainWindow
from utils.logging import setup_logging, get_logger

logger = setup_logging()


def main() -> None:
    logger.info(f"Starting {APP_NAME} v{APP_VERSION}...")
    logger.info(f"Platform: {platform.system()} {platform.release()} ({platform.machine()})")
    logger.info(f"Python: {platform.python_version()} at {sys.executable}")

    try:
        app = MainWindow()
        app.mainloop()
    except KeyboardInterrupt:
        logger.info("Application interrupted by user.")
    except Exception as e:
        logger.critical(f"Unhandled application exception: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
