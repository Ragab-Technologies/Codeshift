"""Parser for dependency files (requirements.txt, pyproject.toml)."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import toml
from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet
from packaging.version import Version


@dataclass
class Dependency:
    """Represents a project dependency."""

    name: str
    version_spec: str | None = None
    extras: list[str] = field(default_factory=list)
    source_file: Path | None = None

    @property
    def min_version(self) -> Version | None:
        """Get the minimum version from the specifier."""
        if not self.version_spec:
            return None

        try:
            specifier = SpecifierSet(self.version_spec)
            for spec in specifier:
                if spec.operator in (">=", "==", "~="):
                    return Version(spec.version)
        except Exception:
            pass
        return None

    @property
    def max_version(self) -> Version | None:
        """Get the maximum version from the specifier."""
        if not self.version_spec:
            return None

        try:
            specifier = SpecifierSet(self.version_spec)
            for spec in specifier:
                if spec.operator in ("<=", "<", "=="):
                    return Version(spec.version)
        except Exception:
            pass
        return None

    def is_version_compatible(self, version: str) -> bool:
        """Check if a version is compatible with this dependency's spec."""
        if not self.version_spec:
            return True

        try:
            specifier = SpecifierSet(self.version_spec)
            return Version(version) in specifier
        except Exception:
            return True


class DependencyParser:
    """Parser for extracting dependencies from project files."""

    def __init__(self, project_path: Path):
        """Initialize the parser.

        Args:
            project_path: Root path of the project
        """
        self.project_path = project_path

    def parse_all(self) -> list[Dependency]:
        """Parse dependencies from all available sources.

        Returns:
            List of all dependencies found
        """
        dependencies = []

        # Try pyproject.toml first
        pyproject_deps = self.parse_pyproject_toml()
        dependencies.extend(pyproject_deps)

        # Also check requirements.txt
        requirements_deps = self.parse_requirements_txt()
        dependencies.extend(requirements_deps)

        # Also check setup.py (basic parsing)
        setup_deps = self.parse_setup_py()
        dependencies.extend(setup_deps)

        # Deduplicate by name (prefer pyproject.toml)
        seen = set()
        unique = []
        for dep in dependencies:
            if dep.name.lower() not in seen:
                seen.add(dep.name.lower())
                unique.append(dep)

        return unique

    def parse_pyproject_toml(self) -> list[Dependency]:
        """Parse dependencies from pyproject.toml.

        Returns:
            List of dependencies found
        """
        pyproject_path = self.project_path / "pyproject.toml"
        if not pyproject_path.exists():
            return []

        try:
            data = toml.load(pyproject_path)
        except Exception:
            return []

        dependencies = []

        # Standard project dependencies
        project_deps = data.get("project", {}).get("dependencies", [])
        for dep_str in project_deps:
            dep = self._parse_requirement_string(dep_str)
            if dep:
                dep.source_file = pyproject_path
                dependencies.append(dep)

        # Optional dependencies
        optional_deps = data.get("project", {}).get("optional-dependencies", {})
        for group_deps in optional_deps.values():
            for dep_str in group_deps:
                dep = self._parse_requirement_string(dep_str)
                if dep:
                    dep.source_file = pyproject_path
                    dependencies.append(dep)

        # Poetry dependencies
        poetry_deps = data.get("tool", {}).get("poetry", {}).get("dependencies", {})
        for name, spec in poetry_deps.items():
            if name.lower() == "python":
                continue
            dep = self._parse_poetry_dep(name, spec)
            if dep:
                dep.source_file = pyproject_path
                dependencies.append(dep)

        # Poetry dev dependencies
        dev_deps = data.get("tool", {}).get("poetry", {}).get("dev-dependencies", {})
        for name, spec in dev_deps.items():
            dep = self._parse_poetry_dep(name, spec)
            if dep:
                dep.source_file = pyproject_path
                dependencies.append(dep)

        return dependencies

    def parse_requirements_txt(self) -> list[Dependency]:
        """Parse dependencies from requirements.txt.

        Returns:
            List of dependencies found
        """
        requirements_path = self.project_path / "requirements.txt"
        if not requirements_path.exists():
            return []

        dependencies = []

        try:
            content = requirements_path.read_text()
        except Exception:
            return []

        for line in content.splitlines():
            line = line.strip()
            # Skip comments and empty lines
            if not line or line.startswith("#") or line.startswith("-"):
                continue

            dep = self._parse_requirement_string(line)
            if dep:
                dep.source_file = requirements_path
                dependencies.append(dep)

        return dependencies

    def parse_setup_py(self) -> list[Dependency]:
        """Parse dependencies from setup.py (basic parsing).

        Returns:
            List of dependencies found
        """
        setup_path = self.project_path / "setup.py"
        if not setup_path.exists():
            return []

        # This is a very basic parser that looks for install_requires
        # A proper implementation would use AST parsing
        try:
            content = setup_path.read_text()
        except Exception:
            return []

        dependencies = []

        # Look for install_requires = [...] pattern
        import re

        match = re.search(r"install_requires\s*=\s*\[(.*?)\]", content, re.DOTALL)
        if match:
            deps_str = match.group(1)
            # Extract quoted strings
            for dep_match in re.finditer(r"['\"]([^'\"]+)['\"]", deps_str):
                dep = self._parse_requirement_string(dep_match.group(1))
                if dep:
                    dep.source_file = setup_path
                    dependencies.append(dep)

        return dependencies

    def get_dependency(self, name: str) -> Dependency | None:
        """Get a specific dependency by name.

        Args:
            name: Name of the dependency to find

        Returns:
            Dependency if found, None otherwise
        """
        all_deps = self.parse_all()
        name_lower = name.lower()
        for dep in all_deps:
            if dep.name.lower() == name_lower:
                return dep
        return None

    def _parse_requirement_string(self, req_str: str) -> Dependency | None:
        """Parse a requirement string like 'pydantic>=1.10,<2.0'.

        Args:
            req_str: The requirement string to parse

        Returns:
            Dependency object or None if parsing fails
        """
        try:
            req = Requirement(req_str)
            return Dependency(
                name=req.name,
                version_spec=str(req.specifier) if req.specifier else None,
                extras=list(req.extras) if req.extras else [],
            )
        except Exception:
            # Try basic parsing
            import re

            match = re.match(r"([a-zA-Z0-9_-]+)(.*)", req_str)
            if match:
                return Dependency(
                    name=match.group(1),
                    version_spec=match.group(2).strip() or None,
                )
            return None

    def _parse_poetry_dep(self, name: str, spec: Any) -> Dependency | None:
        """Parse a Poetry-style dependency specification.

        Args:
            name: Name of the dependency
            spec: Version specification (string, dict, or other)

        Returns:
            Dependency object or None
        """
        if isinstance(spec, str):
            # Simple version spec like "^1.10"
            version_spec = self._convert_poetry_version(spec)
            return Dependency(name=name, version_spec=version_spec)
        elif isinstance(spec, dict):
            version = spec.get("version", "")
            dict_version_spec: str | None = (
                self._convert_poetry_version(version) if version else None
            )
            extras = spec.get("extras", [])
            return Dependency(name=name, version_spec=dict_version_spec, extras=extras)

        return None

    def _convert_poetry_version(self, version: str) -> str:
        """Convert Poetry version syntax to PEP 440.

        Args:
            version: Poetry version string (e.g., "^1.10", "~1.10")

        Returns:
            PEP 440 compatible version string
        """
        if version.startswith("^"):
            # Caret: ^1.2.3 means >=1.2.3,<2.0.0
            base = version[1:]
            parts = base.split(".")
            if len(parts) >= 1:
                major = int(parts[0])
                return f">={base},<{major + 1}.0.0"
        elif version.startswith("~"):
            # Tilde: ~1.2.3 means >=1.2.3,<1.3.0
            base = version[1:]
            parts = base.split(".")
            if len(parts) >= 2:
                major_str = parts[0]
                minor = int(parts[1])
                return f">={base},<{major_str}.{minor + 1}.0"

        return version

    def update_dependency_version(self, name: str, new_version: str) -> list[tuple[Path, bool]]:
        """Update the version of a dependency in all source files.

        Args:
            name: Name of the dependency to update.
            new_version: New version to set (e.g., "2.5.0").

        Returns:
            List of (file_path, success) tuples for each file updated.
        """
        results = []

        # Try to update in pyproject.toml
        pyproject_path = self.project_path / "pyproject.toml"
        if pyproject_path.exists():
            success = self._update_pyproject_toml(name, new_version)
            results.append((pyproject_path, success))

        # Try to update in requirements.txt
        requirements_path = self.project_path / "requirements.txt"
        if requirements_path.exists():
            success = self._update_requirements_txt(name, new_version)
            results.append((requirements_path, success))

        # Try to update in setup.py
        setup_path = self.project_path / "setup.py"
        if setup_path.exists():
            success = self._update_setup_py(name, new_version)
            if success:
                results.append((setup_path, success))

        return results

    def _update_pyproject_toml(self, name: str, new_version: str) -> bool:
        """Update a dependency version in pyproject.toml.

        Args:
            name: Name of the dependency.
            new_version: New version to set.

        Returns:
            True if update was successful.
        """
        import re

        pyproject_path = self.project_path / "pyproject.toml"
        if not pyproject_path.exists():
            return False

        try:
            content = pyproject_path.read_text()
            original_content = content

            # Pattern for standard dependencies: "pydantic>=1.0,<2.0" or "pydantic==1.10.0"
            # Match the package name followed by version specifiers
            pattern = rf'("{name})((?:[><=!~]+[^"]*)?)"'
            replacement = rf'"\1>={new_version}"'
            content = re.sub(pattern, replacement, content, flags=re.IGNORECASE)

            # Pattern for Poetry dependencies: pydantic = "^1.10" or pydantic = {version = "^1.10"}
            # Simple string version
            poetry_pattern = rf'(\[tool\.poetry\.(?:dev-)?dependencies\].*?{name}\s*=\s*)"([^"]*)"'
            poetry_replacement = rf'\1"^{new_version}"'
            content = re.sub(
                poetry_pattern, poetry_replacement, content, flags=re.IGNORECASE | re.DOTALL
            )

            # Poetry dict version: version = "^1.10"
            poetry_dict_pattern = rf'({name}\s*=\s*\{{[^}}]*version\s*=\s*)"([^"]*)"'
            poetry_dict_replacement = rf'\1"^{new_version}"'
            content = re.sub(
                poetry_dict_pattern, poetry_dict_replacement, content, flags=re.IGNORECASE
            )

            if content != original_content:
                pyproject_path.write_text(content)
                return True

            return False

        except Exception:
            return False

    def _update_requirements_txt(self, name: str, new_version: str) -> bool:
        """Update a dependency version in requirements.txt.

        Args:
            name: Name of the dependency.
            new_version: New version to set.

        Returns:
            True if update was successful.
        """
        import re

        requirements_path = self.project_path / "requirements.txt"
        if not requirements_path.exists():
            return False

        try:
            content = requirements_path.read_text()
            original_content = content

            # Pattern: pydantic>=1.0 or pydantic==1.10.0 or just pydantic
            pattern = rf"^({name})([><=!~]+[^\s#]*)?(\s*#.*)?$"

            def replace_line(match: re.Match) -> str:
                pkg_name = match.group(1)
                comment = match.group(3) or ""
                return f"{pkg_name}>={new_version}{comment}"

            content = re.sub(pattern, replace_line, content, flags=re.IGNORECASE | re.MULTILINE)

            if content != original_content:
                requirements_path.write_text(content)
                return True

            return False

        except Exception:
            return False

    def _update_setup_py(self, name: str, new_version: str) -> bool:
        """Update a dependency version in setup.py.

        Args:
            name: Name of the dependency.
            new_version: New version to set.

        Returns:
            True if update was successful.
        """
        import re

        setup_path = self.project_path / "setup.py"
        if not setup_path.exists():
            return False

        try:
            content = setup_path.read_text()
            original_content = content

            # Pattern for install_requires entries: "pydantic>=1.0" or 'pydantic>=1.0'
            for quote in ['"', "'"]:
                pattern = rf"{quote}({name})([><=!~]+[^{quote}]*)?{quote}"
                replacement = rf"{quote}\1>={new_version}{quote}"
                content = re.sub(pattern, replacement, content, flags=re.IGNORECASE)

            if content != original_content:
                setup_path.write_text(content)
                return True

            return False

        except Exception:
            return False
