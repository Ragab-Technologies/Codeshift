"""Source fetchers for changelog and migration guide discovery."""

import re
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse

import httpx

from pyresolve.knowledge.models import ChangelogSource


@dataclass
class PackageInfo:
    """Package information from PyPI."""

    name: str
    version: str
    home_page: Optional[str] = None
    project_url: Optional[str] = None
    repository_url: Optional[str] = None
    documentation_url: Optional[str] = None

    @property
    def github_url(self) -> Optional[str]:
        """Extract GitHub repository URL."""
        for url in [self.repository_url, self.project_url, self.home_page]:
            if url and "github.com" in url:
                # Normalize to https://github.com/owner/repo format
                parsed = urlparse(url)
                if parsed.netloc == "github.com":
                    path_parts = parsed.path.strip("/").split("/")
                    if len(path_parts) >= 2:
                        return f"https://github.com/{path_parts[0]}/{path_parts[1]}"
        return None


class SourceFetcher:
    """Fetches changelog and migration guide sources from various locations."""

    CHANGELOG_FILENAMES = [
        "CHANGELOG.md",
        "CHANGELOG.rst",
        "CHANGELOG.txt",
        "CHANGELOG",
        "CHANGES.md",
        "CHANGES.rst",
        "CHANGES.txt",
        "CHANGES",
        "HISTORY.md",
        "HISTORY.rst",
        "NEWS.md",
        "NEWS.rst",
        "NEWS",
    ]

    MIGRATION_GUIDE_PATTERNS = [
        "docs/migration",
        "docs/upgrading",
        "docs/upgrade",
        "migration",
        "MIGRATION.md",
        "UPGRADING.md",
    ]

    def __init__(self, timeout: float = 30.0):
        """Initialize the fetcher.

        Args:
            timeout: HTTP request timeout in seconds.
        """
        self.timeout = timeout
        self._client: Optional[httpx.Client] = None

    @property
    def client(self) -> httpx.Client:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.Client(
                timeout=self.timeout,
                follow_redirects=True,
                headers={"Accept": "application/vnd.github.v3.raw"},
            )
        return self._client

    def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            self._client.close()
            self._client = None

    def get_package_info(self, package: str) -> Optional[PackageInfo]:
        """Fetch package information from PyPI.

        Args:
            package: Package name.

        Returns:
            PackageInfo or None if not found.
        """
        try:
            response = self.client.get(f"https://pypi.org/pypi/{package}/json")
            response.raise_for_status()
            data = response.json()

            info = data.get("info", {})
            project_urls = info.get("project_urls") or {}

            return PackageInfo(
                name=info.get("name", package),
                version=info.get("version", ""),
                home_page=info.get("home_page"),
                project_url=info.get("project_url"),
                repository_url=project_urls.get("Repository") or project_urls.get("Source") or project_urls.get("GitHub"),
                documentation_url=project_urls.get("Documentation") or project_urls.get("Docs"),
            )
        except Exception:
            return None

    def fetch_github_file(self, repo_url: str, file_path: str, branch: str = "main") -> Optional[str]:
        """Fetch a file from a GitHub repository.

        Args:
            repo_url: GitHub repository URL (https://github.com/owner/repo).
            file_path: Path to the file within the repo.
            branch: Branch to fetch from.

        Returns:
            File content or None if not found.
        """
        # Extract owner/repo from URL
        parsed = urlparse(repo_url)
        path_parts = parsed.path.strip("/").split("/")
        if len(path_parts) < 2:
            return None

        owner, repo = path_parts[0], path_parts[1]

        # Try raw GitHub content URL
        raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{file_path}"

        try:
            response = self.client.get(raw_url)
            if response.status_code == 200:
                return response.text
        except Exception:
            pass

        # Try master branch if main failed
        if branch == "main":
            return self.fetch_github_file(repo_url, file_path, branch="master")

        return None

    def fetch_changelog(self, repo_url: str) -> Optional[ChangelogSource]:
        """Fetch changelog from a GitHub repository.

        Args:
            repo_url: GitHub repository URL.

        Returns:
            ChangelogSource or None if not found.
        """
        for filename in self.CHANGELOG_FILENAMES:
            content = self.fetch_github_file(repo_url, filename)
            if content:
                return ChangelogSource(
                    url=f"{repo_url}/blob/main/{filename}",
                    source_type="changelog",
                    content=content,
                )
        return None

    def fetch_migration_guide(self, repo_url: str) -> Optional[ChangelogSource]:
        """Fetch migration guide from a GitHub repository.

        Args:
            repo_url: GitHub repository URL.

        Returns:
            ChangelogSource or None if not found.
        """
        for pattern in self.MIGRATION_GUIDE_PATTERNS:
            # Try common file extensions
            for ext in [".md", ".rst", ".txt", ""]:
                path = f"{pattern}{ext}" if not pattern.endswith((".md", ".rst", ".txt")) else pattern
                content = self.fetch_github_file(repo_url, path)
                if content:
                    return ChangelogSource(
                        url=f"{repo_url}/blob/main/{path}",
                        source_type="migration_guide",
                        content=content,
                    )
        return None

    def fetch_release_notes(self, repo_url: str, version: str) -> Optional[ChangelogSource]:
        """Fetch release notes for a specific version from GitHub releases.

        Args:
            repo_url: GitHub repository URL.
            version: Version to fetch release notes for.

        Returns:
            ChangelogSource or None if not found.
        """
        parsed = urlparse(repo_url)
        path_parts = parsed.path.strip("/").split("/")
        if len(path_parts) < 2:
            return None

        owner, repo = path_parts[0], path_parts[1]

        # Try GitHub API for releases
        api_url = f"https://api.github.com/repos/{owner}/{repo}/releases"

        try:
            response = self.client.get(api_url)
            if response.status_code != 200:
                return None

            releases = response.json()

            # Find matching release
            version_patterns = [
                f"v{version}",
                version,
                f"release-{version}",
            ]

            for release in releases:
                tag = release.get("tag_name", "")
                for pattern in version_patterns:
                    if tag == pattern or tag.startswith(pattern):
                        body = release.get("body", "")
                        if body:
                            return ChangelogSource(
                                url=release.get("html_url", repo_url),
                                source_type="release_notes",
                                content=body,
                                version_range=(version, version),
                            )
                        break

        except Exception:
            pass

        return None

    async def discover_sources(self, package: str, target_version: Optional[str] = None) -> list[ChangelogSource]:
        """Discover all available changelog sources for a package.

        Args:
            package: Package name.
            target_version: Optional target version for release notes.

        Returns:
            List of discovered ChangelogSources.
        """
        # This is a sync wrapper - the async signature matches the architecture doc
        return self.discover_sources_sync(package, target_version)

    def discover_sources_sync(self, package: str, target_version: Optional[str] = None) -> list[ChangelogSource]:
        """Synchronously discover all available changelog sources for a package.

        Args:
            package: Package name.
            target_version: Optional target version for release notes.

        Returns:
            List of discovered ChangelogSources.
        """
        sources = []

        # Get package info from PyPI
        pkg_info = self.get_package_info(package)
        if not pkg_info:
            return sources

        github_url = pkg_info.github_url
        if not github_url:
            return sources

        # Fetch changelog
        changelog = self.fetch_changelog(github_url)
        if changelog:
            sources.append(changelog)

        # Fetch migration guide
        migration_guide = self.fetch_migration_guide(github_url)
        if migration_guide:
            sources.append(migration_guide)

        # Fetch release notes for target version
        if target_version:
            release_notes = self.fetch_release_notes(github_url, target_version)
            if release_notes:
                sources.append(release_notes)

        return sources

    def extract_version_changelog(
        self,
        changelog_content: str,
        from_version: str,
        to_version: str,
    ) -> str:
        """Extract the relevant portion of a changelog between two versions.

        Args:
            changelog_content: Full changelog content.
            from_version: Starting version.
            to_version: Target version.

        Returns:
            Extracted changelog content for the version range.
        """
        lines = changelog_content.split("\n")
        result_lines = []
        in_range = False
        found_start = False

        # Common version header patterns
        version_pattern = re.compile(
            r"^#+\s*\[?v?(\d+\.\d+(?:\.\d+)?)\]?|"  # ## [1.0.0] or ## v1.0.0
            r"^v?(\d+\.\d+(?:\.\d+)?)\s*[-–—]|"  # 1.0.0 - or v1.0.0 -
            r"^v?(\d+\.\d+(?:\.\d+)?)\s*\(",  # 1.0.0 (date)
            re.IGNORECASE,
        )

        for line in lines:
            match = version_pattern.match(line)
            if match:
                # Extract version number
                version = match.group(1) or match.group(2) or match.group(3)
                if version:
                    # Check if this is our target version or later
                    if self._compare_versions(version, to_version) <= 0:
                        if not found_start:
                            in_range = True
                            found_start = True

                    # Check if we've gone past the from_version
                    if self._compare_versions(version, from_version) < 0:
                        in_range = False

            if in_range:
                result_lines.append(line)

        return "\n".join(result_lines)

    def _compare_versions(self, v1: str, v2: str) -> int:
        """Compare two version strings.

        Returns:
            -1 if v1 < v2, 0 if v1 == v2, 1 if v1 > v2.
        """
        from packaging.version import Version

        try:
            ver1 = Version(v1)
            ver2 = Version(v2)
            if ver1 < ver2:
                return -1
            elif ver1 > ver2:
                return 1
            return 0
        except Exception:
            # Fallback to string comparison
            return (v1 > v2) - (v1 < v2)


# Singleton instance
_default_fetcher: Optional[SourceFetcher] = None


def get_source_fetcher() -> SourceFetcher:
    """Get the default source fetcher instance."""
    global _default_fetcher
    if _default_fetcher is None:
        _default_fetcher = SourceFetcher()
    return _default_fetcher
