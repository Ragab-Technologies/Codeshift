"""Base transformer infrastructure for AST-based code migrations."""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

import libcst as cst


class TransformStatus(Enum):
    """Status of a transformation."""

    SUCCESS = "success"
    PARTIAL = "partial"  # Some transforms applied, some failed
    FAILED = "failed"
    NO_CHANGES = "no_changes"


@dataclass
class TransformChange:
    """Represents a single code change made by a transform."""

    description: str
    line_number: int
    original: str
    replacement: str
    transform_name: str
    confidence: float = 1.0  # 0.0 to 1.0
    notes: Optional[str] = None


@dataclass
class TransformResult:
    """Result of applying transforms to a file."""

    file_path: Path
    status: TransformStatus
    original_code: str
    transformed_code: str
    changes: list[TransformChange] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def has_changes(self) -> bool:
        """Check if any changes were made."""
        return self.original_code != self.transformed_code

    @property
    def change_count(self) -> int:
        """Get the number of changes made."""
        return len(self.changes)

    def get_diff_lines(self) -> list[str]:
        """Get a simple diff representation."""
        import difflib

        original_lines = self.original_code.splitlines(keepends=True)
        transformed_lines = self.transformed_code.splitlines(keepends=True)

        diff = difflib.unified_diff(
            original_lines,
            transformed_lines,
            fromfile=f"{self.file_path} (original)",
            tofile=f"{self.file_path} (transformed)",
        )
        return list(diff)


class BaseTransformer(cst.CSTTransformer):
    """Base class for LibCST transformers with change tracking."""

    def __init__(self) -> None:
        super().__init__()
        self.changes: list[TransformChange] = []
        self.errors: list[str] = []
        self._source_lines: list[str] = []

    def set_source(self, source: str) -> None:
        """Set the source code for reference during transforms."""
        self._source_lines = source.splitlines()

    def record_change(
        self,
        description: str,
        line_number: int,
        original: str,
        replacement: str,
        transform_name: str,
        confidence: float = 1.0,
        notes: Optional[str] = None,
    ) -> None:
        """Record a change made by the transformer."""
        self.changes.append(
            TransformChange(
                description=description,
                line_number=line_number,
                original=original,
                replacement=replacement,
                transform_name=transform_name,
                confidence=confidence,
                notes=notes,
            )
        )

    def record_error(self, error: str) -> None:
        """Record an error that occurred during transformation."""
        self.errors.append(error)

    def get_line(self, line_number: int) -> str:
        """Get a specific line from the source."""
        if 0 < line_number <= len(self._source_lines):
            return self._source_lines[line_number - 1]
        return ""


def transform_file(
    file_path: Path,
    transformer: BaseTransformer,
) -> TransformResult:
    """Transform a file using the given transformer.

    Args:
        file_path: Path to the file to transform
        transformer: The transformer to use

    Returns:
        TransformResult with the original and transformed code
    """
    try:
        original_code = file_path.read_text()
    except Exception as e:
        return TransformResult(
            file_path=file_path,
            status=TransformStatus.FAILED,
            original_code="",
            transformed_code="",
            errors=[f"Failed to read file: {e}"],
        )

    return transform_code(original_code, file_path, transformer)


def transform_code(
    source_code: str,
    file_path: Path,
    transformer: BaseTransformer,
) -> TransformResult:
    """Transform source code using the given transformer.

    Args:
        source_code: The source code to transform
        file_path: Path for reference in results
        transformer: The transformer to use

    Returns:
        TransformResult with the original and transformed code
    """
    try:
        tree = cst.parse_module(source_code)
    except cst.ParserSyntaxError as e:
        return TransformResult(
            file_path=file_path,
            status=TransformStatus.FAILED,
            original_code=source_code,
            transformed_code=source_code,
            errors=[f"Failed to parse file: {e}"],
        )

    transformer.set_source(source_code)

    try:
        transformed_tree = tree.visit(transformer)
        transformed_code = transformed_tree.code
    except Exception as e:
        return TransformResult(
            file_path=file_path,
            status=TransformStatus.FAILED,
            original_code=source_code,
            transformed_code=source_code,
            errors=[f"Transform failed: {e}"],
        )

    # Determine status
    if transformer.errors:
        if transformer.changes:
            status = TransformStatus.PARTIAL
        else:
            status = TransformStatus.FAILED
    elif transformer.changes:
        status = TransformStatus.SUCCESS
    else:
        status = TransformStatus.NO_CHANGES

    return TransformResult(
        file_path=file_path,
        status=status,
        original_code=source_code,
        transformed_code=transformed_code,
        changes=transformer.changes,
        errors=transformer.errors,
    )


def apply_transforms(
    file_path: Path,
    transformers: list[BaseTransformer],
) -> TransformResult:
    """Apply multiple transformers to a file in sequence.

    Args:
        file_path: Path to the file to transform
        transformers: List of transformers to apply in order

    Returns:
        Combined TransformResult
    """
    try:
        current_code = file_path.read_text()
    except Exception as e:
        return TransformResult(
            file_path=file_path,
            status=TransformStatus.FAILED,
            original_code="",
            transformed_code="",
            errors=[f"Failed to read file: {e}"],
        )

    original_code = current_code
    all_changes = []
    all_errors = []

    for transformer in transformers:
        result = transform_code(current_code, file_path, transformer)
        current_code = result.transformed_code
        all_changes.extend(result.changes)
        all_errors.extend(result.errors)

    # Determine final status
    if all_errors:
        if all_changes:
            status = TransformStatus.PARTIAL
        else:
            status = TransformStatus.FAILED
    elif all_changes:
        status = TransformStatus.SUCCESS
    else:
        status = TransformStatus.NO_CHANGES

    return TransformResult(
        file_path=file_path,
        status=status,
        original_code=original_code,
        transformed_code=current_code,
        changes=all_changes,
        errors=all_errors,
    )
