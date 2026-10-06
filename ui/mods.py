"""
Modrinth Content Browser for SandeshLauncher.
Enables searching and one-click installation of Mods, Modpacks, Shaders,
and Resource Packs with selectable Forge / Fabric loaders and Minecraft versions.
"""

import threading
from tkinter import messagebox
from typing import Any, Callable, Dict, List, Optional

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
from mods.installer import ContentInstaller
from mods.modrinth import ModrinthClient, ModrinthProject
from utils.logging import get_logger

logger = get_logger("ui_mods")


class ModrinthBrowserPage(ctk.CTkFrame):
    def __init__(
        self,
        parent: ctk.CTkBaseClass,
        instance_manager: InstanceManager,
        current_instance: Optional[MinecraftInstance] = None,
        on_instance_created: Optional[Callable[[MinecraftInstance], None]] = None,
    ):
        super().__init__(parent, fg_color="transparent")
        self.instance_manager = instance_manager
        self.current_instance = current_instance
        self.on_instance_created = on_instance_created

        self.client = ModrinthClient()
        self.installer = ContentInstaller(self.client, self.instance_manager)
        self.current_type = "mod"  # mod, modpack, shader, resourcepack
        self._search_cache: Dict[tuple, List[ModrinthProject]] = {}

        self._build_ui()
        # Defer initial search so mainloop has started
        self.after(250, self._trigger_search)

    def set_instance(self, instance: MinecraftInstance) -> None:
        self.current_instance = instance
        self.instance_selector.set(instance.name)
        self._sync_filters_to_instance()
        self._trigger_search()

    def _sync_filters_to_instance(self) -> None:
        if self.current_instance:
            ldr = self.current_instance.loader.capitalize()
            if ldr in ("Fabric", "Forge", "Neoforge", "Quilt"):
                if ldr == "Neoforge":
                    ldr = "NeoForge"
                self.loader_selector.set(f"Loader: {ldr}")
            self.version_selector.set(f"Version: {self.current_instance.minecraft_version}")

    def _safe_after(self, func: Callable[[], None]) -> None:
        try:
            self.after(0, func)
        except Exception:
            pass

    def _build_ui(self) -> None:
        # Header Controls
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=30, pady=(20, 10))

        title = ctk.CTkLabel(
            header,
            text="Modrinth Content",
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color=TEXT_COLOR
        )
        title.pack(side="left")

        # Type Tabs (Segmented Button)
        self.tab_selector = ctk.CTkSegmentedButton(
            header,
            values=["Mods", "Modpacks", "Shaders", "Resource Packs"],
            selected_color=ACCENT_COLOR,
            selected_hover_color=ACCENT_HOVER_COLOR,
            unselected_color=SURFACE_COLOR,
            unselected_hover_color=SURFACE_LIGHT_COLOR,
            text_color=TEXT_COLOR,
            height=34,
            command=self._on_tab_changed
        )
        self.tab_selector.set("Mods")
        self.tab_selector.pack(side="right")

        # Row 1: Search Bar & Search Button
        search_bar = ctk.CTkFrame(self, fg_color="transparent")
        search_bar.pack(fill="x", padx=30, pady=(0, 8))

        self.search_entry = ctk.CTkEntry(
            search_bar,
            placeholder_text="Search mods, modpacks, shaders, resource packs...",
            height=38,
            font=ctk.CTkFont(size=13)
        )
        self.search_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.search_entry.bind("<Return>", lambda e: self._trigger_search())

        search_btn = ctk.CTkButton(
            search_bar,
            text="Search",
            width=90,
            height=38,
            fg_color=ACCENT_COLOR,
            hover_color=ACCENT_HOVER_COLOR,
            text_color="#022c22",
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self._trigger_search
        )
        search_btn.pack(side="left")

        # Row 2: Filter Toolbar (Instance, Loader: Fabric/Forge, Version, Sort)
        filter_bar = ctk.CTkFrame(self, fg_color="transparent")
        filter_bar.pack(fill="x", padx=30, pady=(0, 10))

        # Target Instance Selector
        insts = self.instance_manager.get_all()
        inst_names = [i.name for i in insts] if insts else ["No Instance"]
        self.instance_selector = ctk.CTkComboBox(
            filter_bar,
            values=inst_names,
            height=34,
            width=180,
            command=self._on_instance_picked
        )
        if self.current_instance:
            self.instance_selector.set(self.current_instance.name)
        elif insts:
            self.current_instance = insts[0]
            self.instance_selector.set(insts[0].name)
        self.instance_selector.pack(side="left", padx=(0, 8))

        # Loader Selector (Forge / Fabric / NeoForge / Quilt / Any)
        loader_values = [
            "Loader: Auto",
            "Fabric",
            "Forge",
            "NeoForge",
            "Quilt",
            "Any Loader"
        ]
        self.loader_selector = ctk.CTkComboBox(
            filter_bar,
            values=loader_values,
            height=34,
            width=140,
            command=lambda v: self._trigger_search()
        )
        default_loader = "Fabric"
        if self.current_instance:
            ldr = self.current_instance.loader.capitalize()
            if ldr in ("Fabric", "Forge", "Neoforge", "Quilt"):
                default_loader = "NeoForge" if ldr == "Neoforge" else ldr
        self.loader_selector.set(f"Loader: {default_loader}")
        self.loader_selector.pack(side="left", padx=(0, 8))

        # Minecraft Version Selector
        version_values = [
            "Version: Auto",
            "1.21.1",
            "1.21",
            "1.20.4",
            "1.20.1",
            "1.19.4",
            "1.18.2",
            "1.16.5",
            "Any Version"
        ]
        self.version_selector = ctk.CTkComboBox(
            filter_bar,
            values=version_values,
            height=34,
            width=140,
            command=lambda v: self._trigger_search()
        )
        default_ver = self.current_instance.minecraft_version if self.current_instance else "1.21.1"
        self.version_selector.set(f"Version: {default_ver}")
        self.version_selector.pack(side="left", padx=(0, 8))

        # Sort Dropdown
        self.sort_selector = ctk.CTkComboBox(
            filter_bar,
            values=["Downloads", "Relevance", "Follows", "Updated"],
            height=34,
            width=120,
            command=lambda v: self._trigger_search()
        )
        self.sort_selector.set("Downloads")
        self.sort_selector.pack(side="left")

        # Status text
        self.status_lbl = ctk.CTkLabel(
            self,
            text="",
            font=ctk.CTkFont(size=12),
            text_color=TEXT_MUTED_COLOR
        )
        self.status_lbl.pack(fill="x", padx=30, pady=(0, 6))

        # Results Scrollable Frame
        self.scroll_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll_frame.pack(fill="both", expand=True, padx=30, pady=(0, 24))

    def _on_tab_changed(self, choice: str) -> None:
        type_map = {
            "Mods": "mod",
            "Modpacks": "modpack",
            "Shaders": "shader",
            "Resource Packs": "resourcepack",
        }
        self.current_type = type_map.get(choice, "mod")
        self._trigger_search()

    def _on_instance_picked(self, choice: str) -> None:
        for inst in self.instance_manager.get_all():
            if inst.name == choice:
                self.current_instance = inst
                self._sync_filters_to_instance()
                self._trigger_search()
                break

    def _get_active_filters(self) -> tuple[Optional[str], Optional[str]]:
        """Resolves target Minecraft version and Loader from dropdowns or selected instance."""
        # Loader
        raw_loader = self.loader_selector.get()
        if "Auto" in raw_loader and self.current_instance:
            target_loader = self.current_instance.loader
        elif "Any" in raw_loader:
            target_loader = None
        else:
            target_loader = raw_loader.replace("Loader:", "").strip().lower()

        # Version
        raw_ver = self.version_selector.get()
        if "Auto" in raw_ver and self.current_instance:
            target_ver = self.current_instance.minecraft_version
        elif "Any" in raw_ver:
            target_ver = None
        else:
            target_ver = raw_ver.replace("Version:", "").strip()

        return target_ver, target_loader

    def _trigger_search(self) -> None:
        query = self.search_entry.get().strip()
        sort_map = {
            "Relevance": "relevance",
            "Downloads": "downloads",
            "Follows": "follows",
            "Updated": "updated",
        }
        sort_key = sort_map.get(self.sort_selector.get(), "downloads")

        target_ver, target_loader = self._get_active_filters()

        cache_key = (query, self.current_type, target_ver, target_loader, sort_key)
        if cache_key in self._search_cache:
            self._display_results(self._search_cache[cache_key])
            return

        self.status_lbl.configure(text=f"Searching Modrinth {self.current_type}s...")

        def worker() -> None:
            try:
                results = self.client.search(
                    query=query,
                    project_type=self.current_type,
                    minecraft_version=target_ver,
                    loader=target_loader,
                    sort=sort_key,
                    limit=25
                )
                self._search_cache[cache_key] = results
                self._safe_after(lambda r=results: self._display_results(r))
            except Exception as e:
                err_msg = str(e)
                self._safe_after(lambda msg=err_msg: self.status_lbl.configure(text=f"Search failed: {msg}"))

        threading.Thread(target=worker, daemon=True).start()

    def _display_results(self, projects: List[ModrinthProject]) -> None:
        for widget in self.scroll_frame.winfo_children():
            widget.destroy()

        self.status_lbl.configure(text=f"Showing {len(projects)} {self.current_type}(s)")

        if not projects:
            empty = ctk.CTkFrame(self.scroll_frame, fg_color=SURFACE_COLOR, corner_radius=12)
            empty.pack(fill="x", pady=20, padx=10, ipady=30)
            ctk.CTkLabel(
                empty,
                text="No projects found matching your search and filter criteria.",
                font=ctk.CTkFont(size=14),
                text_color=TEXT_MUTED_COLOR,
                justify="center"
            ).pack()
            return

        for p in projects:
            self._render_project_card(p)

    def _render_project_card(self, proj: ModrinthProject) -> None:
        card = ctk.CTkFrame(
            self.scroll_frame,
            fg_color=SURFACE_COLOR,
            border_width=1,
            border_color="#334155",
            corner_radius=12
        )
        card.pack(fill="x", pady=5, padx=8, ipady=6)

        info = ctk.CTkFrame(card, fg_color="transparent")
        info.pack(side="left", fill="both", expand=True, padx=16, pady=8)

        # Title row
        title_row = ctk.CTkFrame(info, fg_color="transparent")
        title_row.pack(fill="x")

        t_lbl = ctk.CTkLabel(
            title_row,
            text=proj.title,
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=TEXT_COLOR
        )
        t_lbl.pack(side="left")

        by_lbl = ctk.CTkLabel(
            title_row,
            text=f"by {proj.author}",
            font=ctk.CTkFont(size=12),
            text_color=TEXT_MUTED_COLOR
        )
        by_lbl.pack(side="left", padx=8)

        dl_lbl = ctk.CTkLabel(
            title_row,
            text=f"⬇ {proj.display_downloads}",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#38bdf8",
            fg_color="#0c4a6e",
            corner_radius=4,
            padx=6,
            pady=2
        )
        dl_lbl.pack(side="left")

        # Description
        d_lbl = ctk.CTkLabel(
            info,
            text=proj.description[:140] + ("..." if len(proj.description) > 140 else ""),
            font=ctk.CTkFont(size=12),
            text_color=TEXT_MUTED_COLOR,
            anchor="w"
        )
        d_lbl.pack(fill="x", pady=(4, 0))

        # Categories & Loaders
        cat_text = " • ".join(proj.categories[:5])
        cat_lbl = ctk.CTkLabel(
            info,
            text=cat_text,
            font=ctk.CTkFont(size=11),
            text_color="#64748b",
            anchor="w"
        )
        cat_lbl.pack(fill="x", pady=(2, 0))

        # Actions Box
        act_box = ctk.CTkFrame(card, fg_color="transparent")
        act_box.pack(side="right", padx=16)

        btn_text = "Install Modpack" if proj.project_type == "modpack" else "Install"
        install_btn = ctk.CTkButton(
            act_box,
            text=btn_text,
            width=90,
            height=34,
            fg_color=ACCENT_COLOR,
            hover_color=ACCENT_HOVER_COLOR,
            text_color="#022c22",
            font=ctk.CTkFont(size=12, weight="bold"),
            command=lambda p_id=proj.id, b=None: self._on_install_clicked(p_id, install_btn)
        )
        install_btn.pack(side="left", padx=3)

        if proj.project_type != "modpack":
            vers_btn = ctk.CTkButton(
                act_box,
                text="Versions ▾",
                width=80,
                height=34,
                fg_color="#334155",
                hover_color=SURFACE_LIGHT_COLOR,
                text_color=TEXT_COLOR,
                font=ctk.CTkFont(size=11),
                command=lambda p=proj: self._show_versions_modal(p)
            )
            vers_btn.pack(side="left", padx=3)

    def _show_versions_modal(self, proj: ModrinthProject) -> None:
        """Opens dialog showing all available versions with explicit Forge/Fabric loader labels."""
        dialog = ctk.CTkToplevel(self)
        dialog.title(f"Versions - {proj.title}")
        dialog.geometry("640x540")
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()

        ctk.CTkLabel(
            dialog,
            text=f"Select Version for {proj.title}",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=TEXT_COLOR
        ).pack(pady=(16, 8))

        # Modal filter row
        f_row = ctk.CTkFrame(dialog, fg_color="transparent")
        f_row.pack(fill="x", padx=24, pady=(0, 10))

        ctk.CTkLabel(f_row, text="Filter:", font=ctk.CTkFont(size=12, weight="bold")).pack(side="left", padx=(0, 8))

        m_loader = ctk.CTkComboBox(f_row, values=["All Loaders", "Fabric", "Forge", "NeoForge", "Quilt"], width=130, height=30)
        m_loader.set("All Loaders")
        m_loader.pack(side="left", padx=(0, 8))

        m_status = ctk.CTkLabel(dialog, text="Fetching releases from Modrinth...", font=ctk.CTkFont(size=11), text_color=TEXT_MUTED_COLOR)
        m_status.pack(pady=(0, 6))

        scroll = ctk.CTkScrollableFrame(dialog, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=24, pady=(0, 16))

        def load_versions() -> None:
            try:
                all_v = self.client.get_project_versions(proj.id)
                self._safe_after(lambda: render_modal_list(all_v))
            except Exception as e:
                err_msg = str(e)
                self._safe_after(lambda: m_status.configure(text=f"Failed to load versions: {err_msg}"))

        def render_modal_list(versions_list: List[Dict[str, Any]]) -> None:
            m_status.configure(text=f"Showing {len(versions_list)} release(s)")
            for widget in scroll.winfo_children():
                widget.destroy()

            selected_loader = m_loader.get()

            count = 0
            for v_data in versions_list:
                loaders = v_data.get("loaders", [])
                if selected_loader != "All Loaders" and selected_loader.lower() not in [l.lower() for l in loaders]:
                    continue

                count += 1
                v_card = ctk.CTkFrame(scroll, fg_color=SURFACE_COLOR, corner_radius=8)
                v_card.pack(fill="x", pady=4, padx=4, ipady=6)

                v_info = ctk.CTkFrame(v_card, fg_color="transparent")
                v_info.pack(side="left", fill="both", expand=True, padx=12)

                v_name = v_data.get("name") or v_data.get("version_number", "Release")
                ctk.CTkLabel(v_info, text=v_name, font=ctk.CTkFont(size=13, weight="bold"), text_color=TEXT_COLOR, anchor="w").pack(fill="x")

                # Loader & MC version badges
                loaders_str = " / ".join([l.upper() for l in loaders])
                game_vers = ", ".join(v_data.get("game_versions", [])[:4])
                meta_str = f"Loaders: {loaders_str}  •  MC: {game_vers}"
                ctk.CTkLabel(v_info, text=meta_str, font=ctk.CTkFont(size=11), text_color=ACCENT_COLOR, anchor="w").pack(fill="x", pady=(2, 0))

                # Install button
                v_id = v_data.get("id")
                inst_btn = ctk.CTkButton(
                    v_card,
                    text="Install",
                    width=75,
                    height=28,
                    fg_color=ACCENT_COLOR,
                    hover_color=ACCENT_HOVER_COLOR,
                    text_color="#022c22",
                    font=ctk.CTkFont(size=11, weight="bold"),
                    command=lambda vid=v_id, b=None: self._install_specific_version(proj.id, vid, dialog)
                )
                inst_btn.pack(side="right", padx=12)

            if count == 0:
                ctk.CTkLabel(scroll, text="No versions match the selected loader filter.", font=ctk.CTkFont(size=12), text_color=TEXT_MUTED_COLOR).pack(pady=20)

        m_loader.configure(command=lambda v: threading.Thread(target=load_versions, daemon=True).start())
        threading.Thread(target=load_versions, daemon=True).start()

    def _install_specific_version(self, project_id: str, version_id: str, dialog_to_close: ctk.CTkToplevel) -> None:
        if not self.current_instance:
            messagebox.showerror("Error", "Please select a target instance first.", parent=dialog_to_close)
            return

        dialog_to_close.destroy()
        self.status_lbl.configure(text="Installing selected version...")

        def worker() -> None:
            try:
                success, msg, installed = self.installer.install_project_to_instance(
                    project_id_or_slug=project_id,
                    instance=self.current_instance,
                    specific_version_id=version_id,
                    progress_callback=lambda m, c, t: self._safe_after(lambda: self.status_lbl.configure(text=m))
                )
                if success:
                    self._safe_after(lambda: messagebox.showinfo("Installed", msg))
                else:
                    self._safe_after(lambda: messagebox.showerror("Failed", msg))
            except Exception as e:
                err_msg = str(e)
                self._safe_after(lambda: messagebox.showerror("Install Error", err_msg))

        threading.Thread(target=worker, daemon=True).start()

    def _on_install_clicked(self, project_id: str, button: ctk.CTkButton) -> None:
        button.configure(state="disabled", text="Installing...")

        target_ver, target_loader = self._get_active_filters()

        def worker() -> None:
            try:
                if self.current_type == "modpack":
                    inst = self.installer.install_modpack(
                        project_id_or_slug=project_id,
                        progress_callback=lambda msg, c, t: self._safe_after(lambda: self.status_lbl.configure(text=msg))
                    )
                    self._safe_after(lambda: self._on_modpack_installed(inst, button))
                else:
                    if not self.current_instance:
                        raise ValueError("Please select a target instance first.")
                    success, msg, installed_files = self.installer.install_project_to_instance(
                        project_id_or_slug=project_id,
                        instance=self.current_instance,
                        target_minecraft_version=target_ver,
                        target_loader=target_loader,
                        progress_callback=lambda msg, c, t: self._safe_after(lambda: self.status_lbl.configure(text=msg))
                    )
                    if success:
                        self._safe_after(lambda: self._on_content_installed(msg, button))
                    else:
                        self._safe_after(lambda: self._on_install_failed(msg, button))
            except Exception as e:
                err_msg = str(e)
                self._safe_after(lambda: self._on_install_failed(err_msg, button))

        threading.Thread(target=worker, daemon=True).start()

    def _on_content_installed(self, message: str, button: ctk.CTkButton) -> None:
        button.configure(state="normal", text="Installed ✓", fg_color="#059669")
        self.status_lbl.configure(text=message, text_color="#34d399")
        messagebox.showinfo("Installation Complete", message)

    def _on_modpack_installed(self, instance: MinecraftInstance, button: ctk.CTkButton) -> None:
        button.configure(state="normal", text="Installed ✓", fg_color="#059669")
        self.status_lbl.configure(text=f"Modpack created instance '{instance.name}' successfully!", text_color="#34d399")
        if self.on_instance_created:
            self.on_instance_created(instance)
        messagebox.showinfo("Modpack Installed", f"Created new instance '{instance.name}'. You can find it in your Instances list!")

    def _on_install_failed(self, error: str, button: ctk.CTkButton) -> None:
        button.configure(state="normal", text="Install", fg_color=ACCENT_COLOR)
        self.status_lbl.configure(text=f"Install error: {error}", text_color="#f87171")
        messagebox.showerror("Installation Error", error)
