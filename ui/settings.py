"""
Settings Page for SandeshLauncher.
Allows customization of Java runtimes, RAM allocation, JVM flags,
directory paths, snapshot toggles, and update checks.
"""

import threading
from tkinter import filedialog, messagebox
from typing import Callable, Optional

import customtkinter as ctk
import psutil

from config import (
    ACCENT_COLOR,
    ACCENT_HOVER_COLOR,
    APP_NAME,
    APP_VERSION,
    DISCLAIMER,
    SURFACE_COLOR,
    SURFACE_LIGHT_COLOR,
    TEXT_COLOR,
    TEXT_MUTED_COLOR,
)
from java.detector import parse_java_version
from java.manager import JavaManager
from updater.github import check_for_updates
from utils.screen import get_desktop_resolution
from utils.settings import SettingsManager


class SettingsPage(ctk.CTkFrame):
    def __init__(
        self,
        parent: ctk.CTkBaseClass,
        java_manager: JavaManager,
        on_window_mode_change: Optional[Callable[[str], None]] = None,
    ):
        super().__init__(parent, fg_color="transparent")
        self.java_manager = java_manager
        self.on_window_mode_change = on_window_mode_change
        self.settings_mgr = SettingsManager.get_instance()
        self.settings = self.settings_mgr.settings

        self._build_ui()

    def _build_ui(self) -> None:
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=30, pady=(24, 16))

        title = ctk.CTkLabel(
            header,
            text="Launcher Settings",
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color=TEXT_COLOR
        )
        title.pack(side="left")

        # Scrollable container
        self.scroll_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll_frame.pack(fill="both", expand=True, padx=30, pady=(0, 24))

        self._build_general_section()
        self._build_display_section()
        self._build_java_section()
        self._build_memory_section()
        self._build_about_section()

    def _create_section(self, title: str) -> ctk.CTkFrame:
        sec = ctk.CTkFrame(self.scroll_frame, fg_color=SURFACE_COLOR, corner_radius=12)
        sec.pack(fill="x", pady=8, padx=4, ipady=12)

        lbl = ctk.CTkLabel(
            sec,
            text=title,
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=TEXT_COLOR
        )
        lbl.pack(anchor="w", padx=20, pady=(12, 10))
        return sec

    def _build_general_section(self) -> None:
        sec = self._create_section("General & Launch Behavior")

        # Close on launch
        row1 = ctk.CTkFrame(sec, fg_color="transparent")
        row1.pack(fill="x", padx=20, pady=6)

        ctk.CTkLabel(row1, text="When Minecraft launches:", font=ctk.CTkFont(size=13)).pack(side="left")
        self.close_behavior = ctk.CTkComboBox(
            row1,
            values=["Minimize Launcher", "Keep Launcher Open", "Close Launcher"],
            width=180,
            command=self._on_close_behavior_change
        )
        current = {"minimize": "Minimize Launcher", "keep_open": "Keep Launcher Open", "close": "Close Launcher"}.get(self.settings.close_on_launch, "Minimize Launcher")
        self.close_behavior.set(current)
        self.close_behavior.pack(side="right")

        # Snapshots Toggle
        row2 = ctk.CTkFrame(sec, fg_color="transparent")
        row2.pack(fill="x", padx=20, pady=6)

        ctk.CTkLabel(row2, text="Show Snapshot versions in version lists:", font=ctk.CTkFont(size=13)).pack(side="left")
        self.snapshot_var = ctk.BooleanVar(value=self.settings.enable_snapshots)
        snap_switch = ctk.CTkSwitch(
            row2,
            text="",
            variable=self.snapshot_var,
            command=lambda: self.settings_mgr.update(enable_snapshots=self.snapshot_var.get())
        )
        snap_switch.pack(side="right")

    def _on_close_behavior_change(self, choice: str) -> None:
        val = "minimize" if "Minimize" in choice else "close" if "Close" in choice else "keep_open"
        self.settings_mgr.update(close_on_launch=val)

    def _build_display_section(self) -> None:
        sec = self._create_section("Display & Launch Performance")

        desk_w, desk_h = get_desktop_resolution()

        # Launcher Window Mode
        row_win = ctk.CTkFrame(sec, fg_color="transparent")
        row_win.pack(fill="x", padx=20, pady=6)

        ctk.CTkLabel(row_win, text="Launcher Window Mode:", font=ctk.CTkFont(size=13)).pack(side="left")
        self.win_mode_combo = ctk.CTkComboBox(
            row_win,
            values=["Maximized (Full Desktop)", "Standard Windowed"],
            width=220,
            command=self._on_window_mode_change
        )
        current_mode = "Maximized (Full Desktop)" if self.settings.window_mode != "windowed" else "Standard Windowed"
        self.win_mode_combo.set(current_mode)
        self.win_mode_combo.pack(side="right")

        # Auto match desktop resolution for Minecraft
        row_res = ctk.CTkFrame(sec, fg_color="transparent")
        row_res.pack(fill="x", padx=20, pady=6)

        res_box = ctk.CTkFrame(row_res, fg_color="transparent")
        res_box.pack(side="left")
        ctk.CTkLabel(res_box, text="Match Game to Desktop Resolution:", font=ctk.CTkFont(size=13)).pack(anchor="w")
        ctk.CTkLabel(res_box, text=f"Detected Desktop: {desk_w} x {desk_h} pixels", font=ctk.CTkFont(size=11), text_color=ACCENT_COLOR).pack(anchor="w")

        self.match_res_var = ctk.BooleanVar(value=self.settings.match_desktop_resolution)
        match_switch = ctk.CTkSwitch(
            row_res,
            text="",
            variable=self.match_res_var,
            command=lambda: self.settings_mgr.update(match_desktop_resolution=self.match_res_var.get())
        )
        match_switch.pack(side="right")

        # Fullscreen Mode
        row_fs = ctk.CTkFrame(sec, fg_color="transparent")
        row_fs.pack(fill="x", padx=20, pady=6)

        ctk.CTkLabel(row_fs, text="Launch Minecraft in Fullscreen:", font=ctk.CTkFont(size=13)).pack(side="left")
        self.fs_var = ctk.BooleanVar(value=self.settings.fullscreen)
        fs_switch = ctk.CTkSwitch(
            row_fs,
            text="",
            variable=self.fs_var,
            command=lambda: self.settings_mgr.update(fullscreen=self.fs_var.get())
        )
        fs_switch.pack(side="right")

        # Fast Launch & Micro-Stutter Optimization
        row_opt = ctk.CTkFrame(sec, fg_color="transparent")
        row_opt.pack(fill="x", padx=20, pady=6)

        opt_box = ctk.CTkFrame(row_opt, fg_color="transparent")
        opt_box.pack(side="left")
        ctk.CTkLabel(opt_box, text="High-Performance Low-Latency Profile:", font=ctk.CTkFont(size=13)).pack(anchor="w")
        ctk.CTkLabel(opt_box, text="Tuned G1GC, parallel thread ref-proc, IPv4 fast stack, string deduplication", font=ctk.CTkFont(size=11), text_color=TEXT_MUTED_COLOR).pack(anchor="w")

        self.opt_var = ctk.BooleanVar(value=self.settings.fast_launch_optimization)
        opt_switch = ctk.CTkSwitch(
            row_opt,
            text="",
            variable=self.opt_var,
            command=lambda: self.settings_mgr.update(fast_launch_optimization=self.opt_var.get())
        )
        opt_switch.pack(side="right")

        # Mesa Multi-Threaded OpenGL (Linux)
        row_mesa = ctk.CTkFrame(sec, fg_color="transparent")
        row_mesa.pack(fill="x", padx=20, pady=6)

        mesa_box = ctk.CTkFrame(row_mesa, fg_color="transparent")
        mesa_box.pack(side="left")
        ctk.CTkLabel(mesa_box, text="Multi-Threaded OpenGL Rendering (mesa_glthread):", font=ctk.CTkFont(size=13)).pack(anchor="w")
        ctk.CTkLabel(mesa_box, text="Accelerates Intel HD & AMD graphics for smooth FPS & fast chunk loads", font=ctk.CTkFont(size=11), text_color="#38bdf8").pack(anchor="w")

        self.mesa_var = ctk.BooleanVar(value=self.settings.mesa_glthread)
        mesa_switch = ctk.CTkSwitch(
            row_mesa,
            text="",
            variable=self.mesa_var,
            command=lambda: self.settings_mgr.update(mesa_glthread=self.mesa_var.get())
        )
        mesa_switch.pack(side="right")

    def _on_window_mode_change(self, choice: str) -> None:
        mode = "maximized" if "Maximized" in choice else "windowed"
        self.settings_mgr.update(window_mode=mode)
        if self.on_window_mode_change:
            self.on_window_mode_change(mode)

    def _build_java_section(self) -> None:
        sec = self._create_section("Java Runtime Management")

        # Auto Java vs Custom
        row1 = ctk.CTkFrame(sec, fg_color="transparent")
        row1.pack(fill="x", padx=20, pady=6)

        ctk.CTkLabel(row1, text="Java Management Mode:", font=ctk.CTkFont(size=13)).pack(side="left")
        self.java_mode = ctk.CTkSegmentedButton(
            row1,
            values=["Automatic", "Custom Executable"],
            selected_color=ACCENT_COLOR,
            selected_hover_color=ACCENT_HOVER_COLOR,
            command=self._on_java_mode_change
        )
        self.java_mode.set("Automatic" if self.settings.java_management == "auto" else "Custom Executable")
        self.java_mode.pack(side="right")

        # Discovered Javas list
        row_disc = ctk.CTkFrame(sec, fg_color="transparent")
        row_disc.pack(fill="x", padx=20, pady=(6, 2))

        javas = self.java_manager.get_all()
        j_names = [f"Java {j.major_version} ({j.vendor}) - {j.path}" for j in javas] if javas else ["No system Java runtimes discovered"]

        ctk.CTkLabel(row_disc, text="Detected System Java Runtimes:", font=ctk.CTkFont(size=12, weight="bold"), text_color=TEXT_MUTED_COLOR).pack(anchor="w")
        for j_text in j_names[:4]:
            ctk.CTkLabel(row_disc, text=f"• {j_text}", font=ctk.CTkFont(size=11), text_color="#94a3b8").pack(anchor="w", padx=10)

        # Temurin Auto-Installer
        row_install = ctk.CTkFrame(sec, fg_color="transparent")
        row_install.pack(fill="x", padx=20, pady=10)

        self.btn_install_java21 = ctk.CTkButton(
            row_install,
            text="Install Java 21 (Temurin OpenJDK)",
            height=32,
            fg_color="#334155",
            hover_color=SURFACE_LIGHT_COLOR,
            command=lambda: self._install_temurin(21)
        )
        self.btn_install_java21.pack(side="left", padx=(0, 8))

        self.btn_install_java17 = ctk.CTkButton(
            row_install,
            text="Install Java 17",
            height=32,
            fg_color="#334155",
            hover_color=SURFACE_LIGHT_COLOR,
            command=lambda: self._install_temurin(17)
        )
        self.btn_install_java17.pack(side="left")

        # Custom Java Entry
        self.custom_java_frame = ctk.CTkFrame(sec, fg_color="transparent")
        self.custom_java_frame.pack(fill="x", padx=20, pady=(8, 4))

        ctk.CTkLabel(self.custom_java_frame, text="Custom Java Executable Path:", font=ctk.CTkFont(size=12)).pack(anchor="w")

        entry_row = ctk.CTkFrame(self.custom_java_frame, fg_color="transparent")
        entry_row.pack(fill="x", pady=4)

        self.java_path_entry = ctk.CTkEntry(entry_row, height=34)
        self.java_path_entry.insert(0, self.settings.custom_java_path or "")
        self.java_path_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))

        browse_btn = ctk.CTkButton(
            entry_row,
            text="Browse...",
            width=80,
            height=34,
            command=self._browse_custom_java
        )
        browse_btn.pack(side="left", padx=(0, 8))

        validate_btn = ctk.CTkButton(
            entry_row,
            text="Validate",
            width=80,
            height=34,
            fg_color=ACCENT_COLOR,
            hover_color=ACCENT_HOVER_COLOR,
            text_color="#022c22",
            command=self._validate_custom_java
        )
        validate_btn.pack(side="left")

    def _on_java_mode_change(self, choice: str) -> None:
        mode = "auto" if choice == "Automatic" else "manual"
        self.settings_mgr.update(java_management=mode)

    def _browse_custom_java(self) -> None:
        path = filedialog.askopenfilename(title="Select Java Executable")
        if path:
            self.java_path_entry.delete(0, "end")
            self.java_path_entry.insert(0, path)
            self.settings_mgr.update(custom_java_path=path)

    def _validate_custom_java(self) -> None:
        path = self.java_path_entry.get().strip()
        info = parse_java_version(path)
        if info:
            messagebox.showinfo("Java Valid", f"Successfully detected:\n{info.display_name}")
            self.settings_mgr.update(custom_java_path=path)
        else:
            messagebox.showerror("Invalid Java", f"The executable at '{path}' could not be executed or is not a valid Java runtime.")

    def _install_temurin(self, major_version: int) -> None:
        confirm = messagebox.askyesno("Install Java", f"Download and install Eclipse Temurin OpenJDK {major_version} automatically?")
        if not confirm:
            return

        def worker() -> None:
            try:
                info = self.java_manager.install_temurin_java(major_version)
                if info:
                    self.after(0, lambda: messagebox.showinfo("Java Installed", f"Java {major_version} installed successfully!"))
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Install Failed", f"Could not install Java {major_version}: {e}"))

        threading.Thread(target=worker, daemon=True).start()

    def _build_memory_section(self) -> None:
        sec = self._create_section("Memory & JVM Settings")

        # Total System RAM
        vm = psutil.virtual_memory()
        total_ram_gb = vm.total // (1024**3)
        rec_ram_mb = min(6144, max(2048, (vm.total // (1024**2)) // 2))

        ram_info = ctk.CTkLabel(
            sec,
            text=f"Total System RAM: {total_ram_gb} GB  •  Recommended Allocation: {rec_ram_mb} MB ({rec_ram_mb//1024} GB)",
            font=ctk.CTkFont(size=12),
            text_color="#38bdf8"
        )
        ram_info.pack(anchor="w", padx=20, pady=(0, 10))

        # Max RAM Slider
        slider_frame = ctk.CTkFrame(sec, fg_color="transparent")
        slider_frame.pack(fill="x", padx=20, pady=4)

        ctk.CTkLabel(slider_frame, text="Default Maximum RAM:", font=ctk.CTkFont(size=13)).pack(side="left")
        self.ram_val_lbl = ctk.CTkLabel(slider_frame, text=f"{self.settings.default_max_ram_mb} MB", font=ctk.CTkFont(size=13, weight="bold"), text_color=ACCENT_COLOR)
        self.ram_val_lbl.pack(side="right")

        max_slider_val = min(32768, (vm.total // (1024**2)))
        self.ram_slider = ctk.CTkSlider(
            sec,
            from_=1024,
            to=max_slider_val,
            number_of_steps=16,
            command=self._on_ram_slider_change
        )
        self.ram_slider.set(self.settings.default_max_ram_mb)
        self.ram_slider.pack(fill="x", padx=20, pady=(4, 12))

        # Custom JVM Flags
        ctk.CTkLabel(sec, text="Default Custom JVM Arguments:", font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w", padx=20)
        self.jvm_entry = ctk.CTkEntry(sec, height=36)
        self.jvm_entry.insert(0, self.settings.custom_jvm_args)
        self.jvm_entry.pack(fill="x", padx=20, pady=(4, 8))

        save_jvm_btn = ctk.CTkButton(
            sec,
            text="Save JVM Flags",
            width=120,
            height=30,
            fg_color="#334155",
            hover_color=SURFACE_LIGHT_COLOR,
            command=lambda: self.settings_mgr.update(custom_jvm_args=self.jvm_entry.get().strip())
        )
        save_jvm_btn.pack(anchor="w", padx=20, pady=(0, 6))

    def _on_ram_slider_change(self, val: float) -> None:
        mb = int(val)
        self.ram_val_lbl.configure(text=f"{mb} MB ({mb // 1024} GB)")
        self.settings_mgr.update(default_max_ram_mb=mb)

    def _build_about_section(self) -> None:
        sec = self._create_section(f"About {APP_NAME}")

        v_lbl = ctk.CTkLabel(
            sec,
            text=f"{APP_NAME} v{APP_VERSION} (Debian / Linux / Windows)",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=TEXT_COLOR
        )
        v_lbl.pack(anchor="w", padx=20, pady=(0, 4))

        disc = ctk.CTkLabel(
            sec,
            text=DISCLAIMER,
            font=ctk.CTkFont(size=11),
            text_color=TEXT_MUTED_COLOR,
            wraplength=650,
            justify="left"
        )
        disc.pack(anchor="w", padx=20, pady=(0, 12))

        # Check for Updates
        update_box = ctk.CTkFrame(sec, fg_color="transparent")
        update_box.pack(fill="x", padx=20, pady=4)

        self.btn_update = ctk.CTkButton(
            update_box,
            text="Check for Updates",
            height=34,
            fg_color=ACCENT_COLOR,
            hover_color=ACCENT_HOVER_COLOR,
            text_color="#022c22",
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self._check_updates
        )
        self.btn_update.pack(side="left")

        self.update_status = ctk.CTkLabel(update_box, text="", font=ctk.CTkFont(size=12), text_color=TEXT_MUTED_COLOR)
        self.update_status.pack(side="left", padx=12)

    def _check_updates(self) -> None:
        self.btn_update.configure(state="disabled", text="Checking...")

        def worker() -> None:
            info = check_for_updates()
            def finish() -> None:
                self.btn_update.configure(state="normal", text="Check for Updates")
                if info.available:
                    self.update_status.configure(text=f"New version {info.latest_version} available!", text_color="#34d399")
                    top = self.winfo_toplevel()
                    if hasattr(top, "show_update_modal"):
                        top.show_update_modal(info)
                    else:
                        messagebox.showinfo("Update Available", f"A new version of SandeshLauncher is available: {info.latest_version}\n\nChangelog:\n{info.changelog}")
                else:
                    self.update_status.configure(text=f"You are on the latest version ({APP_VERSION}).", text_color="#38bdf8")

            self.after(0, finish)

        threading.Thread(target=worker, daemon=True).start()
