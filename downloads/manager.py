"""
Asynchronous Download Manager for SandeshLauncher.
Orchestrates concurrent worker threads, maintains queue of downloads,
and notifies listeners of status updates.
"""

import queue
import threading
from typing import Callable, Dict, List, Optional

from downloads.worker import DownloadTask, DownloadStatus
from utils.logging import get_logger

logger = get_logger("download_manager")


class DownloadManager:
    _instance: Optional["DownloadManager"] = None

    def __init__(self, max_concurrent: int = 4):
        self.max_concurrent = max_concurrent
        self.task_queue: queue.Queue[DownloadTask] = queue.Queue()
        self.all_tasks: Dict[str, DownloadTask] = {}
        self.active_workers: List[threading.Thread] = []
        self._running = True
        self.listeners: List[Callable[[], None]] = []
        self._start_workers()

    @classmethod
    def get_instance(cls) -> "DownloadManager":
        if cls._instance is None:
            cls._instance = DownloadManager()
        return cls._instance

    def _start_workers(self) -> None:
        for i in range(self.max_concurrent):
            t = threading.Thread(target=self._worker_loop, daemon=True, name=f"Downloader-{i+1}")
            t.start()
            self.active_workers.append(t)

    def _worker_loop(self) -> None:
        while self._running:
            try:
                task = self.task_queue.get(timeout=1.0)
            except queue.Empty:
                continue

            if task.is_cancelled():
                self.task_queue.task_done()
                self._notify_listeners()
                continue

            task.execute()
            self.task_queue.task_done()
            self._notify_listeners()

    def add_task(self, task: DownloadTask) -> None:
        self.all_tasks[task.id] = task
        self.task_queue.put(task)
        self._notify_listeners()
        logger.info(f"Queued download: {task.name} ({task.url})")

    def cancel_task(self, task_id: str) -> None:
        task = self.all_tasks.get(task_id)
        if task:
            task.cancel()
            self._notify_listeners()

    def get_all_tasks(self) -> List[DownloadTask]:
        return list(self.all_tasks.values())

    def get_active_tasks(self) -> List[DownloadTask]:
        return [
            t for t in self.all_tasks.values()
            if t.status in (DownloadStatus.PENDING, DownloadStatus.DOWNLOADING)
        ]

    def add_listener(self, callback: Callable[[], None]) -> None:
        self.listeners.append(callback)

    def _notify_listeners(self) -> None:
        for cb in self.listeners:
            try:
                cb()
            except Exception:
                pass
