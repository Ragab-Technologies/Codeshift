"""Package manager detection and sync command generation utilities."""

import shutil
from pathlib import Path
from typing import Literal

PackageManager = Literal["uv", "poetry", "pip"]


def detect_package_manager(project_path: Path) -> PackageManager:
    """Detect the package manager used in a project.

    Detection order:
    1. uv.lock file presence → uv
    2. poetry.lock file presence → poetry
    3. Default → pip

    Args:
        project_path: Path to the project root directory.

    Returns:
        The detected package manager name.
    """
    # Check for uv (uv.lock file)
    if (project_path / "uv.lock").exists():
        return "uv"

    # Check for poetry (poetry.lock file)
    if (project_path / "poetry.lock").exists():
        return "poetry"

    # Default to pip
    return "pip"


def get_sync_command(project_path: Path) -> str:
    """Get the appropriate dependency sync command for the project.

    Args:
        project_path: Path to the project root directory.

    Returns:
        The shell command to sync/install dependencies.
    """
    manager = detect_package_manager(project_path)

    if manager == "uv":
        return "uv sync"
    elif manager == "poetry":
        return "poetry install"
    else:
        # pip - check what kind of project it is
        if (project_path / "pyproject.toml").exists():
            return "pip install -e ."
        elif (project_path / "requirements.txt").exists():
            return "pip install -r requirements.txt"
        else:
            return "pip install -e ."


def is_package_manager_available(manager: PackageManager) -> bool:
    """Check if a package manager is available in the system.

    Args:
        manager: The package manager to check.

    Returns:
        True if the package manager is available, False otherwise.
    """
    return shutil.which(manager) is not None


def get_install_commands(
    project_path: Path,
    libraries: list[dict[str, str]],
) -> list[str]:
    """Generate install commands for the upgraded libraries.

    This is a fallback for when users want to install specific packages
    rather than sync the entire project.

    Args:
        project_path: Path to the project root directory.
        libraries: List of dicts with 'name' and 'version' keys.

    Returns:
        List of install commands for each library.
    """
    manager = detect_package_manager(project_path)

    commands = []
    for lib in libraries:
        name = lib["name"]
        version = lib["version"]
        if manager == "uv":
            commands.append(f"uv add {name}>={version}")
        elif manager == "poetry":
            commands.append(f"poetry add {name}>={version}")
        else:
            commands.append(f"pip install {name}>={version}")

    return commands
