"""Loader for the knowledge base YAML files."""

from pathlib import Path
from typing import Optional

import yaml

from pyresolve.knowledge_base.models import LibraryKnowledge


class KnowledgeBaseLoader:
    """Loads and manages library knowledge bases."""

    def __init__(self, knowledge_base_dir: Optional[Path] = None):
        """Initialize the loader.

        Args:
            knowledge_base_dir: Directory containing the YAML files.
                              Defaults to the 'libraries' subdirectory.
        """
        if knowledge_base_dir is None:
            knowledge_base_dir = Path(__file__).parent / "libraries"
        self.knowledge_base_dir = knowledge_base_dir
        self._cache: dict[str, LibraryKnowledge] = {}

    def get_supported_libraries(self) -> list[str]:
        """Get a list of all supported library names."""
        libraries = []
        if self.knowledge_base_dir.exists():
            for yaml_file in self.knowledge_base_dir.glob("*.yaml"):
                libraries.append(yaml_file.stem)
        return sorted(libraries)

    def load(self, library_name: str) -> LibraryKnowledge:
        """Load the knowledge base for a specific library.

        Args:
            library_name: Name of the library (e.g., "pydantic")

        Returns:
            LibraryKnowledge object containing all breaking change info

        Raises:
            FileNotFoundError: If the knowledge base file doesn't exist
            ValueError: If the YAML file is invalid
        """
        if library_name in self._cache:
            return self._cache[library_name]

        yaml_path = self.knowledge_base_dir / f"{library_name}.yaml"
        if not yaml_path.exists():
            raise FileNotFoundError(
                f"No knowledge base found for library '{library_name}'. "
                f"Available libraries: {', '.join(self.get_supported_libraries())}"
            )

        try:
            with open(yaml_path) as f:
                data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML in knowledge base for '{library_name}': {e}") from e

        if not isinstance(data, dict):
            raise ValueError(f"Knowledge base for '{library_name}' must be a dictionary")

        knowledge = LibraryKnowledge.from_dict(data)
        self._cache[library_name] = knowledge
        return knowledge

    def is_migration_supported(self, library_name: str, from_version: str, to_version: str) -> bool:
        """Check if a specific migration path is supported.

        Args:
            library_name: Name of the library
            from_version: Starting version
            to_version: Target version

        Returns:
            True if the migration path is supported
        """
        try:
            knowledge = self.load(library_name)
        except FileNotFoundError:
            return False

        from packaging.version import Version

        from_v = Version(from_version)
        to_v = Version(to_version)

        for supported_from, supported_to in knowledge.supported_migrations:
            supported_from_v = Version(supported_from)
            supported_to_v = Version(supported_to)

            # Check if requested migration falls within a supported range
            if from_v >= supported_from_v and to_v <= supported_to_v:
                return True

        return False

    def clear_cache(self) -> None:
        """Clear the cached knowledge bases."""
        self._cache.clear()
