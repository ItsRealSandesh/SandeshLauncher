"""
Instances Page for SandeshLauncher.
Displays all instances in a grid/list, with creation wizard, editing, cloning,
and directory opening.
"""

import os
import subprocess
import sys
import threading
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import Callable, Optional

import customtkinter as ctk

from config import (
    ACCENT_COLOR,
    ACCENT_HOVER_COLOR,
    SURFACE_COLOR,
    SURFACE_LIGHT_COLOR,
    TEXT_COLOR,
    TEXT_MUTED_COLOR,
)
from instances.manager import InstanceManager
from instances.model import MinecraftInstance
from minecraft.versions import get_available_versions, get_latest_release_version
from loaders.fabric import get_fabric_loader_versions
from utils.logging import get_logger
from utils.paths import get_instances_dir

logger = get_logger("ui_instances")


class InstancesPage(ctk.CTkFrame):
    def __init__(
        self,
        parent: ctk.CTkBaseClass,
        instance_manager: InstanceManager,
        on_instance_selected: Optional[Callable[[MinecraftInstance], None]] = None,
        on_launch_requested: Optional[Callable[[MinecraftInstance], None]] = None,
    ):
        super().__init__(parent, fg_color="transparent")
        self.instance_manager = instance_manager
        self.on_instance_selected = on_instance_selected
        self.on_launch_requested = on_launch_requested

        self._build_ui()
        self.refresh_instances()

    def _build_ui(self) -> None:
        # Header
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.pack(fill="x", padx=30, pady=(24, 16))

        title = ctk.CTkLabel(
            header_frame,
            text="Minecraft Instances",
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color=TEXT_COLOR
        )
        title.pack(side="left")

        self.btn_new = ctk.CTkButton(
            header_frame,
            text="+ Create Instance",
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=ACCENT_COLOR,
            hover_color=ACCENT_HOVER_COLOR,
            text_color="#022c22",
            height=36,
            command=self._show_create_modal
        )
        self.btn_new.pack(side="right")

        # Scrollable area
        self.scroll_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll_frame.pack(fill="both", expand=True, padx=30, pady=(0, 24))

    def refresh_instances(self) -> None:
        for widget in self.scroll_frame.winfo_children():
            widget.destroy()

        instances = self.instance_manager.get_all()

        if not instances:
            empty_card = ctk.CTkFrame(self.scroll_frame, fg_color=SURFACE_COLOR, corner_radius=12)
            empty_card.pack(fill="x", pady=20, padx=10, ipady=30)
            ctk.CTkLabel(
                empty_card,
                text="No instances created yet.\nClick '+ Create Instance' above to create your first Minecraft setup!",
                font=ctk.CTkFont(size=14),
                text_color=TEXT_MUTED_COLOR,
                justify="center"
            ).pack()
            return

        for inst in instances:
            self._render_instance_card(inst)

    def _render_instance_card(self, inst: MinecraftInstance) -> None:
        card = ctk.CTkFrame(
            self.scroll_frame,
            fg_color=SURFACE_COLOR,
            border_width=1,
            border_color="#334155",
            corner_radius=12
        )
        card.pack(fill="x", pady=6, padx=8, ipady=8)

        # Left Info
        info_frame = ctk.CTkFrame(card, fg_color="transparent")
        info_frame.pack(side="left", fill="both", expand=True, padx=16, pady=8)

        row1 = ctk.CTkFrame(info_frame, fg_color="transparent")
        row1.pack(fill="x")

        name_lbl = ctk.CTkLabel(
            row1,
            text=inst.name,
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=TEXT_COLOR
        )
        name_lbl.pack(side="left")

        # Loader badge
        loader_color = "#3b82f6" if inst.loader == "fabric" else "#8b5cf6" if inst.loader == "quilt" else "#ea580c" if inst.loader in ("forge", "neoforge") else "#10b981"
        loader_badge = ctk.CTkLabel(
            row1,
            text=f"{inst.loader.upper()} {inst.minecraft_version}",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#ffffff",
            fg_color=loader_color,
            corner_radius=6,
            padx=8,
            pady=2
        )
        loader_badge.pack(side="left", padx=10)

        # Details
        playtime_min = inst.playtime_seconds // 60
        last_played_text = f"Last played: {inst.last_played[:10]}" if inst.last_played else "Never played"
        sub_lbl = ctk.CTkLabel(
            info_frame,
            text=f"RAM: {inst.max_ram_mb} MB  |  Playtime: {playtime_min}m  |  {last_played_text}",
            font=ctk.CTkFont(size=12),
            text_color=TEXT_MUTED_COLOR
        )
        sub_lbl.pack(anchor="w", pady=(4, 0))

        # Action Buttons
        btn_frame = ctk.CTkFrame(card, fg_color="transparent")
        btn_frame.pack(side="right", padx=16)

        # Select & Play
        play_btn = ctk.CTkButton(
            btn_frame,
            text="▶ Play",
            width=70,
            height=32,
            fg_color=ACCENT_COLOR,
            hover_color=ACCENT_HOVER_COLOR,
            text_color="#022c22",
            font=ctk.CTkFont(size=12, weight="bold"),
            command=lambda i=inst: self._trigger_play(i)
        )
        play_btn.pack(side="left", padx=3)

        folder_btn = ctk.CTkButton(
            btn_frame,
            text="📂 Folder",
            width=70,
            height=32,
            fg_color="#334155",
            hover_color=SURFACE_LIGHT_COLOR,
            text_color=TEXT_COLOR,
            font=ctk.CTkFont(size=12),
            command=lambda i=inst: self._open_folder(i)
        )
        folder_btn.pack(side="left", padx=3)

        edit_btn = ctk.CTkButton(
            btn_frame,
            text="⚙ Edit",
            width=60,
            height=32,
            fg_color="#334155",
            hover_color=SURFACE_LIGHT_COLOR,
            text_color=TEXT_COLOR,
            font=ctk.CTkFont(size=12),
            command=lambda i=inst: self._show_edit_modal(i)
        )
        edit_btn.pack(side="left", padx=3)

        del_btn = ctk.CTkButton(
            btn_frame,
            text="🗑",
            width=36,
            height=32,
            fg_color="#334155",
            hover_color="#ef4444",
            text_color=TEXT_COLOR,
            font=ctk.CTkFont(size=13),
            command=lambda i=inst: self._delete_instance(i)
        )
        del_btn.pack(side="left", padx=3)

    def _trigger_play(self, instance: MinecraftInstance) -> None:
        if self.on_instance_selected:
            self.on_instance_selected(instance)
        if self.on_launch_requested:
            self.on_launch_requested(instance)

    def _open_folder(self, instance: MinecraftInstance) -> None:
        game_dir = instance.get_game_dir(get_instances_dir())
        try:
            if sys.platform == "win32":
                os.startfile(str(game_dir))
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(game_dir)])
            else:
                subprocess.Popen(["xdg-open", str(game_dir)])
        except Exception as e:
            messagebox.showerror("Error", f"Could not open directory: {e}")

    def _delete_instance(self, instance: MinecraftInstance) -> None:
        confirm = messagebox.askyesno(
            "Delete Instance",
            f"Are you sure you want to delete instance '{instance.name}'?\nThis will remove all mods, worlds, and configs in this instance."
        )
        if confirm:
            self.instance_manager.delete(instance.id)
            self.refresh_instances()

    def _show_create_modal(self) -> None:
        dialog = ctk.CTkToplevel(self)
        dialog.title("Create Minecraft Instance")
        dialog.geometry("520x600")
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()
        dialog.resizable(False, False)

        ctk.CTkLabel(
            dialog,
            text="Create New Instance",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color=TEXT_COLOR
        ).pack(pady=(20, 16))

        content = ctk.CTkFrame(dialog, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=32)

        # Name
        ctk.CTkLabel(content, text="Instance Name:", font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w")
        name_entry = ctk.CTkEntry(content, height=36, font=ctk.CTkFont(size=13))
        name_entry.insert(0, "My Survival")
        name_entry.pack(fill="x", pady=(4, 14))

        # Minecraft Version
        ctk.CTkLabel(content, text="Minecraft Version:", font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w")
        version_dropdown = ctk.CTkComboBox(content, height=36, values=["1.21.1", "1.21", "1.20.4", "1.20.1", "1.19.4", "1.16.5"])
        version_dropdown.set(get_latest_release_version())
        version_dropdown.pack(fill="x", pady=(4, 14))

        # Asynchronously fetch full version list from Mojang
        def fetch_versions() -> None:
            try:
                vers = get_available_versions(include_snapshots=False)
                ids = [v["id"] for v in vers[:40]]
                if ids:
                    self.after(0, lambda: version_dropdown.configure(values=ids))
            except Exception:
                pass
        threading.Thread(target=fetch_versions, daemon=True).start()

        # Mod Loader
        ctk.CTkLabel(content, text="Mod Loader:", font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w")
        loader_dropdown = ctk.CTkComboBox(
            content,
            height=36,
            values=["Vanilla", "Fabric", "Forge", "NeoForge", "Quilt"]
        )
        loader_dropdown.set("Fabric")
        loader_dropdown.pack(fill="x", pady=(4, 14))

        # Loader Version
        ctk.CTkLabel(content, text="Loader Version:", font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w")
        loader_ver_entry = ctk.CTkEntry(content, height=36, font=ctk.CTkFont(size=13))
        loader_ver_entry.insert(0, "latest")
        loader_ver_entry.pack(fill="x", pady=(4, 14))

        # RAM
        ctk.CTkLabel(content, text="Max Memory Allocation (MB):", font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w")
        ram_slider_frame = ctk.CTkFrame(content, fg_color="transparent")
        ram_slider_frame.pack(fill="x", pady=(4, 20))

        ram_label = ctk.CTkLabel(ram_slider_frame, text="4096 MB (4 GB)", font=ctk.CTkFont(size=12), text_color=ACCENT_COLOR)
        ram_label.pack(side="right")

        ram_slider = ctk.CTkSlider(
            ram_slider_frame,
            from_=1024,
            to=8192,
            number_of_steps=14,
            command=lambda val: ram_label.configure(text=f"{int(val)} MB ({int(val)//1024} GB)")
        )
        ram_slider.set(4096)
        ram_slider.pack(side="left", fill="x", expand=True, padx=(0, 10))

        def do_create() -> None:
            name = name_entry.get().strip() or "Minecraft Instance"
            mc_ver = version_dropdown.get().strip()
            loader = loader_dropdown.get().strip().lower()
            l_ver = loader_ver_entry.get().strip() or "latest"
            max_ram = int(ram_slider.get())

            try:
                inst = self.instance_manager.create(
                    name=name,
                    minecraft_version=mc_ver,
                    loader=loader,
                    loader_version=l_ver,
                    max_ram_mb=max_ram
                )
                dialog.destroy()
                self.refresh_instances()
                if self.on_instance_selected:
                    self.on_instance_selected(inst)
            except Exception as e:
                messagebox.showerror("Error", f"Could not create instance: {e}", parent=dialog)

        create_btn = ctk.CTkButton(
            dialog,
            text="Create Instance",
            fg_color=ACCENT_COLOR,
            hover_color=ACCENT_HOVER_COLOR,
            text_color="#022c22",
            height=40,
            font=ctk.CTkFont(size=14, weight="bold"),
            command=do_create
        )
        create_btn.pack(fill="x", padx=32, pady=(0, 24))

    def _show_edit_modal(self, instance: MinecraftInstance) -> None:
        dialog = ctk.CTkToplevel(self)
        dialog.title(f"Edit - {instance.name}")
        dialog.geometry("500x520")
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()
        dialog.resizable(False, False)

        ctk.CTkLabel(
            dialog,
            text=f"Edit Instance Settings",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=TEXT_COLOR
        ).pack(pady=(20, 16))

        content = ctk.CTkFrame(dialog, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=32)

        # Name
        ctk.CTkLabel(content, text="Instance Name:", font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w")
        name_entry = ctk.CTkEntry(content, height=36)
        name_entry.insert(0, instance.name)
        name_entry.pack(fill="x", pady=(4, 12))

        # Max RAM
        ctk.CTkLabel(content, text="Max RAM (MB):", font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w")
        ram_entry = ctk.CTkEntry(content, height=36)
        ram_entry.insert(0, str(instance.max_ram_mb))
        ram_entry.pack(fill="x", pady=(4, 12))

        # Custom JVM arguments
        ctk.CTkLabel(content, text="Custom JVM Arguments:", font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w")
        jvm_entry = ctk.CTkEntry(content, height=36)
        jvm_entry.insert(0, instance.jvm_args or "")
        jvm_entry.pack(fill="x", pady=(4, 12))

        # Custom Java
        ctk.CTkLabel(content, text="Java Path ('auto' for default):", font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w")
        java_entry = ctk.CTkEntry(content, height=36)
        java_entry.insert(0, instance.java_path or "auto")
        java_entry.pack(fill="x", pady=(4, 20))

        def do_save() -> None:
            instance.name = name_entry.get().strip() or instance.name
            try:
                instance.max_ram_mb = int(ram_entry.get().strip())
            except ValueError:
                pass
            instance.jvm_args = jvm_entry.get().strip()
            instance.java_path = java_entry.get().strip() or "auto"

            self.instance_manager.save(instance)
            dialog.destroy()
            self.refresh_instances()

        save_btn = ctk.CTkButton(
            dialog,
            text="Save Changes",
            fg_color=ACCENT_COLOR,
            hover_color=ACCENT_HOVER_COLOR,
            text_color="#022c22",
            height=38,
            font=ctk.CTkFont(size=13, weight="bold"),
            command=do_save
        )
        save_btn.pack(fill="x", padx=32, pady=(0, 24))
