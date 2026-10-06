"""
Logs & Console Page for SandeshLauncher.
Displays live launcher logs and running Minecraft game output,
with one-click clipboard copying, diagnostics export, and token redaction.
"""

import os
import subprocess
import sys
import tkinter as tk
from tkinter import filedialog, messagebox

import customtkinter as ctk

from config import (
    ACCENT_COLOR,
    ACCENT_HOVER_COLOR,
    SURFACE_COLOR,
    SURFACE_LIGHT_COLOR,
    TEXT_COLOR,
    TEXT_MUTED_COLOR,
)
from utils.logging import (
    ui_log_buffer,
    minecraft_log_buffer,
    export_diagnostics,
    get_logs_dir,
)


class LogsPage(ctk.CTkFrame):
    def __init__(self, parent: ctk.CTkBaseClass):
        super().__init__(parent, fg_color="transparent")
        self.current_tab = "launcher"  # "launcher" or "minecraft"
        self._build_ui()

        # Connect live log listeners
        ui_log_buffer.set_listener(self._on_launcher_log_line)
        minecraft_log_buffer.set_listener(self._on_minecraft_log_line)

        # Load initial backlog
        self._reload_text()

    def _build_ui(self) -> None:
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=30, pady=(20, 10))

        title = ctk.CTkLabel(
            header,
            text="Logs & Diagnostics",
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color=TEXT_COLOR
        )
        title.pack(side="left")

        # Action Buttons
        btn_box = ctk.CTkFrame(header, fg_color="transparent")
        btn_box.pack(side="right")

        self.copy_btn = ctk.CTkButton(
            btn_box,
            text="Copy Logs",
            width=90,
            height=34,
            fg_color=SURFACE_COLOR,
            hover_color=SURFACE_LIGHT_COLOR,
            border_width=1,
            border_color="#475569",
            command=self._copy_to_clipboard
        )
        self.copy_btn.pack(side="left", padx=4)

        self.export_btn = ctk.CTkButton(
            btn_box,
            text="Export Diagnostics",
            width=130,
            height=34,
            fg_color=SURFACE_COLOR,
            hover_color=SURFACE_LIGHT_COLOR,
            border_width=1,
            border_color="#475569",
            command=self._export_diagnostics
        )
        self.export_btn.pack(side="left", padx=4)

        self.folder_btn = ctk.CTkButton(
            btn_box,
            text="📂 Open Logs",
            width=100,
            height=34,
            fg_color=SURFACE_COLOR,
            hover_color=SURFACE_LIGHT_COLOR,
            border_width=1,
            border_color="#475569",
            command=self._open_logs_dir
        )
        self.folder_btn.pack(side="left", padx=4)

        # Tabs & Auto-Scroll
        nav_row = ctk.CTkFrame(self, fg_color="transparent")
        nav_row.pack(fill="x", padx=30, pady=(0, 10))

        self.tab_selector = ctk.CTkSegmentedButton(
            nav_row,
            values=["Launcher Logs", "Minecraft Game Output"],
            selected_color=ACCENT_COLOR,
            selected_hover_color=ACCENT_HOVER_COLOR,
            unselected_color=SURFACE_COLOR,
            unselected_hover_color=SURFACE_LIGHT_COLOR,
            text_color=TEXT_COLOR,
            height=32,
            command=self._on_tab_changed
        )
        self.tab_selector.set("Launcher Logs")
        self.tab_selector.pack(side="left")

        self.autoscroll_var = ctk.BooleanVar(value=True)
        self.autoscroll_cb = ctk.CTkCheckBox(
            nav_row,
            text="Auto-scroll",
            variable=self.autoscroll_var,
            font=ctk.CTkFont(size=12),
            text_color=TEXT_MUTED_COLOR
        )
        self.autoscroll_cb.pack(side="right")

        # Log Text Box
        self.text_box = ctk.CTkTextbox(
            self,
            fg_color="#090d16",
            text_color="#e2e8f0",
            font=ctk.CTkFont(family="monospace", size=11),
            corner_radius=10,
            wrap="none"
        )
        self.text_box.pack(fill="both", expand=True, padx=30, pady=(0, 24))

    def _on_tab_changed(self, choice: str) -> None:
        self.current_tab = "launcher" if choice == "Launcher Logs" else "minecraft"
        self._reload_text()

    def _reload_text(self) -> None:
        lines = ui_log_buffer.get_all() if self.current_tab == "launcher" else minecraft_log_buffer.get_all()
        self.text_box.delete("1.0", "end")
        self.text_box.insert("end", "\n".join(lines) + ("\n" if lines else ""))
        if self.autoscroll_var.get():
            self.text_box.see("end")

    def _on_launcher_log_line(self, line: str) -> None:
        if self.current_tab == "launcher":
            self._queue_line(line)

    def _on_minecraft_log_line(self, line: str) -> None:
        if self.current_tab == "minecraft":
            self._queue_line(line)

    def _queue_line(self, line: str) -> None:
        if not hasattr(self, "_pending_lines"):
            self._pending_lines = []
            self._flush_scheduled = False

        self._pending_lines.append(line)
        if not self._flush_scheduled:
            self._flush_scheduled = True
            try:
                self.after(60, self._flush_pending_lines)
            except Exception:
                pass

    def _flush_pending_lines(self) -> None:
        self._flush_scheduled = False
        if not hasattr(self, "_pending_lines") or not self._pending_lines:
            return

        chunk = "\n".join(self._pending_lines) + "\n"
        self._pending_lines.clear()

        try:
            self.text_box.insert("end", chunk)
            if self.autoscroll_var.get():
                self.text_box.see("end")
        except Exception:
            pass

    def _copy_to_clipboard(self) -> None:
        content = self.text_box.get("1.0", "end")
        self.clipboard_clear()
        self.clipboard_append(content)
        messagebox.showinfo("Copied", "Logs copied to clipboard!")

    def _export_diagnostics(self) -> None:
        file_path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text file", "*.txt")],
            initialfile="sandesh_diagnostics.txt",
            title="Export Diagnostics Report"
        )
        if file_path:
            try:
                export_diagnostics(Path(file_path))
                messagebox.showinfo("Success", f"Diagnostics saved to {file_path}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to export diagnostics: {e}")

    def _open_logs_dir(self) -> None:
        logs_dir = get_logs_dir()
        try:
            if sys.platform == "win32":
                os.startfile(str(logs_dir))
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(logs_dir)])
            else:
                subprocess.Popen(["xdg-open", str(logs_dir)])
        except Exception as e:
            messagebox.showerror("Error", f"Could not open directory: {e}")
