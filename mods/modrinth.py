"""
Modrinth API Client for SandeshLauncher.
Integrates search, project retrieval, version filtering, and asset discovery.
"""

import json
import time
import urllib.parse
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

from config import MODRINTH_API_URL, DEFAULT_USER_AGENT
from utils.logging import get_logger
from utils.paths import get_cache_dir

logger = get_logger("modrinth")


@dataclass
class ModrinthProject:
    id: str
    slug: str
    title: str
    description: str
    author: str
    project_type: str  # mod, modpack, shader, resourcepack
    icon_url: Optional[str]
    downloads: int
    categories: List[str]
    versions: List[str]

    @property
    def display_downloads(self) -> str:
        if self.downloads >= 1_000_000:
            return f"{self.downloads / 1_000_000:.1f}M"
        if self.downloads >= 1_000:
            return f"{self.downloads / 1_000:.1f}k"
        return str(self.downloads)


class ModrinthClient:
    def __init__(self, base_url: str = MODRINTH_API_URL):
        self.base_url = base_url
        self.headers = {"User-Agent": DEFAULT_USER_AGENT}
        self.cache_dir = get_cache_dir() / "modrinth"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _get_cached(self, key: str, ttl_seconds: int = 1800) -> Optional[Any]:
        cache_file = self.cache_dir / f"{key}.json"
        if cache_file.exists():
            try:
                if time.time() - cache_file.stat().st_mtime < ttl_seconds:
                    with open(cache_file, "r", encoding="utf-8") as f:
                        return json.load(f)
            except Exception:
                pass
        return None

    def _set_cache(self, key: str, data: Any) -> None:
        cache_file = self.cache_dir / f"{key}.json"
        try:
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(data, f)
        except Exception:
            pass

    def search(
        self,
        query: str = "",
        project_type: str = "mod",
        minecraft_version: Optional[str] = None,
        loader: Optional[str] = None,
        sort: str = "relevance",  # relevance, downloads, follows, new, updated
        limit: int = 20,
        offset: int = 0,
    ) -> List[ModrinthProject]:
        """Searches Modrinth projects with faceted filtering."""
        facets_list = []
        if project_type:
            facets_list.append([f"project_type:{project_type}"])
        if minecraft_version and minecraft_version.lower() not in ("all", "any", ""):
            facets_list.append([f"versions:{minecraft_version}"])
        if loader and loader.lower() not in ("vanilla", "all", "any", ""):
            facets_list.append([f"categories:{loader.lower()}"])

        params: Dict[str, Any] = {
            "limit": limit,
            "offset": offset,
            "index": sort,
        }
        if query:
            params["query"] = query
        if facets_list:
            params["facets"] = json.dumps(facets_list)

        cache_key = f"search_{project_type}_{minecraft_version}_{loader}_{sort}_{offset}_{hash(query)}"
        cached = self._get_cached(cache_key, ttl_seconds=300)
        if cached is not None:
            return [self._parse_search_hit(h) for h in cached]

        url = f"{self.base_url}/search"
        logger.info(f"Modrinth Search: type={project_type}, query='{query}', loader={loader}, ver={minecraft_version}")

        try:
            resp = requests.get(url, params=params, headers=self.headers, timeout=12)
            resp.raise_for_status()
            data = resp.json()
            hits = data.get("hits", [])
            self._set_cache(cache_key, hits)
            return [self._parse_search_hit(h) for h in hits]
        except Exception as e:
            logger.error(f"Modrinth search error: {e}")
            raise ConnectionError(f"Unable to reach Modrinth: {e}")

    def _parse_search_hit(self, hit: Dict[str, Any]) -> ModrinthProject:
        return ModrinthProject(
            id=hit.get("project_id", ""),
            slug=hit.get("slug", ""),
            title=hit.get("title", "Untitled"),
            description=hit.get("description", ""),
            author=hit.get("author", "Unknown"),
            project_type=hit.get("project_type", "mod"),
            icon_url=hit.get("icon_url"),
            downloads=hit.get("downloads", 0),
            categories=hit.get("categories", []),
            versions=hit.get("versions", []),
        )

    def get_project(self, project_id_or_slug: str) -> Dict[str, Any]:
        """Fetches full project details."""
        cache_key = f"proj_{project_id_or_slug}"
        cached = self._get_cached(cache_key, ttl_seconds=3600)
        if cached:
            return cached

        url = f"{self.base_url}/project/{project_id_or_slug}"
        resp = requests.get(url, headers=self.headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        self._set_cache(cache_key, data)
        return data

    def get_project_versions(
        self,
        project_id_or_slug: str,
        minecraft_version: Optional[str] = None,
        loader: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Retrieves versions for a project, optionally filtered by game version and loader."""
        params: Dict[str, Any] = {}
        if loader and loader.lower() not in ("vanilla", "all", "any", ""):
            params["loaders"] = json.dumps([loader.lower()])
        if minecraft_version and minecraft_version.lower() not in ("all", "any", ""):
            params["game_versions"] = json.dumps([minecraft_version])

        cache_key = f"versions_{project_id_or_slug}_{minecraft_version}_{loader}"
        cached = self._get_cached(cache_key, ttl_seconds=600)
        if cached is not None:
            return cached

        url = f"{self.base_url}/project/{project_id_or_slug}/version"
        try:
            resp = requests.get(url, params=params, headers=self.headers, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            self._set_cache(cache_key, data)
            return data
        except Exception as e:
            logger.warning(f"Could not fetch versions for {project_id_or_slug}: {e}")
            return []

    def get_version(self, version_id: str) -> Dict[str, Any]:
        """Fetches a specific version by its ID."""
        cache_key = f"ver_{version_id}"
        cached = self._get_cached(cache_key, ttl_seconds=3600)
        if cached:
            return cached

        url = f"{self.base_url}/version/{version_id}"
        resp = requests.get(url, headers=self.headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        self._set_cache(cache_key, data)
        return data
