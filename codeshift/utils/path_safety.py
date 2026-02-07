"""Path validation utilities to prevent path traversal attacks."""

from pathlib import Path


def validate_file_within_project(file_path: Path, project_path: Path) -> Path:
    """Ensure a file path resolves to within the project directory.

    Args:
        file_path: The file path to validate (may be relative or absolute).
        project_path: The project root directory (must be resolved).

    Returns:
        The resolved, validated file path.

    Raises:
        ValueError: If the file path resolves to outside the project directory.
    """
    resolved = file_path.resolve()
    project_resolved = project_path.resolve()

    if not resolved.is_relative_to(project_resolved):
        raise ValueError(
            f"File path '{file_path}' resolves to outside the project directory. "
            f"Expected paths within '{project_resolved}'."
        )

    return resolved
