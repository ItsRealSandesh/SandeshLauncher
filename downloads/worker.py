"""
Download task and worker thread definition for SandeshLauncher.
Tracks download state, progress percentages, speed metrics, and cancellation.
"""

import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Callable, Optional

from utils.logging import get_logger
from utils.network import download_file_with_progress

logger = get_logger("download_worker")


class DownloadStatus(Enum):
    PENDING = "Pending"
    DOWNLOADING = "Downloading"
    COMPLETED = "Completed"
    FAILED = "Failed"
    CANCELLED = "Cancelled"


@dataclass
class DownloadTask:
    id: str
    name: str
    url: str
    destination: Path
    status: DownloadStatus = DownloadStatus.PENDING
    downloaded_bytes: int = 0
    total_bytes: int = 0
    speed_text: str = ""
    error_message: Optional[str] = None
    sha512: Optional[str] = None
    sha1: Optional[str] = None
    on_complete: Optional[Callable[[], None]] = None
    on_error: Optional[Callable[[Exception], None]] = None
    _cancelled: bool = False

    @property
    def progress_percentage(self) -> float:
        if self.total_bytes <= 0:
            return 0.0
        return min(100.0, (self.downloaded_bytes / self.total_bytes) * 100.0)

    def cancel(self) -> None:
        self._cancelled = True
        self.status = DownloadStatus.CANCELLED

    def is_cancelled(self) -> bool:
        return self._cancelled

    def execute(self) -> bool:
        """Executes the file download with progress updates."""
        if self._cancelled:
            return False

        self.status = DownloadStatus.DOWNLOADING
        start_time = time.time()

        def _prog(cur: int, tot: int, sp: str) -> None:
            self.downloaded_bytes = cur
            self.total_bytes = tot
            self.speed_text = sp

        try:
            download_file_with_progress(
                url=self.url,
                destination=self.destination,
                expected_sha512=self.sha512,
                expected_sha1=self.sha1,
                progress_callback=_prog,
                cancel_flag=self.is_cancelled
            )
            self.status = DownloadStatus.COMPLETED
            if self.on_complete:
                self.on_complete()
            return True
        except InterruptedError:
            self.status = DownloadStatus.CANCELLED
            return False
        except Exception as e:
            self.status = DownloadStatus.FAILED
            self.error_message = str(e)
            logger.error(f"Download task '{self.name}' failed: {e}")
            if self.on_error:
                self.on_error(e)
            return False
