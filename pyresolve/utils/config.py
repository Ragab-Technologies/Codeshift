"""Configuration management for PyResolve."""

from dataclasses import dataclass, field
from pathlib import Path

import toml


@dataclass
class ProjectConfig:
    """Configuration loaded from pyproject.toml [tool.pyresolve] section."""

    exclude: list[str] = field(
        default_factory=lambda: [".pyresolve/*", "tests/*", ".venv/*", "venv/*"]
    )
    use_llm: bool = True
    anthropic_api_key: str | None = None
    cache_dir: Path = field(default_factory=lambda: Path.home() / ".pyresolve" / "cache")

    @classmethod
    def from_pyproject(cls, project_path: Path) -> "ProjectConfig":
        """Load configuration from pyproject.toml if it exists."""
        pyproject_path = project_path / "pyproject.toml"
        config = cls()

        if pyproject_path.exists():
            try:
                data = toml.load(pyproject_path)
                pyresolve_config = data.get("tool", {}).get("pyresolve", {})

                if "exclude" in pyresolve_config:
                    config.exclude = pyresolve_config["exclude"]
                if "use_llm" in pyresolve_config:
                    config.use_llm = pyresolve_config["use_llm"]
                if "anthropic_api_key" in pyresolve_config:
                    config.anthropic_api_key = pyresolve_config["anthropic_api_key"]
                if "cache_dir" in pyresolve_config:
                    config.cache_dir = Path(pyresolve_config["cache_dir"])
            except Exception:
                # If we can't parse the config, use defaults
                pass

        return config


@dataclass
class Config:
    """Runtime configuration for a PyResolve session."""

    project_path: Path
    target_library: str
    target_version: str
    project_config: ProjectConfig = field(default_factory=ProjectConfig)
    state_file: Path | None = None
    dry_run: bool = False
    verbose: bool = False

    def __post_init__(self) -> None:
        """Initialize derived fields."""
        if self.state_file is None:
            self.state_file = self.project_path / ".pyresolve" / "state.json"

    @property
    def pyresolve_dir(self) -> Path:
        """Get the .pyresolve directory for this project."""
        return self.project_path / ".pyresolve"

    def ensure_dirs(self) -> None:
        """Ensure required directories exist."""
        self.pyresolve_dir.mkdir(parents=True, exist_ok=True)
        self.project_config.cache_dir.mkdir(parents=True, exist_ok=True)
