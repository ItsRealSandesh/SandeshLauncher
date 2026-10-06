"""
Accounts Page for SandeshLauncher.
Supports Microsoft OAuth sign-in, separate Offline profile creation,
account switching, avatar display, and session management.
"""

import threading
import tkinter as tk
from tkinter import messagebox
from typing import Callable, Optional

import customtkinter as ctk
from PIL import Image

from auth.microsoft import MicrosoftAuthManager, APPROVAL_PENDING_MESSAGE
from auth.offline import create_offline_profile, OFFLINE_DISCLAIMER
from auth.token_store import Account, TokenStore
from config import ACCENT_COLOR, ACCENT_HOVER_COLOR, SURFACE_COLOR, SURFACE_LIGHT_COLOR, TEXT_COLOR, TEXT_MUTED_COLOR
from utils.logging import get_logger
from utils.avatar import get_player_avatar

logger = get_logger("ui_accounts")


class AccountsPage(ctk.CTkFrame):
    def __init__(self, parent: ctk.CTkBaseClass, token_store: TokenStore, on_account_changed: Optional[Callable[[Account], None]] = None):
        super().__init__(parent, fg_color="transparent")
        self.token_store = token_store
        self.on_account_changed = on_account_changed
        self.ms_auth = MicrosoftAuthManager()

        self._build_ui()
        self.refresh_accounts()

    def _build_ui(self) -> None:
        # Header
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.pack(fill="x", padx=30, pady=(24, 16))

        title = ctk.CTkLabel(
            header_frame,
            text="Account Manager",
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color=TEXT_COLOR
        )
        title.pack(side="left")

        # Action Buttons
        btn_box = ctk.CTkFrame(header_frame, fg_color="transparent")
        btn_box.pack(side="right")

        self.btn_offline = ctk.CTkButton(
            btn_box,
            text="+ Create Offline Profile",
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=SURFACE_COLOR,
            hover_color=SURFACE_LIGHT_COLOR,
            border_width=1,
            border_color="#475569",
            height=36,
            command=self._show_offline_modal
        )
        self.btn_offline.pack(side="right", padx=(8, 0))

        self.btn_ms = ctk.CTkButton(
            btn_box,
            text="Sign in with Microsoft",
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=ACCENT_COLOR,
            hover_color=ACCENT_HOVER_COLOR,
            text_color="#022c22",
            height=36,
            command=self._start_microsoft_login
        )
        self.btn_ms.pack(side="right")

        # Status / Notice Banner
        self.status_banner = ctk.CTkLabel(
            self,
            text="",
            font=ctk.CTkFont(size=12),
            text_color="#38bdf8",
            wraplength=700
        )
        self.status_banner.pack(fill="x", padx=30, pady=(0, 10))

        # Accounts List Scrollable Frame
        self.scroll_frame = ctk.CTkScrollableFrame(
            self,
            fg_color="transparent",
            corner_radius=12
        )
        self.scroll_frame.pack(fill="both", expand=True, padx=30, pady=(0, 24))

    def refresh_accounts(self) -> None:
        """Rerenders the saved accounts cards."""
        for widget in self.scroll_frame.winfo_children():
            widget.destroy()

        accounts = self.token_store.get_all_accounts()

        if not accounts:
            empty_card = ctk.CTkFrame(self.scroll_frame, fg_color=SURFACE_COLOR, corner_radius=12)
            empty_card.pack(fill="x", pady=20, padx=10, ipady=30)
            ctk.CTkLabel(
                empty_card,
                text="No accounts saved yet.\nClick 'Sign in with Microsoft' or 'Create Offline Profile' to begin.",
                font=ctk.CTkFont(size=14),
                text_color=TEXT_MUTED_COLOR,
                justify="center"
            ).pack()
            return

        for acc in accounts:
            self._render_account_card(acc)

    def _render_account_card(self, acc: Account) -> None:
        card = ctk.CTkFrame(
            self.scroll_frame,
            fg_color="#182234" if acc.is_active else SURFACE_COLOR,
            border_width=2 if acc.is_active else 1,
            border_color=ACCENT_COLOR if acc.is_active else "#334155",
            corner_radius=12
        )
        card.pack(fill="x", pady=6, padx=8, ipady=6)

        # Avatar
        avatar_path = get_player_avatar(acc.uuid, acc.skin_url, size=48)
        try:
            pil_img = Image.open(avatar_path)
            ctk_avatar = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(48, 48))
            img_lbl = ctk.CTkLabel(card, image=ctk_avatar, text="")
            img_lbl.image = ctk_avatar  # Prevent garbage collection
            img_lbl.pack(side="left", padx=16, pady=10)
        except Exception:
            pass

        # Text Details
        info_frame = ctk.CTkFrame(card, fg_color="transparent")
        info_frame.pack(side="left", fill="both", expand=True, pady=10)

        name_row = ctk.CTkFrame(info_frame, fg_color="transparent")
        name_row.pack(fill="x")

        name_lbl = ctk.CTkLabel(
            name_row,
            text=acc.username,
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=TEXT_COLOR
        )
        name_lbl.pack(side="left")

        # Badges
        is_ms = acc.account_type == "microsoft"
        type_badge = ctk.CTkLabel(
            name_row,
            text="Microsoft Account" if is_ms else "Offline Profile",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#6ee7b7" if is_ms else "#cbd5e1",
            fg_color="#064e3b" if is_ms else "#334155",
            corner_radius=6,
            padx=8,
            pady=2
        )
        type_badge.pack(side="left", padx=10)

        if acc.is_active:
            active_badge = ctk.CTkLabel(
                name_row,
                text="ACTIVE",
                font=ctk.CTkFont(size=10, weight="bold"),
                text_color="#064e3b",
                fg_color=ACCENT_COLOR,
                corner_radius=6,
                padx=8,
                pady=2
            )
            active_badge.pack(side="left")

        uuid_lbl = ctk.CTkLabel(
            info_frame,
            text=f"UUID: {acc.uuid}",
            font=ctk.CTkFont(size=11),
            text_color=TEXT_MUTED_COLOR
        )
        uuid_lbl.pack(anchor="w", pady=(2, 0))

        # Actions
        act_frame = ctk.CTkFrame(card, fg_color="transparent")
        act_frame.pack(side="right", padx=16)

        if not acc.is_active:
            use_btn = ctk.CTkButton(
                act_frame,
                text="Use",
                width=72,
                height=32,
                fg_color=ACCENT_COLOR,
                hover_color=ACCENT_HOVER_COLOR,
                text_color="#022c22",
                font=ctk.CTkFont(size=12, weight="bold"),
                command=lambda a_id=acc.id: self._set_active(a_id)
            )
            use_btn.pack(side="left", padx=4)

        del_btn = ctk.CTkButton(
            act_frame,
            text="Remove",
            width=72,
            height=32,
            fg_color="#334155",
            hover_color="#ef4444",
            text_color=TEXT_COLOR,
            font=ctk.CTkFont(size=12),
            command=lambda a_id=acc.id: self._remove_account(a_id)
        )
        del_btn.pack(side="left", padx=4)

    def _set_active(self, account_id: str) -> None:
        self.token_store.set_active_account(account_id)
        active = self.token_store.get_active_account()
        self.refresh_accounts()
        if self.on_account_changed and active:
            self.on_account_changed(active)

    def _remove_account(self, account_id: str) -> None:
        self.token_store.remove_account(account_id)
        active = self.token_store.get_active_account()
        self.refresh_accounts()
        if self.on_account_changed and active:
            self.on_account_changed(active)

    def _start_microsoft_login(self) -> None:
        self.btn_ms.configure(state="disabled", text="Signing in...")
        self.status_banner.configure(
            text="Opening your browser... Please complete sign-in on Microsoft's website.",
            text_color="#38bdf8"
        )

        def worker() -> None:
            try:
                acc = self.ms_auth.login(
                    progress_callback=lambda msg: self.after(0, lambda: self.status_banner.configure(text=msg))
                )
                self.token_store.add_or_update_account(acc)
                self.after(0, self._on_login_success, acc)
            except PermissionError as pe:
                self.after(0, self._on_login_permission_error, str(pe))
            except Exception as e:
                self.after(0, self._on_login_error, str(e))
            finally:
                self.after(0, lambda: self.btn_ms.configure(state="normal", text="Sign in with Microsoft"))

        threading.Thread(target=worker, daemon=True).start()

    def _on_login_success(self, account: Account) -> None:
        self.status_banner.configure(
            text=f"Welcome, {account.username}! Signed in with Microsoft successfully.",
            text_color="#34d399"
        )
        self.refresh_accounts()
        if self.on_account_changed:
            self.on_account_changed(account)

    def _on_login_permission_error(self, message: str) -> None:
        self.status_banner.configure(text=message, text_color="#fbbf24")
        messagebox.showinfo("Minecraft Services Notice", message)

    def _on_login_error(self, message: str) -> None:
        self.status_banner.configure(text=f"Login Error: {message}", text_color="#f87171")
        messagebox.showerror("Sign-in Failed", message)

    def _show_offline_modal(self) -> None:
        dialog = ctk.CTkToplevel(self)
        dialog.title("Create Offline Profile")
        dialog.geometry("460x340")
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()
        dialog.resizable(False, False)

        ctk.CTkLabel(
            dialog,
            text="Create Offline Profile",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=TEXT_COLOR
        ).pack(pady=(20, 8))

        disc = ctk.CTkLabel(
            dialog,
            text=OFFLINE_DISCLAIMER,
            font=ctk.CTkFont(size=11),
            text_color=TEXT_MUTED_COLOR,
            wraplength=400,
            justify="center"
        )
        disc.pack(padx=24, pady=(0, 16))

        entry_lbl = ctk.CTkLabel(
            dialog,
            text="Choose Username (3 - 16 characters):",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=TEXT_COLOR
        )
        entry_lbl.pack(anchor="w", padx=30, pady=(0, 4))

        username_entry = ctk.CTkEntry(
            dialog,
            placeholder_text="e.g. Steve",
            height=38,
            font=ctk.CTkFont(size=14)
        )
        username_entry.pack(fill="x", padx=30, pady=(0, 20))
        username_entry.focus()

        def do_create() -> None:
            name = username_entry.get().strip()
            try:
                acc = create_offline_profile(name)
                self.token_store.add_or_update_account(acc)
                dialog.destroy()
                self.refresh_accounts()
                if self.on_account_changed:
                    self.on_account_changed(acc)
            except Exception as e:
                messagebox.showerror("Invalid Username", str(e), parent=dialog)

        create_btn = ctk.CTkButton(
            dialog,
            text="Create Profile",
            fg_color=ACCENT_COLOR,
            hover_color=ACCENT_HOVER_COLOR,
            text_color="#022c22",
            height=38,
            font=ctk.CTkFont(size=13, weight="bold"),
            command=do_create
        )
        create_btn.pack(fill="x", padx=30)
