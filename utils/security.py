"""
Security utilities for SandeshLauncher.
Includes token redaction, safe zip extraction (ZipSlip defense),
file permissions, and PKCE cryptographic helpers.
"""

import base64
import hashlib
import os
import re
import secrets
import sys
import zipfile
from pathlib import Path
from typing import Union, List

# Patterns matching sensitive authentication tokens
SENSITIVE_PATTERNS = [
    # OAuth bearer tokens and access tokens
    re.compile(r"(Bearer\s+)[A-Za-z0-9\-._~+/]+=*", re.IGNORECASE),
    re.compile(r"(--accessToken\s+)[^\s]+", re.IGNORECASE),
    re.compile(r"(--uuid\s+)[0-9a-fA-F\-]{32,36}", re.IGNORECASE),
    re.compile(r"('access_token':\s*['\"])[^'\"]+(['\"])", re.IGNORECASE),
    re.compile(r"('refresh_token':\s*['\"])[^'\"]+(['\"])", re.IGNORECASE),
    re.compile(r'("access_token":\s*")[^"]+(")', re.IGNORECASE),
    re.compile(r'("refresh_token":\s*")[^"]+(")', re.IGNORECASE),
    re.compile(r"(client_secret=[^&\s]+)", re.IGNORECASE),
    re.compile(r"(code=[a-zA-Z0-9_\-\.]+)", re.IGNORECASE),
    re.compile(r"(X-Xbl-Contract-Version:[^\n]+)", re.IGNORECASE),
    re.compile(r"(Authorization:\s*)[^\n\r]+", re.IGNORECASE),
    re.compile(r"(uhs=[a-zA-Z0-9_\-\.]+)", re.IGNORECASE),
]


def redact_sensitive_text(text: str) -> str:
    """Replaces any sensitive tokens, codes, or secrets with [REDACTED]."""
    if not text:
        return text
    redacted = text
    for pattern in SENSITIVE_PATTERNS:
        # If group matches exist, replace value inside
        try:
            redacted = pattern.sub(r"\g<1>[REDACTED]\g<2>" if pattern.groups >= 2 else r"\g<1>[REDACTED]", redacted)
        except Exception:
            redacted = pattern.sub("[REDACTED]", redacted)
    return redacted


def secure_write_file(filepath: Union[str, Path], content: str, mode: int = 0o600) -> None:
    """
    Writes content to a file with restricted permissions (0600 on Unix)
    preventing unauthorized users on the same machine from reading it.
    """
    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(".tmp")
    
    # Create with restricted permissions
    if sys.platform != "win32":
        # Open with explicit file descriptor and mode
        fd = os.open(temp_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, mode)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
    else:
        with open(temp_path, "w", encoding="utf-8") as f:
            f.write(content)

    temp_path.replace(path)


def safe_extract_zip(zip_path: Union[str, Path], target_dir: Union[str, Path], strip_top_dir: bool = False) -> List[Path]:
    """
    Safely extracts a ZIP archive, verifying every entry is strictly inside target_dir.
    Prevents directory traversal (ZipSlip vulnerability).
    """
    target = Path(target_dir).resolve()
    target.mkdir(parents=True, exist_ok=True)
    extracted_files: List[Path] = []

    with zipfile.ZipFile(zip_path, 'r') as archive:
        for member in archive.infolist():
            member_path = member.filename
            if strip_top_dir and "/" in member_path:
                parts = member_path.split("/", 1)
                if not parts[1]:
                    continue
                member_path = parts[1]

            dest_path = (target / member_path).resolve()
            try:
                dest_path.relative_to(target)
            except ValueError:
                raise ValueError(f"Security Exception: Zip archive member '{member.filename}' escapes target directory '{target}'")

            if member.is_dir():
                dest_path.mkdir(parents=True, exist_ok=True)
            else:
                dest_path.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(member) as source, open(dest_path, "wb") as output:
                    output.write(source.read())
                extracted_files.append(dest_path)

    return extracted_files


def generate_pkce_pair() -> tuple[str, str]:
    """
    Generates a secure PKCE code verifier and SHA-256 code challenge.
    Returns: (code_verifier, code_challenge)
    """
    # 64 random bytes -> 86 base64url characters
    code_verifier = secrets.token_urlsafe(64)
    # SHA256 of verifier
    sha256_digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    # Base64url encode without trailing '='
    code_challenge = base64.urlsafe_b64encode(sha256_digest).decode("ascii").rstrip("=")
    return code_verifier, code_challenge


def generate_state() -> str:
    """Generates a secure cryptographically random state parameter for OAuth."""
    return secrets.token_urlsafe(32)
