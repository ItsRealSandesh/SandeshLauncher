"""
Microsoft OAuth 2.0 and Minecraft Services authentication for SandeshLauncher.
Implements PKCE, state validation, automatic localhost callback server,
and specific handling for pending Minecraft Services App ID approval.
"""

import http.server
import socket
import threading
import time
import urllib.parse
import webbrowser
from datetime import datetime
from typing import Callable, Optional, Tuple, Dict, Any

import minecraft_launcher_lib.microsoft_account as mla
from minecraft_launcher_lib.exceptions import (
    AccountNotOwnMinecraft,
    AzureAppNotPermitted,
    InvalidRefreshToken,
)

from auth.token_store import Account
from config import MICROSOFT_CLIENT_ID
from utils.logging import get_logger

logger = get_logger("auth_microsoft")

APPROVAL_PENDING_MESSAGE = (
    "SandeshLauncher is waiting for Minecraft Services approval.\n\n"
    "Your Microsoft sign-in succeeded, but this SandeshLauncher application "
    "has not yet been permitted to access Minecraft Services.\n\n"
    "Please try again after the application's Minecraft API approval is completed."
)

NO_OWNERSHIP_MESSAGE = (
    "Your Microsoft account does not own Minecraft Java Edition.\n\n"
    "A Minecraft Java Edition license is required to play with an authenticated Microsoft account.\n"
    "If you wish to test or play on offline servers, you can use Offline Mode instead."
)


class OAuthCallbackHandler(http.server.BaseHTTPRequestHandler):
    """Temporary HTTP handler to capture authorization code and state from browser redirect."""
    server: "OAuthCallbackServer"

    def log_message(self, format: str, *args: Any) -> None:
        # Suppress standard HTTP server console spam
        pass

    def do_GET(self) -> None:
        parsed_url = urllib.parse.urlparse(self.path)
        query = urllib.parse.parse_qs(parsed_url.query)

        code = query.get("code", [None])[0]
        state = query.get("state", [None])[0]
        error = query.get("error", [None])[0]
        error_description = query.get("error_description", [None])[0]

        if error:
            self.server.auth_error = f"{error}: {error_description or 'Authentication was cancelled or denied.'}"
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            html = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="utf-8">
                <title>SandeshLauncher - Login Failed</title>
                <style>
                    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0f172a; color: #f8fafc; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; }}
                    .card {{ background: #1e293b; padding: 40px; border-radius: 16px; border: 1px solid #ef4444; max-width: 480px; text-align: center; box-shadow: 0 10px 25px rgba(0,0,0,0.5); }}
                    h2 {{ color: #ef4444; margin-bottom: 12px; }}
                    p {{ color: #94a3b8; line-height: 1.5; }}
                </style>
            </head>
            <body>
                <div class="card">
                    <h2>Sign-in Cancelled</h2>
                    <p>{self.server.auth_error}</p>
                    <p>You can close this window and return to SandeshLauncher.</p>
                </div>
            </body>
            </html>
            """
            self.wfile.write(html.encode("utf-8"))
            return

        if code:
            self.server.auth_code = code
            self.server.auth_state = state
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            html = """
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="utf-8">
                <title>SandeshLauncher - Login Successful</title>
                <style>
                    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0f172a; color: #f8fafc; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; }
                    .card { background: #1e293b; padding: 40px; border-radius: 16px; border: 1px solid #10b981; max-width: 480px; text-align: center; box-shadow: 0 10px 25px rgba(0,0,0,0.5); }
                    .badge { background: #10b981; color: #064e3b; font-weight: bold; padding: 6px 16px; border-radius: 999px; display: inline-block; margin-bottom: 16px; }
                    h2 { margin: 8px 0; color: #f8fafc; }
                    p { color: #94a3b8; line-height: 1.5; }
                </style>
            </head>
            <body>
                <div class="card">
                    <div class="badge">Connected</div>
                    <h2>SandeshLauncher</h2>
                    <p>Authentication was successful! You can now safely close this browser tab and return to the launcher.</p>
                </div>
            </body>
            </html>
            """
            self.wfile.write(html.encode("utf-8"))
        else:
            self.send_response(400)
            self.end_headers()


class OAuthCallbackServer(http.server.HTTPServer):
    def __init__(self, server_address: Tuple[str, int]):
        super().__init__(server_address, OAuthCallbackHandler)
        self.auth_code: Optional[str] = None
        self.auth_state: Optional[str] = None
        self.auth_error: Optional[str] = None


def find_free_port() -> int:
    """Finds an unused TCP port on localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class MicrosoftAuthManager:
    def __init__(self, client_id: str = MICROSOFT_CLIENT_ID):
        self.client_id = client_id

    def login(
        self,
        progress_callback: Optional[Callable[[str], None]] = None,
        timeout_seconds: int = 180
    ) -> Account:
        """
        Executes complete automated Microsoft login:
        1. Allocates free local port and starts temporary callback server
        2. Generates PKCE pair and state
        3. Opens system browser
        4. Waits for localhost callback
        5. Validates state
        6. Exchanges auth code for Minecraft profile and session
        """
        port = find_free_port()
        redirect_uri = f"http://localhost:{port}"

        if progress_callback:
            progress_callback("Preparing Microsoft secure authentication...")

        login_url, expected_state, code_verifier = mla.get_secure_login_data(
            self.client_id,
            redirect_uri
        )

        server = OAuthCallbackServer(("127.0.0.1", port))
        server_thread = threading.Thread(target=server.serve_forever, daemon=True)
        server_thread.start()

        try:
            logger.info(f"Opening browser for Microsoft OAuth: {redirect_uri}")
            if progress_callback:
                progress_callback("Opening browser for Microsoft sign-in...")

            opened = webbrowser.open(login_url)
            if not opened:
                logger.warning("Default browser could not be automatically launched.")

            if progress_callback:
                progress_callback("Waiting for sign-in completion in browser...")

            # Wait for callback
            start_time = time.time()
            while server.auth_code is None and server.auth_error is None:
                if time.time() - start_time > timeout_seconds:
                    raise TimeoutError("Sign-in timed out. Please try again.")
                time.sleep(0.5)

            if server.auth_error:
                raise RuntimeError(server.auth_error)

            # Validate State
            if server.auth_state != expected_state:
                raise ValueError("Security verification failed: OAuth state mismatch.")

            auth_code = server.auth_code
            if not auth_code:
                raise ValueError("No authorization code received.")

        finally:
            server.shutdown()
            server.server_close()

        # Exchange authorization code for Minecraft session
        if progress_callback:
            progress_callback("Authenticating with Minecraft Services...")

        try:
            login_data = mla.complete_login(
                client_id=self.client_id,
                client_secret=None,
                redirect_uri=redirect_uri,
                auth_code=auth_code,
                code_verifier=code_verifier
            )
        except AzureAppNotPermitted:
            logger.warning("Minecraft Services returned AzureAppNotPermitted.")
            raise PermissionError(APPROVAL_PENDING_MESSAGE)
        except AccountNotOwnMinecraft:
            logger.warning("Microsoft account does not own Minecraft Java Edition.")
            raise PermissionError(NO_OWNERSHIP_MESSAGE)
        except Exception as e:
            err_str = str(e)
            if "AzureAppNotPermitted" in err_str or "403" in err_str:
                raise PermissionError(APPROVAL_PENDING_MESSAGE)
            logger.error(f"Failed to complete Microsoft login: {e}")
            raise RuntimeError(f"Authentication failed: {e}")

        # Construct Account
        username = login_data.get("name", "Player")
        user_uuid = login_data.get("id", "")
        access_token = login_data.get("access_token", "")
        refresh_token = login_data.get("refresh_token", "")

        # Try to extract skin url
        skin_url = None
        skins = login_data.get("skins", [])
        if skins and isinstance(skins, list):
            for s in skins:
                if s.get("state") == "ACTIVE":
                    skin_url = s.get("url")
                    break
            if not skin_url and skins:
                skin_url = skins[0].get("url")

        expires_in = login_data.get("expires_in", 86400)
        expires_at = datetime.now().timestamp() + expires_in

        account = Account(
            id=f"ms_{user_uuid}",
            account_type="microsoft",
            username=username,
            uuid=user_uuid,
            skin_url=skin_url,
            avatar_path=None,
            access_token=access_token,
            refresh_token=refresh_token,
            token_expires_at=expires_at,
            is_active=True,
            created_at=datetime.now().isoformat()
        )

        logger.info(f"Successfully authenticated Microsoft user: {username} ({user_uuid})")
        return account

    def refresh_account(self, account: Account) -> bool:
        """Refreshes an expired Microsoft session using its refresh token."""
        if account.account_type != "microsoft" or not account.refresh_token:
            return False

        try:
            logger.info(f"Refreshing token for {account.username}...")
            new_data = mla.complete_refresh(
                client_id=self.client_id,
                client_secret=None,
                redirect_uri=None,
                refresh_token=account.refresh_token
            )
            account.access_token = new_data.get("access_token")
            account.refresh_token = new_data.get("refresh_token") or account.refresh_token
            expires_in = new_data.get("expires_in", 86400)
            account.token_expires_at = datetime.now().timestamp() + expires_in
            logger.info(f"Token refresh successful for {account.username}")
            return True
        except (InvalidRefreshToken, AzureAppNotPermitted, Exception) as e:
            logger.warning(f"Could not refresh token for {account.username}: {e}")
            return False
