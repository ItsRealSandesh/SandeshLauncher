"""
Mod, Resource Pack, Shader, and Modpack installer pipeline for SandeshLauncher.
Downloads components with cryptographic hash checks, automatic directory routing,
and full Modrinth .mrpack modpack unpacking.
"""

import json
import zipfile
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from instances.manager import InstanceManager
from instances.model import MinecraftInstance
from mods.dependencies import DependencyResolver, ResolvedDependency
from mods.modrinth import ModrinthClient
from utils.logging import get_logger
from utils.network import download_file_with_progress
from utils.paths import get_instances_dir
from utils.security import safe_extract_zip

logger = get_logger("content_installer")


class ContentInstaller:
    def __init__(
        self,
        modrinth_client: Optional[ModrinthClient] = None,
        instance_manager: Optional[InstanceManager] = None,
    ):
        self.client = modrinth_client or ModrinthClient()
        self.instance_manager = instance_manager or InstanceManager()
        self.dep_resolver = DependencyResolver(self.client)

    def install_project_to_instance(
        self,
        project_id_or_slug: str,
        instance: MinecraftInstance,
        target_minecraft_version: Optional[str] = None,
        target_loader: Optional[str] = None,
        specific_version_id: Optional[str] = None,
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
        auto_install_dependencies: bool = True,
    ) -> Tuple[bool, str, List[str]]:
        """
        Installs a Mod, Shader, or Resource Pack into the specified instance.
        Supports explicit Minecraft version and Loader (Fabric / Forge / NeoForge / Quilt)
        or direct specific version installation.
        Returns: (success, message, list_of_installed_filenames)
        """
        proj_info = self.client.get_project(project_id_or_slug)
        project_type = proj_info.get("project_type", "mod")
        title = proj_info.get("title", project_id_or_slug)

        logger.info(f"Installing {project_type} '{title}' into instance '{instance.name}'...")

        if specific_version_id:
            try:
                target_version = self.client.get_version(specific_version_id)
            except Exception as e:
                return False, f"Could not fetch version {specific_version_id}: {e}", []
        else:
            req_ver = target_minecraft_version if (target_minecraft_version and target_minecraft_version.lower() not in ("all", "any", "auto")) else instance.minecraft_version
            req_loader = target_loader if (target_loader and target_loader.lower() not in ("all", "any", "auto")) else instance.loader

            versions = self.client.get_project_versions(
                project_id_or_slug,
                minecraft_version=req_ver,
                loader=req_loader
            )

            if not versions:
                return False, f"No compatible version of '{title}' found for Minecraft {req_ver} with loader {req_loader}.", []

            target_version = versions[0]
        files = target_version.get("files", [])
        primary_file = next((f for f in files if f.get("primary")), files[0] if files else None)

        if not primary_file:
            return False, f"No downloadable files found for {title}.", []

        file_url = primary_file.get("url")
        file_name = primary_file.get("filename")
        hashes = primary_file.get("hashes", {})
        sha512 = hashes.get("sha512")
        sha1 = hashes.get("sha1")

        # Determine target directory
        game_dir = instance.get_game_dir(get_instances_dir())
        if project_type == "mod":
            target_dir = instance.get_mods_dir(get_instances_dir())
        elif project_type == "shader":
            target_dir = instance.get_shaderpacks_dir(get_instances_dir())
        elif project_type == "resourcepack":
            target_dir = instance.get_resourcepacks_dir(get_instances_dir())
        else:
            target_dir = game_dir

        target_path = target_dir / file_name

        if progress_callback:
            progress_callback(f"Downloading {file_name}...", 0, 100)

        installed_files = []
        try:
            download_file_with_progress(
                url=file_url,
                destination=target_path,
                expected_sha512=sha512,
                expected_sha1=sha1,
                progress_callback=lambda cur, tot, sp: progress_callback(f"Downloading {file_name} ({sp})...", cur, tot) if progress_callback else None
            )
            installed_files.append(file_name)
        except Exception as e:
            logger.error(f"Download failed for {file_name}: {e}")
            return False, f"Download failed: {e}", []

        # Handle dependencies for mods
        if project_type == "mod" and auto_install_dependencies:
            try:
                deps = self.dep_resolver.resolve_required_dependencies(
                    version_data=target_version,
                    minecraft_version=instance.minecraft_version,
                    loader=instance.loader
                )

                for dep in deps:
                    dep_target = target_dir / dep.file_name
                    if not dep_target.exists():
                        if progress_callback:
                            progress_callback(f"Downloading dependency {dep.project_title}...", 0, 100)
                        logger.info(f"Installing required dependency '{dep.project_title}' ({dep.file_name})")
                        download_file_with_progress(
                            url=dep.download_url,
                            destination=dep_target,
                            expected_sha512=dep.sha512,
                            expected_sha1=dep.sha1,
                            progress_callback=lambda cur, tot, sp: progress_callback(f"Downloading dependency {dep.project_title} ({sp})...", cur, tot) if progress_callback else None
                        )
                        installed_files.append(dep.file_name)
            except Exception as e:
                logger.warning(f"Could not install some dependencies for {title}: {e}")

        logger.info(f"Successfully installed '{title}' into {instance.name}")
        return True, f"Successfully installed '{title}' into instance '{instance.name}'.", installed_files

    def install_modpack(
        self,
        project_id_or_slug: str,
        custom_instance_name: Optional[str] = None,
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
    ) -> MinecraftInstance:
        """
        Installs a Modrinth .mrpack modpack by creating a new dedicated instance.
        """
        proj_info = self.client.get_project(project_id_or_slug)
        title = custom_instance_name or proj_info.get("title", "Modpack")

        versions = self.client.get_project_versions(project_id_or_slug)
        if not versions:
            raise ValueError(f"No releases found for modpack '{title}'.")

        latest_version = versions[0]
        files = latest_version.get("files", [])
        primary_file = next((f for f in files if f.get("filename", "").endswith(".mrpack")), files[0] if files else None)

        if not primary_file:
            raise ValueError(f"No .mrpack archive found for '{title}'.")

        mrpack_url = primary_file.get("url")
        mrpack_name = primary_file.get("filename")

        # Download temporary .mrpack
        temp_mrpack = get_instances_dir() / f"temp_{mrpack_name}"
        if progress_callback:
            progress_callback(f"Downloading modpack archive {mrpack_name}...", 0, 100)

        download_file_with_progress(
            url=mrpack_url,
            destination=temp_mrpack,
            progress_callback=lambda cur, tot, sp: progress_callback(f"Downloading modpack archive ({sp})...", cur, tot) if progress_callback else None
        )

        # Parse modrinth.index.json
        try:
            with zipfile.ZipFile(temp_mrpack, "r") as archive:
                with archive.open("modrinth.index.json") as f:
                    index_data = json.load(f)

            deps = index_data.get("dependencies", {})
            mc_ver = deps.get("minecraft", "1.21.1")
            
            # Detect loader
            loader = "vanilla"
            loader_ver = "latest"
            if "fabric-loader" in deps:
                loader = "fabric"
                loader_ver = deps["fabric-loader"]
            elif "quilt-loader" in deps:
                loader = "quilt"
                loader_ver = deps["quilt-loader"]
            elif "forge" in deps:
                loader = "forge"
                loader_ver = deps["forge"]
            elif "neoforge" in deps:
                loader = "neoforge"
                loader_ver = deps["neoforge"]

            # Create new instance
            inst = self.instance_manager.create(
                name=title,
                minecraft_version=mc_ver,
                loader=loader,
                loader_version=loader_ver,
            )
            game_dir = inst.get_game_dir(get_instances_dir())

            # Download files specified in manifest
            pack_files = index_data.get("files", [])
            total_files = len(pack_files)

            for idx, item in enumerate(pack_files, 1):
                item_path = item.get("path")
                dest_file = game_dir / item_path
                dest_file.parent.mkdir(parents=True, exist_ok=True)

                hashes = item.get("hashes", {})
                downloads = item.get("downloads", [])
                if downloads:
                    dl_url = downloads[0]
                    if progress_callback:
                        progress_callback(f"Downloading modpack files ({idx}/{total_files})...", idx, total_files)

                    download_file_with_progress(
                        url=dl_url,
                        destination=dest_file,
                        expected_sha512=hashes.get("sha512"),
                        expected_sha1=hashes.get("sha1")
                    )

            # Extract overrides & client-overrides
            with zipfile.ZipFile(temp_mrpack, "r") as archive:
                for member in archive.infolist():
                    prefix = None
                    if member.filename.startswith("overrides/"):
                        prefix = "overrides/"
                    elif member.filename.startswith("client-overrides/"):
                        prefix = "client-overrides/"

                    if prefix and len(member.filename) > len(prefix):
                        rel_path = member.filename[len(prefix):]
                        dest_path = game_dir / rel_path
                        if member.is_dir():
                            dest_path.mkdir(parents=True, exist_ok=True)
                        else:
                            dest_path.parent.mkdir(parents=True, exist_ok=True)
                            with archive.open(member) as src, open(dest_path, "wb") as dst:
                                dst.write(src.read())

            temp_mrpack.unlink(missing_ok=True)
            logger.info(f"Modpack '{title}' successfully installed as instance '{inst.id}'")
            return inst

        except Exception as e:
            logger.error(f"Failed to install modpack {title}: {e}")
            temp_mrpack.unlink(missing_ok=True)
            raise RuntimeError(f"Modpack installation failed: {e}")
