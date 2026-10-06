"""
Installed Mods and Content manager page for SandeshLauncher.
Enables toggling mod states (enable/disable), uninstalling, and opening folders.
"""

import os
import subprocess
import sys
from tkinter import messagebox
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
from mods.manager import ModManager, InstalledMod
from utils.logging import get_logger
from utils.paths import get_instances_dir

logger = get_logger("ui_installed")


class InstalledContentPage(ctk.CTkFrame):
    def __init__(
        self,
        parent: ctk.CTkBaseClass,
        instance_manager: InstanceManager,
        current_instance: Optional[MinecraftInstance] = None,
    ):
        super().__init__(parent, fg_color="transparent")
        self.instance_manager = instance_manager
        self.current_instance = current_instance
        self.mod_manager: Optional[ModManager] = None

        if self.current_instance:
            self.mod_manager = ModManager(self.current_instance)

        self._build_ui()
        self.refresh_list()

    def set_instance(self, instance: MinecraftInstance) -> None:
        self.current_instance = instance
        self.mod_manager = ModManager(instance)
        self.instance_selector.set(instance.name)
        self.refresh_list()

    def _build_ui(self) -> None:
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.pack(fill="x", padx=30, pady=(24, 16))

        title = ctk.CTkLabel(
            header_frame,
            text="Installed Mods",
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color=TEXT_COLOR
        )
        title.pack(side="left")

        # Instance Picker & Folder Button
        right_box = ctk.CTkFrame(header_frame, fg_color="transparent")
        right_box.pack(side="right")

        instances = self.instance_manager.get_all()
        inst_names = [i.name for i in instances] if instances else ["No Instances"]

        self.instance_selector = ctk.CTkComboBox(
            right_box,
            values=inst_names,
            height=36,
            width=200,
            command=self._on_instance_picked
        )
        if self.current_instance:
            self.instance_selector.set(self.current_instance.name)
        elif instances:
            self.current_instance = instances[0]
            self.mod_manager = ModManager(self.current_instance)
            self.instance_selector.set(instances[0].name)

        self.instance_selector.pack(side="left", padx=(0, 8))

        folder_btn = ctk.CTkButton(
            right_box,
            text="📂 Open Mods Folder",
            height=36,
            fg_color=SURFACE_COLOR,
            hover_color=SURFACE_LIGHT_COLOR,
            border_width=1,
            border_color="#475569",
            command=self._open_mods_folder
        )
        folder_btn.pack(side="left")

        # Scrollable area
        self.scroll_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll_frame.pack(fill="both", expand=True, padx=30, pady=(0, 24))

    def _on_instance_picked(self, choice: str) -> None:
        for inst in self.instance_manager.get_all():
            if inst.name == choice:
                self.current_instance = inst
                self.mod_manager = ModManager(inst)
                self.refresh_list()
                break

    def refresh_list(self) -> None:
        for widget in self.scroll_frame.winfo_children():
            widget.destroy()

        if not self.mod_manager:
            return

        mods = self.mod_manager.list_installed_mods()

        if not mods:
            empty_card = ctk.CTkFrame(self.scroll_frame, fg_color=SURFACE_COLOR, corner_radius=12)
            empty_card.pack(fill="x", pady=20, padx=10, ipady=30)
            ctk.CTkLabel(
                empty_card,
                text="No mods installed in this instance.\nUse the 'Modrinth Content' browser to download mods with one click!",
                font=ctk.CTkFont(size=14),
                text_color=TEXT_MUTED_COLOR,
                justify="center"
            ).pack()
            return

        for m in mods:
            self._render_mod_card(m)

    def _render_mod_card(self, mod: InstalledMod) -> None:
        card = ctk.CTkFrame(
            self.scroll_frame,
            fg_color=SURFACE_COLOR if mod.enabled else "#18181b",
            border_width=1,
            border_color="#334155" if mod.enabled else "#27272a",
            corner_radius=12
        )
        card.pack(fill="x", pady=4, padx=8, ipady=6)

        info = ctk.CTkFrame(card, fg_color="transparent")
        info.pack(side="left", fill="both", expand=True, padx=16, pady=6)

        title_row = ctk.CTkFrame(info, fg_color="transparent")
        title_row.pack(fill="x")

        title_lbl = ctk.CTkLabel(
            title_row,
            text=mod.name,
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=TEXT_COLOR if mod.enabled else TEXT_MUTED_COLOR
        )
        title_lbl.pack(side="left")

        if mod.version:
            ver_badge = ctk.CTkLabel(
                title_row,
                text=mod.version,
                font=ctk.CTkFont(size=11),
                text_color="#94a3b8",
                fg_color="#334155",
                corner_radius=4,
                padx=6,
                pady=1
            )
            ver_badge.pack(side="left", padx=8)

        status_badge = ctk.CTkLabel(
            title_row,
            text="ENABLED" if mod.enabled else "DISABLED",
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color="#064e3b" if mod.enabled else "#71717a",
            fg_color=ACCENT_COLOR if mod.enabled else "#27272a",
            corner_radius=4,
            padx=6,
            pady=1
        )
        status_badge.pack(side="left")

        desc_text = mod.description or mod.filename
        desc_lbl = ctk.CTkLabel(
            info,
            text=desc_text[:120] + ("..." if len(desc_text) > 120 else ""),
            font=ctk.CTkFont(size=12),
            text_color=TEXT_MUTED_COLOR,
            anchor="w"
        )
        desc_lbl.pack(fill="x", pady=(2, 0))

        # Actions
        btn_frame = ctk.CTkFrame(card, fg_color="transparent")
        btn_frame.pack(side="right", padx=16)

        # Toggle Switch
        toggle_switch = ctk.CTkSwitch(
            btn_frame,
            text="",
            width=40,
            command=lambda m_name=mod.filename: self._toggle_mod(m_name)
        )
        if mod.enabled:
            toggle_switch.select()
        else:
            toggle_switch.deselect()
        toggle_switch.pack(side="left", padx=8)

        del_btn = ctk.CTkButton(
            btn_frame,
            text="🗑",
            width=36,
            height=30,
            fg_color="#334155",
            hover_color="#ef4444",
            text_color=TEXT_COLOR,
            command=lambda m_name=mod.filename: self._delete_mod(m_name)
        )
        del_btn.pack(side="left", padx=4)

    def _toggle_mod(self, filename: str) -> None:
        if self.mod_manager:
            self.mod_manager.toggle_mod(filename)
            self.refresh_list()

    def _delete_mod(self, filename: str) -> None:
        confirm = messagebox.askyesno("Uninstall Mod", f"Are you sure you want to remove '{filename}'?")
        if confirm and self.mod_manager:
            self.mod_manager.delete_mod(filename)
            self.refresh_list()

    def _open_mods_folder(self) -> None:
        if not self.current_instance:
            return
        mods_dir = self.current_instance.get_mods_dir(get_instances_dir())
        try:
            if sys.platform == "win32":
                os.startfile(str(mods_dir))
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(mods_dir)])
            else:
                subprocess.Popen(["xdg-open", str(mods_dir)])
        except Exception as e:
            messagebox.showerror("Error", f"Could not open directory: {e}")
