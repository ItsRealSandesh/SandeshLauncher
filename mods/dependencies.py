"""
Dependency resolution engine for Modrinth projects.
Recursively resolves required dependencies for mods, ensuring all prerequisites are installed.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple, Any

from mods.modrinth import ModrinthClient
from utils.logging import get_logger

logger = get_logger("dependencies")


@dataclass
class ResolvedDependency:
    project_id: str
    project_title: str
    version_id: str
    file_name: str
    download_url: str
    sha512: Optional[str]
    sha1: Optional[str]
    size: int


class DependencyResolver:
    def __init__(self, modrinth_client: Optional[ModrinthClient] = None):
        self.client = modrinth_client or ModrinthClient()

    def resolve_required_dependencies(
        self,
        version_data: Dict[str, Any],
        minecraft_version: str,
        loader: str,
        already_installed_projects: Optional[Set[str]] = None,
    ) -> List[ResolvedDependency]:
        """
        Recursively discovers all required dependencies that are not yet installed.
        Returns a list of ResolvedDependency objects ready for download.
        """
        resolved: List[ResolvedDependency] = []
        visited_projects: Set[str] = set(already_installed_projects or set())

        def _traverse(deps: List[Dict[str, Any]]) -> None:
            for dep in deps:
                dep_type = dep.get("dependency_type")
                if dep_type != "required":
                    continue

                proj_id = dep.get("project_id")
                ver_id = dep.get("version_id")

                if not proj_id and not ver_id:
                    continue

                if proj_id and proj_id in visited_projects:
                    continue

                # If version ID is specified directly
                target_version_data = None
                if ver_id:
                    try:
                        target_version_data = self.client.get_version(ver_id)
                        if not proj_id:
                            proj_id = target_version_data.get("project_id")
                    except Exception as e:
                        logger.warning(f"Could not fetch dependency version {ver_id}: {e}")

                # If project ID is specified, find best compatible version
                if not target_version_data and proj_id:
                    try:
                        compat_versions = self.client.get_project_versions(
                            proj_id,
                            minecraft_version=minecraft_version,
                            loader=loader
                        )
                        if compat_versions:
                            target_version_data = compat_versions[0]
                    except Exception as e:
                        logger.warning(f"Could not find compatible version for dependency {proj_id}: {e}")

                if not target_version_data:
                    logger.warning(f"Could not resolve dependency {proj_id or ver_id}")
                    continue

                if proj_id:
                    visited_projects.add(proj_id)

                # Fetch project name
                proj_title = proj_id
                try:
                    if proj_id:
                        p_info = self.client.get_project(proj_id)
                        proj_title = p_info.get("title", proj_id)
                except Exception:
                    pass

                files = target_version_data.get("files", [])
                primary_file = next((f for f in files if f.get("primary")), files[0] if files else None)

                if primary_file:
                    hashes = primary_file.get("hashes", {})
                    resolved.append(ResolvedDependency(
                        project_id=proj_id or "",
                        project_title=proj_title,
                        version_id=target_version_data.get("id", ""),
                        file_name=primary_file.get("filename", "mod.jar"),
                        download_url=primary_file.get("url", ""),
                        sha512=hashes.get("sha512"),
                        sha1=hashes.get("sha1"),
                        size=primary_file.get("size", 0),
                    ))

                    # Recursively resolve child dependencies
                    sub_deps = target_version_data.get("dependencies", [])
                    if sub_deps:
                        _traverse(sub_deps)

        initial_deps = version_data.get("dependencies", [])
        _traverse(initial_deps)
        return resolved
