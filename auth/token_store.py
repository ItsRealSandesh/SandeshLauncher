"""
Secure token and account persistence store for SandeshLauncher.
Uses OS keyring when available, with a fallback to restricted-permission files (0600).
"""

import json
import os
import sys
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

try:
    import keyring
    HAS_KEYRING = True
except ImportError:
    keyring = None
    HAS_KEYRING = False

from config import APP_NAME
from utils.logging import get_logger
from utils.paths import get_auth_dir
from utils.security import secure_write_file

logger = get_logger("token_store")

KEYRING_SERVICE_NAME = f"{APP_NAME}_Auth"


@dataclass
class Account:
    id: str
    account_type: str  # "microsoft" or "offline"
    username: str
    uuid: str
    skin_url: Optional[str] = None
    avatar_path: Optional[str] = None
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    token_expires_at: Optional[float] = None
    is_active: bool = False
    created_at: str = ""

    def is_token_expired(self) -> bool:
        if self.account_type == "offline":
            return False
        if not self.token_expires_at:
            return True
        # Consider expired 5 minutes before actual expiration
        return datetime.now().timestamp() >= (self.token_expires_at - 300)

    def to_dict(self, include_tokens: bool = False) -> Dict[str, Any]:
        data = asdict(self)
        if not include_tokens:
            data.pop("access_token", None)
            data.pop("refresh_token", None)
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Account":
        valid_keys = cls.__dataclass_fields__.keys()
        filtered = {k: v for k, v in data.items() if k in valid_keys}
        return cls(**filtered)


class TokenStore:
    def __init__(self):
        self.auth_dir = get_auth_dir()
        self.accounts_file = self.auth_dir / "accounts.json"
        self._accounts: Dict[str, Account] = {}
        self.load_accounts()

    def _save_secret_to_keyring(self, key: str, secret: str) -> bool:
        """Attempts to store secret in OS keyring."""
        if not HAS_KEYRING or keyring is None:
            return False
        try:
            keyring.set_password(KEYRING_SERVICE_NAME, key, secret)
            return True
        except Exception as e:
            logger.debug(f"Keyring write not available: {e}")
            return False

    def _load_secret_from_keyring(self, key: str) -> Optional[str]:
        """Attempts to retrieve secret from OS keyring."""
        if not HAS_KEYRING or keyring is None:
            return None
        try:
            return keyring.get_password(KEYRING_SERVICE_NAME, key)
        except Exception as e:
            logger.debug(f"Keyring read not available: {e}")
            return None

    def _delete_secret_from_keyring(self, key: str) -> None:
        if not HAS_KEYRING or keyring is None:
            return
        try:
            keyring.delete_password(KEYRING_SERVICE_NAME, key)
        except Exception:
            pass

    def load_accounts(self) -> List[Account]:
        self._accounts.clear()
        if not self.accounts_file.exists():
            return []

        try:
            with open(self.accounts_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            for acc_data in data.get("accounts", []):
                acc = Account.from_dict(acc_data)
                # Attempt to restore refresh/access token from keyring or stored fallback
                kr_refresh = self._load_secret_from_keyring(f"{acc.id}_refresh_token")
                kr_access = self._load_secret_from_keyring(f"{acc.id}_access_token")

                if kr_refresh:
                    acc.refresh_token = kr_refresh
                if kr_access:
                    acc.access_token = kr_access

                self._accounts[acc.id] = acc

            logger.info(f"Loaded {len(self._accounts)} account(s) from secure store.")
        except Exception as e:
            logger.error(f"Failed to load accounts: {e}")

        return list(self._accounts.values())

    def save_accounts(self) -> None:
        """Persists accounts, storing tokens securely."""
        try:
            serialized_list = []
            for acc in self._accounts.values():
                use_keyring = False
                if acc.refresh_token:
                    use_keyring = self._save_secret_to_keyring(f"{acc.id}_refresh_token", acc.refresh_token)
                if acc.access_token:
                    self._save_secret_to_keyring(f"{acc.id}_access_token", acc.access_token)

                # If keyring is available, strip tokens from json. Otherwise write with 0600 mode.
                data = acc.to_dict(include_tokens=not use_keyring)
                serialized_list.append(data)

            payload = {"accounts": serialized_list}
            secure_write_file(self.accounts_file, json.dumps(payload, indent=2))
        except Exception as e:
            logger.error(f"Failed to persist accounts: {e}")

    def add_or_update_account(self, account: Account) -> None:
        # If this is the only account or set active, update others
        if account.is_active or len(self._accounts) == 0:
            account.is_active = True
            for a in self._accounts.values():
                if a.id != account.id:
                    a.is_active = False

        self._accounts[account.id] = account
        self.save_accounts()

    def set_active_account(self, account_id: str) -> bool:
        if account_id not in self._accounts:
            return False
        for a in self._accounts.values():
            a.is_active = (a.id == account_id)
        self.save_accounts()
        return True

    def get_active_account(self) -> Optional[Account]:
        for a in self._accounts.values():
            if a.is_active:
                return a
        # Fallback to first if none active
        if self._accounts:
            first = next(iter(self._accounts.values()))
            first.is_active = True
            self.save_accounts()
            return first
        return None

    def get_account(self, account_id: str) -> Optional[Account]:
        return self._accounts.get(account_id)

    def get_all_accounts(self) -> List[Account]:
        return list(self._accounts.values())

    def remove_account(self, account_id: str) -> bool:
        if account_id in self._accounts:
            self._delete_secret_from_keyring(f"{account_id}_refresh_token")
            self._delete_secret_from_keyring(f"{account_id}_access_token")
            del self._accounts[account_id]
            if self._accounts and not any(a.is_active for a in self._accounts.values()):
                next(iter(self._accounts.values())).is_active = True
            self.save_accounts()
            logger.info(f"Removed account {account_id}")
            return True
        return False
