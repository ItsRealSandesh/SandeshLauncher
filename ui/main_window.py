"""
Main Window and Navigation Controller for SandeshLauncher.
Features a sleek modern dark sidebar, responsive page router,
and seamless first-run onboarding experience.
"""

from pathlib import Path
from tkinter import messagebox
from typing import Dict, Optional

import customtkinter as ctk
from PIL import Image

from auth.token_store import Account, TokenStore
from config import (
    ACCENT_COLOR,
    ACCENT_HOVER_COLOR,
    APP_NAME,
    APP_VERSION,
    SURFACE_COLOR,
    SURFACE_LIGHT_COLOR,
    TEXT_COLOR,
    TEXT_MUTED_COLOR,
)
from downloads.manager import DownloadManager
from instances.manager import InstanceManager
from instances.model import MinecraftInstance
from java.manager import JavaManager
from minecraft.launcher import MinecraftLauncher
from minecraft.versions import get_latest_release_version
from ui.accounts import AccountsPage
from ui.downloads import DownloadsPage
from ui.home import HomePage
from ui.installed import InstalledContentPage
from ui.instances import InstancesPage
from ui.logs import LogsPage
from ui.mods import ModrinthBrowserPage
from ui.settings import SettingsPage
from updater.github import (
    UpdateInfo,
    check_for_updates,
    download_and_apply_update,
    restart_application,
)
from utils.logging import get_logger
from utils.paths import get_assets_dir
from utils.settings import SettingsManager

from utils.screen import apply_desktop_window_fit, get_desktop_resolution

logger = get_logger("main_window")


class MainWindow(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(f"{APP_NAME} - Minecraft Launcher")

        # Set appearance
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("green")

        # Initialize core managers
        self.settings_mgr = SettingsManager.get_instance()
        self.token_store = TokenStore()
        self.instance_manager = InstanceManager()
        self.java_manager = JavaManager()
        self.download_manager = DownloadManager.get_instance()
        self.minecraft_launcher = MinecraftLauncher(self.java_manager)

        # Always adapt window to desktop size so there is no clipping or taskbar overlap
        mode = self.settings_mgr.settings.window_mode
        apply_desktop_window_fit(self, maximize=(mode != "windowed"))
        if mode != "windowed":
            self.after(60, lambda: apply_desktop_window_fit(self, maximize=True))

        # Ensure at least one default instance exists
        if not self.instance_manager.get_all():
            latest_v = get_latest_release_version()
            self.instance_manager.create(
                name="Default Fabric 1.21",
                minecraft_version=latest_v,
                loader="fabric",
                loader_version="latest"
            )

        self._load_app_icon()
        self._build_layout()
        self._check_first_run()
        self._schedule_startup_update_check()

    def _load_app_icon(self) -> None:
        icon_path = get_assets_dir() / "icons" / "app_icon.png"
        if icon_path.exists():
            try:
                # Tkinter iconphoto
                img = Image.open(icon_path)
                ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(32, 32))
                self._icon_img = ctk_img
                # Set window icon
                self.iconphoto(True, tk_img := ctk.CTkImage(light_image=img, dark_image=img, size=(32, 32))._light_image)
            except Exception:
                pass

    def _build_layout(self) -> None:
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        # 1. Left Sidebar
        self.sidebar = ctk.CTkFrame(self, width=200, fg_color=SURFACE_COLOR, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_rowconfigure(9, weight=1)

        # Brand
        brand_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        brand_frame.pack(fill="x", padx=14, pady=(14, 16))

        brand_lbl = ctk.CTkLabel(
            brand_frame,
            text=APP_NAME.upper(),
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=TEXT_COLOR
        )
        brand_lbl.pack(anchor="w")

        v_lbl = ctk.CTkLabel(
            brand_frame,
            text=f"v{APP_VERSION} • Production",
            font=ctk.CTkFont(size=11),
            text_color=ACCENT_COLOR
        )
        v_lbl.pack(anchor="w")

        # Navigation buttons container
        self.nav_btns: Dict[str, ctk.CTkButton] = {}
        nav_items = [
            ("home", "🏠  Home"),
            ("instances", "📦  Instances"),
            ("mods", "🌐  Modrinth Content"),
            ("installed", "🧩  Installed Mods"),
            ("accounts", "👤  Accounts"),
            ("downloads", "⬇  Downloads"),
            ("settings", "⚙  Settings"),
            ("logs", "📋  Logs & Console"),
        ]

        for page_id, label in nav_items:
            btn = ctk.CTkButton(
                self.sidebar,
                text=label,
                anchor="w",
                font=ctk.CTkFont(size=12, weight="bold"),
                fg_color="transparent",
                text_color=TEXT_COLOR,
                hover_color=SURFACE_LIGHT_COLOR,
                height=36,
                corner_radius=8,
                command=lambda pid=page_id: self.navigate_to(pid)
            )
            btn.pack(fill="x", padx=10, pady=2)
            self.nav_btns[page_id] = btn

        # 2. Main Content Page Container
        self.content_area = ctk.CTkFrame(self, fg_color="transparent")
        self.content_area.grid(row=0, column=1, sticky="nsew")

        # Instantiate Pages
        self.pages: Dict[str, ctk.CTkFrame] = {}

        self.pages["home"] = HomePage(
            parent=self.content_area,
            token_store=self.token_store,
            instance_manager=self.instance_manager,
            java_manager=self.java_manager,
            launcher=self.minecraft_launcher,
            on_navigate=self.navigate_to
        )

        self.pages["instances"] = InstancesPage(
            parent=self.content_area,
            instance_manager=self.instance_manager,
            on_instance_selected=self._on_instance_selected,
            on_launch_requested=self._on_launch_requested_from_instances
        )

        self.pages["mods"] = ModrinthBrowserPage(
            parent=self.content_area,
            instance_manager=self.instance_manager,
            current_instance=self.pages["home"].current_instance,
            on_instance_created=self._on_modpack_instance_created
        )

        self.pages["installed"] = InstalledContentPage(
            parent=self.content_area,
            instance_manager=self.instance_manager,
            current_instance=self.pages["home"].current_instance
        )

        self.pages["accounts"] = AccountsPage(
            parent=self.content_area,
            token_store=self.token_store,
            on_account_changed=self._on_account_changed
        )

        self.pages["downloads"] = DownloadsPage(
            parent=self.content_area,
            download_manager=self.download_manager
        )

        self.pages["settings"] = SettingsPage(
            parent=self.content_area,
            java_manager=self.java_manager,
            on_window_mode_change=self.apply_window_mode
        )

        self.pages["logs"] = LogsPage(
            parent=self.content_area
        )

        # Show Home by default
        self.active_page_id = ""
        self.navigate_to("home")

    def apply_window_mode(self, mode: str) -> None:
        """Dynamically applies window mode: 'maximized' (desktop fit) or 'windowed'."""
        self.settings_mgr.update(window_mode=mode)
        apply_desktop_window_fit(self, maximize=(mode != "windowed"))

    def navigate_to(self, page_id: str) -> None:
        if page_id == self.active_page_id:
            return

        # Hide current
        if self.active_page_id and self.active_page_id in self.pages:
            self.pages[self.active_page_id].pack_forget()
            if self.active_page_id in self.nav_btns:
                self.nav_btns[self.active_page_id].configure(fg_color="transparent")

        # Show new
        if page_id in self.pages:
            self.pages[page_id].pack(fill="both", expand=True)
            self.active_page_id = page_id
            if page_id in self.nav_btns:
                self.nav_btns[page_id].configure(fg_color="#334155")

            # Refresh specific pages on entry
            if page_id == "instances":
                self.pages["instances"].refresh_instances()
            elif page_id == "installed":
                self.pages["installed"].set_instance(self.pages["home"].current_instance)
            elif page_id == "mods":
                self.pages["mods"].set_instance(self.pages["home"].current_instance)
            elif page_id == "home":
                self.pages["home"].refresh_instances_list()

    def _on_instance_selected(self, instance: MinecraftInstance) -> None:
        self.settings_mgr.update(last_selected_instance_id=instance.id)
        self.pages["home"].set_instance(instance)
        self.pages["mods"].set_instance(instance)
        self.pages["installed"].set_instance(instance)

    def _on_launch_requested_from_instances(self, instance: MinecraftInstance) -> None:
        self.navigate_to("home")
        self.pages["home"]._on_play_clicked()

    def _on_modpack_instance_created(self, instance: MinecraftInstance) -> None:
        self.pages["instances"].refresh_instances()
        self.pages["home"].refresh_instances_list()
        self.pages["home"].set_instance(instance)

    def _on_account_changed(self, account: Account) -> None:
        self.pages["home"].set_account(account)

    def _check_first_run(self) -> None:
        """Shows onboarding guide if no accounts exist."""
        accounts = self.token_store.get_all_accounts()
        if not accounts and not self.settings_mgr.settings.first_run_completed:
            self.after(300, self._show_first_run_dialog)

    def _show_first_run_dialog(self) -> None:
        dialog = ctk.CTkToplevel(self)
        dialog.title(f"Welcome to {APP_NAME}")
        dialog.geometry("540x440")
        dialog.transient(self)
        dialog.grab_set()
        dialog.resizable(False, False)

        ctk.CTkLabel(
            dialog,
            text=f"Welcome to {APP_NAME}!",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color=TEXT_COLOR
        ).pack(pady=(28, 8))

        ctk.CTkLabel(
            dialog,
            text="Get started by selecting how you would like to play Minecraft:\nSign in securely with Microsoft or create an Offline profile.",
            font=ctk.CTkFont(size=13),
            text_color=TEXT_MUTED_COLOR,
            justify="center"
        ).pack(padx=30, pady=(0, 24))

        btn_ms = ctk.CTkButton(
            dialog,
            text="Sign in with Microsoft (Official)",
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color=ACCENT_COLOR,
            hover_color=ACCENT_HOVER_COLOR,
            text_color="#022c22",
            height=44,
            command=lambda: (dialog.destroy(), self.navigate_to("accounts"), self.pages["accounts"]._start_microsoft_login())
        )
        btn_ms.pack(fill="x", padx=48, pady=(0, 12))

        btn_offline = ctk.CTkButton(
            dialog,
            text="Use Offline Mode",
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color=SURFACE_COLOR,
            hover_color=SURFACE_LIGHT_COLOR,
            border_width=1,
            border_color="#475569",
            height=44,
            command=lambda: (dialog.destroy(), self.navigate_to("accounts"), self.pages["accounts"]._show_offline_modal())
        )
        btn_offline.pack(fill="x", padx=48, pady=(0, 20))

        disc = ctk.CTkLabel(
            dialog,
            text="Offline Mode does not authenticate with Microsoft and is intended for local/testing use. Authenticated Microsoft profiles verify Minecraft ownership.",
            font=ctk.CTkFont(size=11),
            text_color=TEXT_MUTED_COLOR,
            wraplength=440,
            justify="center"
        )
        disc.pack(padx=40)

        self.settings_mgr.update(first_run_completed=True)

    def _schedule_startup_update_check(self) -> None:
        """Schedules a non-blocking background check for updates on startup."""
        self.after(1500, self._run_background_update_check)

    def _run_background_update_check(self) -> None:
        """Runs the update check against GitHub in a background thread."""
        import threading

        def worker() -> None:
            try:
                info = check_for_updates()
                if info.available:
                    self.after(0, lambda: self.show_update_modal(info))
            except Exception as e:
                logger.debug(f"Startup update check failed: {e}")

        threading.Thread(target=worker, daemon=True).start()

    def show_update_modal(self, info: UpdateInfo) -> None:
        """Displays modal offering to download and auto-replace the launcher files with the latest GitHub version."""
        dialog = ctk.CTkToplevel(self)
        dialog.title(f"Update Available - {APP_NAME}")
        dialog.geometry("520x360")
        dialog.transient(self)
        dialog.grab_set()
        dialog.resizable(False, False)

        header_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        header_frame.pack(fill="x", padx=24, pady=(20, 10))

        ctk.CTkLabel(
            header_frame,
            text="🚀 New Update Available!",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color=TEXT_COLOR
        ).pack(anchor="w")

        ctk.CTkLabel(
            header_frame,
            text=f"A new version of {APP_NAME} is available on GitHub.",
            font=ctk.CTkFont(size=12),
            text_color=TEXT_MUTED_COLOR
        ).pack(anchor="w", pady=(2, 0))

        info_card = ctk.CTkFrame(dialog, fg_color=SURFACE_COLOR, corner_radius=8)
        info_card.pack(fill="x", padx=24, pady=8)

        v_box = ctk.CTkFrame(info_card, fg_color="transparent")
        v_box.pack(fill="x", padx=16, pady=12)

        ctk.CTkLabel(
            v_box,
            text=f"Current: v{info.current_version}   ➔   Latest: v{info.latest_version}",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=ACCENT_COLOR
        ).pack(anchor="w")

        changelog_snippet = info.changelog.strip() if info.changelog else "Bug fixes and performance improvements."
        if len(changelog_snippet) > 160:
            changelog_snippet = changelog_snippet[:157] + "..."

        ctk.CTkLabel(
            v_box,
            text=f"{changelog_snippet}",
            font=ctk.CTkFont(size=12),
            text_color="#cbd5e1",
            wraplength=450,
            justify="left"
        ).pack(anchor="w", pady=(6, 0))

        status_lbl = ctk.CTkLabel(dialog, text="", font=ctk.CTkFont(size=12), text_color=TEXT_MUTED_COLOR)
        status_lbl.pack(fill="x", padx=24, pady=(4, 2))

        progress_bar = ctk.CTkProgressBar(dialog, height=10, fg_color=SURFACE_COLOR, progress_color=ACCENT_COLOR)
        progress_bar.set(0)

        btn_box = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_box.pack(fill="x", padx=24, pady=(12, 16), side="bottom")

        btn_cancel = ctk.CTkButton(
            btn_box,
            text="Later",
            width=100,
            height=36,
            fg_color=SURFACE_COLOR,
            hover_color=SURFACE_LIGHT_COLOR,
            command=dialog.destroy
        )
        btn_cancel.pack(side="left")

        def start_update() -> None:
            btn_cancel.configure(state="disabled")
            btn_update.configure(state="disabled", text="Updating...")
            progress_bar.pack(fill="x", padx=24, pady=(2, 10))
            status_lbl.configure(text="Downloading latest release from GitHub...")

            def progress_cb(frac: float, msg: str) -> None:
                self.after(0, lambda: (progress_bar.set(frac), status_lbl.configure(text=msg)))

            import threading

            def update_worker() -> None:
                success, msg = download_and_apply_update(info, progress_callback=progress_cb)

                def on_done() -> None:
                    if success:
                        status_lbl.configure(text=f"Update v{info.latest_version} applied! Restarting...", text_color="#34d399")
                        self.after(1200, restart_application)
                    else:
                        status_lbl.configure(text=f"Update error: {msg}", text_color="#ef4444")
                        btn_cancel.configure(state="normal", text="Close")
                        btn_update.configure(state="normal", text="Retry")

                self.after(0, on_done)

            threading.Thread(target=update_worker, daemon=True).start()

        btn_update = ctk.CTkButton(
            btn_box,
            text=f"Update to v{info.latest_version}",
            height=36,
            fg_color=ACCENT_COLOR,
            hover_color=ACCENT_HOVER_COLOR,
            text_color="#022c22",
            font=ctk.CTkFont(size=13, weight="bold"),
            command=start_update
        )
        btn_update.pack(side="right")

