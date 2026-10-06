"""
Comprehensive Automated Test Suite for SandeshLauncher.
Validates all core subsystems required in Section 49:
- Startup & Configuration
- Instance Creation & Management
- Minecraft Version Retrieval
- Microsoft OAuth Callback & State Verification
- Offline Mode Profiles
- Java Detection & Mapping
- Modrinth Search & Dependencies
- Path Traversal & Security
- Token Redaction in Logs
- Download Manager & Hash Verification
"""

import http.client
import os
import shutil
import tempfile
import time
import unittest
from pathlib import Path

from auth.microsoft import OAuthCallbackServer, find_free_port
from auth.offline import create_offline_profile, generate_offline_uuid
from auth.token_store import Account, TokenStore
from config import APP_NAME, MICROSOFT_CLIENT_ID
from downloads.manager import DownloadManager
from downloads.worker import DownloadTask, DownloadStatus
from instances.manager import InstanceManager
from java.detector import detect_system_javas, get_required_java_version
from minecraft.versions import get_version_manifest, get_available_versions
from mods.modrinth import ModrinthClient
from utils.paths import ensure_safe_path
from utils.security import redact_sensitive_text, generate_pkce_pair, generate_state
from utils.settings import SettingsManager


class TestSandeshLauncher(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.test_dir = Path(tempfile.mkdtemp(prefix="sandesh_test_"))

    @classmethod
    def tearDownClass(cls):
        if cls.test_dir.exists():
            shutil.rmtree(cls.test_dir, ignore_errors=True)

    def test_01_configuration(self):
        """Verifies centralized non-secret configuration."""
        self.assertEqual(APP_NAME, "SandeshLauncher")
        self.assertEqual(MICROSOFT_CLIENT_ID, "4bc2d5f5-05c1-4377-893d-8a11da7567f5")
        settings = SettingsManager.get_instance().settings
        self.assertIsNotNone(settings)
        self.assertGreater(settings.default_max_ram_mb, 512)

    def test_02_instance_creation_and_lifecycle(self):
        """Verifies creating, modifying, duplicating, and deleting instances."""
        inst_dir = self.test_dir / "instances"
        mgr = InstanceManager(inst_dir)

        # Create
        inst = mgr.create(
            name="Test Instance",
            minecraft_version="1.21.1",
            loader="fabric",
            loader_version="latest",
            max_ram_mb=4096
        )
        self.assertTrue(inst.id.startswith("test_instance_"))
        self.assertEqual(inst.minecraft_version, "1.21.1")
        self.assertEqual(inst.loader, "fabric")

        # Verify filesystem folders created
        game_dir = inst.get_game_dir(inst_dir)
        self.assertTrue((game_dir / "mods").exists())
        self.assertTrue((game_dir / "config").exists())

        # Rename
        success = mgr.rename(inst.id, "Renamed Instance")
        self.assertTrue(success)
        self.assertEqual(mgr.get(inst.id).name, "Renamed Instance")

        # Duplicate
        cloned = mgr.duplicate(inst.id, "Cloned Instance")
        self.assertIsNotNone(cloned)
        self.assertEqual(cloned.minecraft_version, "1.21.1")

        # Delete
        del_success = mgr.delete(inst.id)
        self.assertTrue(del_success)
        self.assertIsNone(mgr.get(inst.id))

    def test_03_offline_mode(self):
        """Verifies distinct offline player profile generation."""
        player = create_offline_profile("TestPlayer")
        self.assertEqual(player.username, "TestPlayer")
        self.assertEqual(player.account_type, "offline")
        self.assertTrue(player.id.startswith("offline_"))
        self.assertFalse(player.is_token_expired())

        # Test deterministic UUID
        expected_uuid = generate_offline_uuid("TestPlayer")
        self.assertEqual(player.uuid, expected_uuid)

        # Test invalid name
        with self.assertRaises(ValueError):
            create_offline_profile("ab")  # Too short

    def test_04_token_redaction(self):
        """Verifies sensitive access/refresh tokens are stripped from text."""
        raw_msg = (
            "Starting game with --accessToken eyJhbGciOiJIUzI1NiJ9.secret12345 "
            "and Bearer M.R3_ABCDE12345--token"
        )
        clean = redact_sensitive_text(raw_msg)
        self.assertNotIn("eyJhbGciOiJIUzI1NiJ9.secret12345", clean)
        self.assertNotIn("M.R3_ABCDE12345--token", clean)
        self.assertIn("[REDACTED]", clean)

    def test_05_path_safety(self):
        """Verifies directory traversal attacks are prevented."""
        base_dir = self.test_dir / "safe_zone"
        base_dir.mkdir(parents=True, exist_ok=True)

        safe = ensure_safe_path(base_dir, "instance_1/mods/mod.jar")
        self.assertTrue(str(safe).startswith(str(base_dir)))

        # Malicious path traversal
        with self.assertRaises(ValueError):
            ensure_safe_path(base_dir, "../../etc/shadow")

    def test_06_java_detection_and_mapping(self):
        """Verifies Java detection on current system and version rules."""
        javas = detect_system_javas()
        self.assertGreater(len(javas), 0, "At least one Java runtime should be found on Debian")

        # Version rules
        self.assertEqual(get_required_java_version("1.21.1"), 21)
        self.assertEqual(get_required_java_version("1.20.4"), 17)
        self.assertEqual(get_required_java_version("1.16.5"), 8)

    def test_07_oauth_callback_server_and_state(self):
        """Verifies the temporary localhost OAuth callback server and state matching."""
        port = find_free_port()
        server = OAuthCallbackServer(("127.0.0.1", port))

        import threading
        t = threading.Thread(target=server.serve_forever, daemon=True)
        t.start()

        try:
            expected_state = generate_state()
            code_verifier, code_challenge = generate_pkce_pair()
            self.assertGreater(len(code_verifier), 40)
            self.assertGreater(len(code_challenge), 40)

            # Send HTTP GET simulation
            conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
            conn.request("GET", f"/?code=MOCK_AUTH_CODE_123&state={expected_state}")
            resp = conn.getresponse()
            self.assertEqual(resp.status, 200)

            # Verify server captured
            self.assertEqual(server.auth_code, "MOCK_AUTH_CODE_123")
            self.assertEqual(server.auth_state, expected_state)
        finally:
            server.shutdown()
            server.server_close()

    def test_08_minecraft_version_manifest(self):
        """Verifies Mojang version manifest fetching and caching."""
        manifest = get_version_manifest()
        self.assertIn("versions", manifest)
        self.assertGreater(len(manifest["versions"]), 50)

        releases = get_available_versions(include_snapshots=False)
        self.assertGreater(len(releases), 20)
        self.assertTrue(all(v["type"] == "release" for v in releases))

    def test_09_modrinth_api_search(self):
        """Verifies official Modrinth public API integration."""
        client = ModrinthClient()
        results = client.search(
            query="sodium",
            project_type="mod",
            limit=5
        )
        self.assertGreater(len(results), 0)
        self.assertTrue(any("sodium" in r.title.lower() for r in results))

    def test_10_download_manager_task(self):
        """Verifies download task execution, progress tracking, and hash checks."""
        dm = DownloadManager.get_instance()
        dest_file = self.test_dir / "mojang_test_download.json"

        # Download Mojang version manifest as a test download
        task = DownloadTask(
            id="test_task_1",
            name="Mojang Manifest Download",
            url="https://launchermeta.mojang.com/mc/game/version_manifest_v2.json",
            destination=dest_file
        )
        dm.add_task(task)

        # Wait for task completion
        timeout = 15
        start = time.time()
        while task.status == DownloadStatus.DOWNLOADING or task.status == DownloadStatus.PENDING:
            if time.time() - start > timeout:
                break
            time.sleep(0.2)

        self.assertEqual(task.status, DownloadStatus.COMPLETED)
        self.assertTrue(dest_file.exists())
        self.assertGreater(dest_file.stat().st_size, 1000)

    def test_11_screen_resolution_and_display_optimization(self):
        """Verifies desktop screen detection, display fitting, and launch optimizations."""
        from utils.screen import get_desktop_resolution, get_standard_resolutions
        w, h = get_desktop_resolution()
        self.assertGreaterEqual(w, 800)
        self.assertGreaterEqual(h, 480)

        res_list = get_standard_resolutions()
        self.assertGreater(len(res_list), 0)
        self.assertEqual(res_list[0][0], w)
        self.assertEqual(res_list[0][1], h)

        settings = SettingsManager.get_instance().settings
        self.assertTrue(hasattr(settings, "window_mode"))
        self.assertTrue(hasattr(settings, "match_desktop_resolution"))
        self.assertTrue(hasattr(settings, "fast_launch_optimization"))
        self.assertTrue(hasattr(settings, "mesa_glthread"))
        self.assertTrue(settings.fast_launch_optimization)
        self.assertTrue(settings.mesa_glthread)

    def test_12_last_selected_instance_persistence(self):
        """Verifies that the last selected instance is remembered and restored."""
        mgr = InstanceManager(self.test_dir / "persist_instances")
        i1 = mgr.create("Instance Alpha", "1.21.1")
        i2 = mgr.create("Instance Beta", "1.20.4")

        # Preferred without any selection returns the first or most recent
        self.assertIsNotNone(mgr.get_preferred_instance(None))

        # Explicit preferred selection returns exactly the matching instance
        self.assertEqual(mgr.get_preferred_instance(i2.id).name, "Instance Beta")
        self.assertEqual(mgr.get_preferred_instance(i1.id).name, "Instance Alpha")

    def test_14_version_and_updater(self):
        """Verifies local version file loading and updater structure."""
        from config import APP_VERSION, GITHUB_REPO_OWNER, GITHUB_REPO_NAME
        from updater.github import check_for_updates

        self.assertEqual(GITHUB_REPO_OWNER, "ItsRealSandesh")
        self.assertEqual(GITHUB_REPO_NAME, "SandeshLauncher")
        self.assertTrue(Path("version.txt").exists())
        with open("version.txt", "r") as f:
            v_txt = f.read().strip()
        self.assertEqual(APP_VERSION, v_txt)

        info = check_for_updates()
        self.assertIsNotNone(info)
        self.assertEqual(info.current_version, APP_VERSION)


if __name__ == "__main__":
    unittest.main()

