"""
Logging subsystem for SandeshLauncher.
Features automatic token redaction, separate launcher and Minecraft logs,
rotating/in-memory buffers for GUI consumption, and diagnostic export.
"""

import logging
import sys
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Callable, List, Optional

from utils.paths import get_logs_dir
from utils.security import redact_sensitive_text


class RedactingFilter(logging.Filter):
    """Filter that automatically strips sensitive tokens from all log records."""
    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = redact_sensitive_text(record.msg)
        if record.args:
            record.args = tuple(
                redact_sensitive_text(arg) if isinstance(arg, str) else arg
                for arg in record.args
            )
        return True


class LogBufferHandler(logging.Handler):
    """Stores the latest log messages in an in-memory queue for real-time GUI display."""
    def __init__(self, max_records: int = 1000):
        super().__init__()
        self.buffer: deque[str] = deque(maxlen=max_records)
        self.listener: Optional[Callable[[str], None]] = None

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            self.buffer.append(msg)
            if self.listener:
                self.listener(msg)
        except Exception:
            self.handleError(record)

    def set_listener(self, callback: Callable[[str], None]) -> None:
        self.listener = callback

    def get_all(self) -> List[str]:
        return list(self.buffer)


# Singleton log buffer
ui_log_buffer = LogBufferHandler(max_records=2000)
minecraft_log_buffer = LogBufferHandler(max_records=5000)

_logger_initialized = False


def setup_logging() -> logging.Logger:
    """Initializes launcher root logger with console, file, and UI buffer handlers."""
    global _logger_initialized
    logger = logging.getLogger("SandeshLauncher")

    if _logger_initialized:
        return logger

    logger.setLevel(logging.INFO)
    logger.addFilter(RedactingFilter())

    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%H:%M:%S"
    )

    # Console Handler
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)
    console.addFilter(RedactingFilter())
    logger.addHandler(console)

    # UI Buffer Handler
    ui_log_buffer.setFormatter(formatter)
    ui_log_buffer.addFilter(RedactingFilter())
    logger.addHandler(ui_log_buffer)

    # File Handler
    try:
        logs_dir = get_logs_dir()
        log_file = logs_dir / f"launcher_{datetime.now().strftime('%Y-%m-%d')}.log"
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(formatter)
        file_handler.addFilter(RedactingFilter())
        logger.addHandler(file_handler)
    except Exception as e:
        print(f"Warning: Failed to initialize file logger: {e}", file=sys.stderr)

    _logger_initialized = True
    return logger


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """Returns a child logger under SandeshLauncher hierarchy."""
    if not _logger_initialized:
        setup_logging()
    if name:
        return logging.getLogger(f"SandeshLauncher.{name}")
    return logging.getLogger("SandeshLauncher")


def log_minecraft_output(line: str) -> None:
    """Logs a single raw stdout/stderr line from running Minecraft process."""
    clean_line = redact_sensitive_text(line.rstrip())
    if clean_line:
        minecraft_log_buffer.buffer.append(clean_line)
        if minecraft_log_buffer.listener:
            minecraft_log_buffer.listener(clean_line)
        
        # Also append to instance or daily game log file
        try:
            logs_dir = get_logs_dir()
            mc_log_file = logs_dir / "minecraft_latest.log"
            with open(mc_log_file, "a", encoding="utf-8") as f:
                f.write(clean_line + "\n")
        except Exception:
            pass


def export_diagnostics(output_path: Path) -> Path:
    """Creates a consolidated diagnostic report redacting all credentials."""
    import platform
    import psutil
    from config import APP_NAME, APP_VERSION

    report = []
    report.append(f"=== {APP_NAME} Diagnostics Report ===")
    report.append(f"Generated at: {datetime.now().isoformat()}")
    report.append(f"Version: {APP_VERSION}")
    report.append(f"OS: {platform.system()} {platform.release()} ({platform.machine()})")
    report.append(f"Python: {platform.python_version()}")
    try:
        vm = psutil.virtual_memory()
        report.append(f"RAM: Total={vm.total // (1024**2)}MB, Available={vm.available // (1024**2)}MB")
    except Exception:
        pass
    report.append("\n=== Launcher Recent Logs ===")
    report.extend(ui_log_buffer.get_all()[-200:])
    report.append("\n=== Minecraft Recent Logs ===")
    report.extend(minecraft_log_buffer.get_all()[-200:])

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(report))

    return output_path
