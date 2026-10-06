"""
Downloads Page for SandeshLauncher.
Displays active download tasks, real-time speed, progress bars, and cancellation.
"""

from typing import List

import customtkinter as ctk

from config import (
    ACCENT_COLOR,
    SURFACE_COLOR,
    SURFACE_LIGHT_COLOR,
    TEXT_COLOR,
    TEXT_MUTED_COLOR,
)
from downloads.manager import DownloadManager
from downloads.worker import DownloadTask, DownloadStatus


class DownloadsPage(ctk.CTkFrame):
    def __init__(self, parent: ctk.CTkBaseClass, download_manager: DownloadManager):
        super().__init__(parent, fg_color="transparent")
        self.download_manager = download_manager
        self.download_manager.add_listener(self._on_tasks_updated)

        self._build_ui()
        self.refresh_tasks()

    def _build_ui(self) -> None:
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=30, pady=(24, 16))

        title = ctk.CTkLabel(
            header,
            text="Download Manager",
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color=TEXT_COLOR
        )
        title.pack(side="left")

        self.scroll_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll_frame.pack(fill="both", expand=True, padx=30, pady=(0, 24))

    def _on_tasks_updated(self) -> None:
        self.after(0, self.refresh_tasks)

    def refresh_tasks(self) -> None:
        for widget in self.scroll_frame.winfo_children():
            widget.destroy()

        tasks = self.download_manager.get_all_tasks()

        if not tasks:
            empty = ctk.CTkFrame(self.scroll_frame, fg_color=SURFACE_COLOR, corner_radius=12)
            empty.pack(fill="x", pady=20, padx=10, ipady=30)
            ctk.CTkLabel(
                empty,
                text="No active downloads.",
                font=ctk.CTkFont(size=14),
                text_color=TEXT_MUTED_COLOR,
                justify="center"
            ).pack()
            return

        for t in reversed(tasks):
            self._render_task_card(t)

    def _render_task_card(self, task: DownloadTask) -> None:
        card = ctk.CTkFrame(
            self.scroll_frame,
            fg_color=SURFACE_COLOR,
            border_width=1,
            border_color="#334155",
            corner_radius=12
        )
        card.pack(fill="x", pady=5, padx=8, ipady=8)

        # Row 1: Name and Status
        row1 = ctk.CTkFrame(card, fg_color="transparent")
        row1.pack(fill="x", padx=16, pady=(6, 4))

        name_lbl = ctk.CTkLabel(
            row1,
            text=task.name,
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=TEXT_COLOR
        )
        name_lbl.pack(side="left")

        status_color = "#34d399" if task.status == DownloadStatus.COMPLETED else "#38bdf8" if task.status == DownloadStatus.DOWNLOADING else "#f87171" if task.status == DownloadStatus.FAILED else "#94a3b8"
        status_lbl = ctk.CTkLabel(
            row1,
            text=task.status.value,
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=status_color
        )
        status_lbl.pack(side="right")

        # Row 2: Progress Bar
        bar = ctk.CTkProgressBar(card, height=8, progress_color=ACCENT_COLOR)
        pct = task.progress_percentage / 100.0 if task.total_bytes > 0 else 0.0
        bar.set(pct)
        bar.pack(fill="x", padx=16, pady=4)

        # Row 3: Metrics & Cancel
        row3 = ctk.CTkFrame(card, fg_color="transparent")
        row3.pack(fill="x", padx=16, pady=(2, 6))

        dl_mb = task.downloaded_bytes / (1024 * 1024)
        tot_mb = task.total_bytes / (1024 * 1024) if task.total_bytes > 0 else 0
        metric_str = f"{dl_mb:.1f} MB / {tot_mb:.1f} MB  •  {task.speed_text}" if task.status == DownloadStatus.DOWNLOADING else f"{dl_mb:.1f} MB"
        metrics_lbl = ctk.CTkLabel(
            row3,
            text=metric_str,
            font=ctk.CTkFont(size=11),
            text_color=TEXT_MUTED_COLOR
        )
        metrics_lbl.pack(side="left")

        if task.status in (DownloadStatus.PENDING, DownloadStatus.DOWNLOADING):
            cancel_btn = ctk.CTkButton(
                row3,
                text="Cancel",
                width=60,
                height=24,
                fg_color="#334155",
                hover_color="#ef4444",
                text_color=TEXT_COLOR,
                font=ctk.CTkFont(size=11),
                command=lambda t_id=task.id: self.download_manager.cancel_task(t_id)
            )
            cancel_btn.pack(side="right")
