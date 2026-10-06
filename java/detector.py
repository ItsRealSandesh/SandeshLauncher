"""
Java runtime detector for SandeshLauncher.
Discovers installed Java runtimes on Linux, Windows, and macOS,
and parses their major versions and architecture.
"""

import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from utils.logging import get_logger
from utils.paths import get_runtimes_dir

logger = get_logger("java_detector")


@dataclass
class JavaInfo:
    path: str
    major_version: int
    version_string: str
    is_64bit: bool = True
    vendor: str = "Unknown"

    @property
    def display_name(self) -> str:
        arch = "64-bit" if self.is_64bit else "32-bit"
        return f"Java {self.major_version} ({self.vendor}, {arch}) - {self.path}"


_PARSED_JAVA_CACHE: Dict[str, Optional[JavaInfo]] = {}
_SYSTEM_JAVAS_CACHE: Optional[List[JavaInfo]] = None


def parse_java_version(executable_path: str) -> Optional[JavaInfo]:
    """
    Executes `<java_path> -version` to extract major version,
    full version string, 64-bit status, and vendor.
    Caches parsed info for high performance.
    """
    if not executable_path or not os.path.exists(executable_path):
        return None

    resolved_key = str(Path(executable_path).resolve())
    if resolved_key in _PARSED_JAVA_CACHE:
        return _PARSED_JAVA_CACHE[resolved_key]

    try:
        proc = subprocess.run(
            [executable_path, "-version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=5,
            check=False
        )
        output = proc.stderr or proc.stdout
        if not output:
            return None

        # Parse version
        # e.g.: openjdk version "21.0.11"
        # or java version "1.8.0_381"
        version_match = re.search(r'version "([0-9._\-a-zA-Z]+)"', output)
        if not version_match:
            return None

        ver_str = version_match.group(1)
        # Parse major version
        if ver_str.startswith("1."):
            # Java 1.8 -> major 8
            parts = ver_str.split(".")
            major = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 8
        else:
            # Java 17.0.2 -> major 17
            major_str = ver_str.split(".")[0].split("-")[0]
            major = int(major_str) if major_str.isdigit() else 0

        if major == 0:
            return None

        is_64 = "64-Bit" in output or "x86_64" in output or "amd64" in output

        vendor = "OpenJDK"
        if "Eclipse Adoptium" in output or "Temurin" in output:
            vendor = "Temurin"
        elif "Oracle" in output:
            vendor = "Oracle"
        elif "Zulu" in output:
            vendor = "Azul Zulu"
        elif "Corretto" in output:
            vendor = "Amazon Corretto"
        elif "Microsoft" in output:
            vendor = "Microsoft"

        info = JavaInfo(
            path=str(Path(executable_path).resolve()),
            major_version=major,
            version_string=ver_str,
            is_64bit=is_64,
            vendor=vendor
        )
        _PARSED_JAVA_CACHE[resolved_key] = info
        return info
    except Exception as e:
        logger.debug(f"Could not parse Java version from {executable_path}: {e}")
        _PARSED_JAVA_CACHE[resolved_key] = None
        return None


def detect_system_javas(force_refresh: bool = False) -> List[JavaInfo]:
    """Scans system paths and directories for installed Java executables (cached)."""
    global _SYSTEM_JAVAS_CACHE
    if not force_refresh and _SYSTEM_JAVAS_CACHE is not None:
        return list(_SYSTEM_JAVAS_CACHE)

    found_paths = set()
    results: List[JavaInfo] = []

    # 1. Check `which java` or `where java`
    which_java = shutil.which("java")
    if which_java:
        found_paths.add(Path(which_java).resolve())

    # 2. Check JAVA_HOME
    java_home = os.environ.get("JAVA_HOME")
    if java_home:
        jh_exec = Path(java_home) / "bin" / ("java.exe" if sys.platform == "win32" else "java")
        if jh_exec.exists():
            found_paths.add(jh_exec.resolve())

    # 3. Check launcher runtimes directory
    runtimes_dir = get_runtimes_dir()
    if runtimes_dir.exists():
        for sub in runtimes_dir.glob("**/java*"):
            if sub.is_file() and os.access(sub, os.X_OK) and sub.name in ("java", "java.exe"):
                found_paths.add(sub.resolve())

    # 4. OS-specific directories
    search_dirs = []
    if sys.platform == "linux":
        search_dirs.extend([
            Path("/usr/lib/jvm"),
            Path("/usr/java"),
            Path("/opt"),
            Path.home() / ".jdks",
            Path.home() / ".sdkman/candidates/java",
        ])
    elif sys.platform == "win32":
        for env_var in ["ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA"]:
            val = os.environ.get(env_var)
            if val:
                search_dirs.extend([
                    Path(val) / "Java",
                    Path(val) / "Eclipse Adoptium",
                    Path(val) / "BellSoft",
                    Path(val) / "Zulu",
                    Path(val) / "Microsoft",
                ])
    elif sys.platform == "darwin":
        search_dirs.extend([
            Path("/Library/Java/JavaVirtualMachines"),
            Path.home() / "Library/Java/JavaVirtualMachines",
        ])

    for base in search_dirs:
        if base.exists():
            pattern = "**/bin/java.exe" if sys.platform == "win32" else "**/bin/java"
            try:
                for candidate in base.glob(pattern):
                    if candidate.is_file() and os.access(candidate, os.X_OK):
                        found_paths.add(candidate.resolve())
            except Exception:
                pass

    for p in found_paths:
        info = parse_java_version(str(p))
        if info:
            if not any(r.path == info.path for r in results):
                results.append(info)

    results.sort(key=lambda j: j.major_version, reverse=True)
    logger.info(f"Discovered {len(results)} Java runtime(s): {[f'Java {j.major_version}' for j in results]}")
    _SYSTEM_JAVAS_CACHE = list(results)
    return results


def get_required_java_version(minecraft_version: str, game_dir: Optional[Path] = None) -> int:
    """
    Determines the required Java major version for a given Minecraft version string
    and any installed mods in game_dir.
    1. Base requirement from version string (26.x/25.x -> 25, >=1.20.5 -> 21, 1.17-1.20.4 -> 17, <=1.16.5 -> 8)
    2. Checks official version.json (e.g. 26.2.json specifies majorVersion: 25)
    3. Checks installed mods in game_dir/mods (fabric.mod.json, mods.toml dependencies)
    """
    clean_ver = minecraft_version.lower().strip()
    required = 8

    # 1. Base requirement from version string
    if re.match(r"^2[5-9]", clean_ver) or re.match(r"^2[5-9]w", clean_ver):
        required = 25
    elif re.match(r"^24w[0-9]{2}", clean_ver):
        required = 21
    elif re.match(r"^2[1-3]w[0-9]{2}", clean_ver):
        required = 17
    else:
        match = re.match(r"^1\.(\d+)(?:\.(\d+))?", clean_ver)
        if match:
            minor = int(match.group(1))
            patch = int(match.group(2)) if match.group(2) else 0
            if minor > 20 or (minor == 20 and patch >= 5):
                required = 21
            elif minor >= 17:
                required = 17
            else:
                required = 8
        else:
            required = 21

    # 2. Try reading official Mojang or loader version.json if available
    try:
        from utils.paths import get_shared_minecraft_dir
        shared_dir = get_shared_minecraft_dir()
        v_file = shared_dir / "versions" / clean_ver / f"{clean_ver}.json"
        if v_file.exists():
            with open(v_file, "r", encoding="utf-8") as f:
                v_data = json.load(f)
            jv = v_data.get("javaVersion", {})
            if isinstance(jv, dict) and jv.get("majorVersion"):
                required = max(required, int(jv["majorVersion"]))
    except Exception:
        pass

    # 3. Check installed mods for higher Java requirements (e.g. Fabric API >= 25)
    if game_dir:
        mods_dir = Path(game_dir) / "mods"
        if mods_dir.exists():
            from zipfile import ZipFile
            for jar_path in mods_dir.glob("*.jar"):
                try:
                    with ZipFile(jar_path, "r") as zf:
                        if "fabric.mod.json" in zf.namelist():
                            m_data = json.loads(zf.read("fabric.mod.json").decode("utf-8", errors="ignore"))
                            deps = m_data.get("depends", {})
                            if isinstance(deps, dict):
                                java_req = str(deps.get("java", ""))
                                j_match = re.search(r"(\d+)", java_req)
                                if j_match:
                                    required = max(required, int(j_match.group(1)))
                except Exception:
                    pass

    return required

