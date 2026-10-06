"""
Home Page for SandeshLauncher.
Main launch cockpit featuring player head, selected instance selector,
large glowing PLAY button, and real-time installation progress tracking.
"""

import threading
from typing import Callable, Optional

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
from instances.manager import InstanceManager
from instances.model import MinecraftInstance
from java.manager import JavaManager
from minecraft.launcher import MinecraftLauncher
from utils.logging import get_logger
from utils.settings import SettingsManager
from utils.avatar import get_player_avatar

logger = get_logger("ui_home")


class HomePage(ctk.CTkFrame):
    def __init__(
        self,
        parent: ctk.CTkBaseClass,
        token_store: TokenStore,
        instance_manager: InstanceManager,
        java_manager: JavaManager,
        launcher: MinecraftLauncher,
        on_navigate: Optional[Callable[[str], None]] = None,
    ):
        super().__init__(parent, fg_color="transparent")
        self.token_store = token_store
        self.instance_manager = instance_manager
        self.java_manager = java_manager
        self.launcher = launcher
        self.on_navigate = on_navigate
        self.settings_mgr = SettingsManager.get_instance()

        self.current_account: Optional[Account] = self.token_store.get_active_account()

        # Restore last selected instance instead of reverting to default
        pref_id = self.settings_mgr.settings.last_selected_instance_id or self.settings_mgr.settings.default_instance_id
        self.current_instance: Optional[MinecraftInstance] = self.instance_manager.get_preferred_instance(pref_id)

        self._build_ui()
        self.update_player_card()
        self.update_instance_card()

    def set_account(self, account: Account) -> None:
        self.current_account = account
        self.update_player_card()

    def set_instance(self, instance: MinecraftInstance) -> None:
        self.current_instance = instance
        self.settings_mgr.update(last_selected_instance_id=instance.id)
        if hasattr(self, "instance_combo"):
            self.instance_combo.set(instance.name)
        self.update_instance_card()

    def refresh_instances_list(self) -> None:
        instances = self.instance_manager.get_all()
        names = [i.name for i in instances] if instances else ["No Instances"]
        self.instance_combo.configure(values=names)

        pref_id = self.settings_mgr.settings.last_selected_instance_id or self.settings_mgr.settings.default_instance_id
        target = self.current_instance or self.instance_manager.get_preferred_instance(pref_id)

        if target and target.name in names:
            self.current_instance = target
            self.instance_combo.set(target.name)
        elif instances:
            self.current_instance = instances[0]
            self.instance_combo.set(instances[0].name)
            self.settings_mgr.update(last_selected_instance_id=self.current_instance.id)
        self.update_instance_card()

    def _build_ui(self) -> None:
        # Top banner with branding & player info
        top_banner = ctk.CTkFrame(self, fg_color=SURFACE_COLOR, corner_radius=14)
        top_banner.pack(fill="x", padx=20, pady=(12, 10), ipady=4)

        # Player Info (Left)
        self.player_box = ctk.CTkFrame(top_banner, fg_color="transparent")
        self.player_box.pack(side="left", padx=16, pady=6)

        self.avatar_label = ctk.CTkLabel(self.player_box, text="")
        self.avatar_label.pack(side="left", padx=(0, 12))

        p_info = ctk.CTkFrame(self.player_box, fg_color="transparent")
        p_info.pack(side="left")

        self.username_label = ctk.CTkLabel(
            p_info,
            text="Not Logged In",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=TEXT_COLOR
        )
        self.username_label.pack(anchor="w")

        self.acc_type_label = ctk.CTkLabel(
            p_info,
            text="No Account",
            font=ctk.CTkFont(size=11),
            text_color=TEXT_MUTED_COLOR
        )
        self.acc_type_label.pack(anchor="w")

        # Launcher Status (Right)
        status_box = ctk.CTkFrame(top_banner, fg_color="transparent")
        status_box.pack(side="right", padx=20)

        ctk.CTkLabel(
            status_box,
            text=f"{APP_NAME} v{APP_VERSION}",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=TEXT_COLOR
        ).pack(anchor="e")

        self.state_label = ctk.CTkLabel(
            status_box,
            text="Ready to Play",
            font=ctk.CTkFont(size=12),
            text_color="#34d399"
        )
        self.state_label.pack(anchor="e")

        # Central Instance Hero Card
        self.hero_card = ctk.CTkFrame(self, fg_color=SURFACE_COLOR, corner_radius=14)
        self.hero_card.pack(fill="both", expand=True, padx=20, pady=(0, 12), ipady=10)

        # Instance selector row inside Hero
        selector_row = ctk.CTkFrame(self.hero_card, fg_color="transparent")
        selector_row.pack(fill="x", padx=20, pady=(12, 6))

        ctk.CTkLabel(
            selector_row,
            text="Selected Instance:",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=TEXT_MUTED_COLOR
        ).pack(side="left")

        instances = self.instance_manager.get_all()
        names = [i.name for i in instances] if instances else ["No Instances"]

        self.instance_combo = ctk.CTkComboBox(
            selector_row,
            values=names,
            width=220,
            height=34,
            command=self._on_combo_instance_selected
        )
        if self.current_instance:
            self.instance_combo.set(self.current_instance.name)
        self.instance_combo.pack(side="left", padx=12)

        if self.on_navigate:
            new_inst_btn = ctk.CTkButton(
                selector_row,
                text="+ New Instance",
                height=34,
                fg_color="#334155",
                hover_color=SURFACE_LIGHT_COLOR,
                command=lambda: self.on_navigate("instances")
            )
            new_inst_btn.pack(side="left")

        # Instance Highlight Banner
        self.inst_banner = ctk.CTkFrame(self.hero_card, fg_color="#182234", corner_radius=10)
        self.inst_banner.pack(fill="x", padx=20, pady=(6, 10), ipady=8)

        self.inst_title = ctk.CTkLabel(
            self.inst_banner,
            text="Default Minecraft",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color=TEXT_COLOR
        )
        self.inst_title.pack(anchor="w", padx=16, pady=(6, 2))

        self.inst_details = ctk.CTkLabel(
            self.inst_banner,
            text="Minecraft 1.21.1  •  Fabric",
            font=ctk.CTkFont(size=12),
            text_color=ACCENT_COLOR
        )
        self.inst_details.pack(anchor="w", padx=16, pady=(0, 6))

        # Quick Actions inside Hero
        quick_row = ctk.CTkFrame(self.hero_card, fg_color="transparent")
        quick_row.pack(fill="x", padx=20, pady=(0, 10))

        if self.on_navigate:
            browse_mods_btn = ctk.CTkButton(
                quick_row,
                text="🌐 Browse Modrinth Mods",
                height=32,
                fg_color="#334155",
                hover_color=SURFACE_LIGHT_COLOR,
                command=lambda: self.on_navigate("mods")
            )
            browse_mods_btn.pack(side="left", padx=(0, 8))

            view_mods_btn = ctk.CTkButton(
                quick_row,
                text="🧩 Manage Installed Mods",
                height=32,
                fg_color="#334155",
                hover_color=SURFACE_LIGHT_COLOR,
                command=lambda: self.on_navigate("installed")
            )
            view_mods_btn.pack(side="left")

        # Progress Section
        self.progress_frame = ctk.CTkFrame(self.hero_card, fg_color="transparent")
        self.progress_frame.pack(fill="x", padx=20, pady=(0, 6))

        self.progress_label = ctk.CTkLabel(
            self.progress_frame,
            text="",
            font=ctk.CTkFont(size=12),
            text_color="#38bdf8"
        )
        self.progress_label.pack(anchor="w", pady=(0, 2))

        self.progress_bar = ctk.CTkProgressBar(
            self.progress_frame,
            height=7,
            progress_color=ACCENT_COLOR
        )
        self.progress_bar.set(0)
        self.progress_bar.pack(fill="x")
        self.progress_frame.pack_forget()

        # Giant PLAY Button
        self.play_button = ctk.CTkButton(
            self.hero_card,
            text="PLAY",
            font=ctk.CTkFont(size=20, weight="bold"),
            fg_color=ACCENT_COLOR,
            hover_color=ACCENT_HOVER_COLOR,
            text_color="#022c22",
            height=50,
            corner_radius=12,
            command=self._on_play_clicked
        )
        self.play_button.pack(fill="x", padx=20, pady=(6, 8))

    def _on_combo_instance_selected(self, choice: str) -> None:
        inst = self.instance_manager.get_by_name(choice)
        if inst:
            self.current_instance = inst
            self.settings_mgr.update(last_selected_instance_id=inst.id)
            self.update_instance_card()
            if hasattr(self, "on_instance_changed") and self.on_instance_changed:
                self.on_instance_changed(inst)

    def update_player_card(self) -> None:
        if self.current_account:
            self.username_label.configure(text=self.current_account.username)
            badge_text = "Microsoft Account" if self.current_account.account_type == "microsoft" else "Offline Profile"
            self.acc_type_label.configure(text=badge_text, text_color="#34d399" if self.current_account.account_type == "microsoft" else "#cbd5e1")

            avatar_path = get_player_avatar(self.current_account.uuid, self.current_account.skin_url, size=44)
            try:
                img = Image.open(avatar_path)
                ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(44, 44))
                self.avatar_label.configure(image=ctk_img)
                self.avatar_label.image = ctk_img
            except Exception:
                pass
        else:
            self.username_label.configure(text="No Account")
            self.acc_type_label.configure(text="Please sign in or create offline profile")

    def update_instance_card(self) -> None:
        if self.current_instance:
            self.inst_title.configure(text=self.current_instance.name)
            self.inst_details.configure(
                text=f"Minecraft {self.current_instance.minecraft_version}  •  {self.current_instance.loader.upper()}  •  {self.current_instance.max_ram_mb} MB RAM"
            )
            self.play_button.configure(state="normal", text="PLAY", fg_color=ACCENT_COLOR)
        else:
            self.inst_title.configure(text="No Instance Selected")
            self.inst_details.configure(text="Create an instance in the Instances tab")
            self.play_button.configure(state="disabled", text="NO INSTANCE")

    def _on_play_clicked(self) -> None:
        if self.launcher.is_running:
            # Terminate running game
            self.launcher.terminate()
            self.play_button.configure(text="PLAY", fg_color=ACCENT_COLOR)
            self.state_label.configure(text="Stopped", text_color=TEXT_MUTED_COLOR)
            return

        if not self.current_account:
            if self.on_navigate:
                self.on_navigate("accounts")
            return

        if not self.current_instance:
            if self.on_navigate:
                self.on_navigate("instances")
            return

        # Start Launch Workflow
        self.play_button.configure(state="disabled", text="Preparing...")
        self.progress_frame.pack(fill="x", padx=30, pady=(0, 10))
        self.progress_bar.set(0)
        self.progress_label.configure(text="Preparing launch sequence...")
        self.state_label.configure(text="Preparing...", text_color="#38bdf8")

        def worker() -> None:
            try:
                # Progress handler
                def on_progress(status_text: str, current: int, maximum: int) -> None:
                    pct = (current / maximum) if maximum > 0 else 0.0
                    self.after(0, lambda s=status_text, p=pct: self._update_progress_ui(s, p))

                # Launch game
                self.launcher.launch(
                    instance=self.current_instance,
                    account=self.current_account,
                    status_callback=lambda s: self.after(0, lambda msg=s: self.state_label.configure(text=msg)),
                    progress_callback=on_progress,
                    on_start=self._on_game_started,
                    on_exit=self._on_game_exited,
                )
            except Exception as e:
                err_msg = str(e)
                self.after(0, lambda msg=err_msg: self._on_launch_failed(msg))

        threading.Thread(target=worker, daemon=True).start()

    def _update_progress_ui(self, status: str, pct: float) -> None:
        self.progress_label.configure(text=status)
        self.progress_bar.set(pct)

    def _on_game_started(self) -> None:
        self.after(0, self._handle_game_started_ui)

    def _handle_game_started_ui(self) -> None:
        self.state_label.configure(text="Minecraft Running", text_color="#34d399")
        self.play_button.configure(
            state="normal",
            text="Stop Minecraft",
            fg_color="#ef4444",
            hover_color="#dc2626"
        )
        self.progress_frame.pack_forget()

        # Handle window minimize/close if configured
        settings = SettingsManager.get_instance().settings
        toplevel = self.winfo_toplevel()
        if settings.close_on_launch == "minimize":
            toplevel.iconify()
        elif settings.close_on_launch == "close":
            toplevel.destroy()

    def _on_game_exited(self, returncode: int) -> None:
        self.after(0, lambda rc=returncode: self._handle_game_exited_ui(rc))

    def _handle_game_exited_ui(self, returncode: int) -> None:
        if returncode == 0:
            self.state_label.configure(text="Ready to Play", text_color="#34d399")
        else:
            self.state_label.configure(text=f"Game Exited (Code {returncode})", text_color="#f87171")
        self.play_button.configure(state="normal", text="PLAY", fg_color=ACCENT_COLOR, hover_color=ACCENT_HOVER_COLOR)
        self.progress_frame.pack_forget()
        if self.current_instance:
            self.instance_manager.save(self.current_instance)

        # Restore launcher window to desktop fit if minimized
        settings = SettingsManager.get_instance().settings
        if settings.close_on_launch == "minimize":
            try:
                toplevel = self.winfo_toplevel()
                toplevel.deiconify()
                from utils.screen import apply_desktop_window_fit
                apply_desktop_window_fit(toplevel, maximize=(settings.window_mode != "windowed"))
            except Exception:
                pass

    def _on_launch_failed(self, error_message: str) -> None:
        self.state_label.configure(text="Launch Failed", text_color="#f87171")
        self.play_button.configure(state="normal", text="PLAY", fg_color=ACCENT_COLOR)
        self.progress_frame.pack_forget()
        import tkinter.messagebox as mb
        mb.showerror("Launch Error", f"Failed to launch Minecraft:\n\n{error_message}")
