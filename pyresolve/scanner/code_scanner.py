"""Code scanner for finding library imports and usage."""

from dataclasses import dataclass, field
from pathlib import Path

import libcst as cst
from libcst.metadata import MetadataWrapper, PositionProvider


@dataclass
class ImportInfo:
    """Information about an import statement."""

    module: str  # e.g., "pydantic"
    names: list[str]  # e.g., ["BaseModel", "Field"]
    alias: str | None = None  # e.g., "pd" for "import pandas as pd"
    file_path: Path = field(default_factory=Path)
    line_number: int = 0
    is_from_import: bool = False  # True for "from x import y"

    @property
    def full_import(self) -> str:
        """Get the full import string."""
        if self.is_from_import:
            names_str = ", ".join(self.names)
            return f"from {self.module} import {names_str}"
        if self.alias:
            return f"import {self.module} as {self.alias}"
        return f"import {self.module}"


@dataclass
class UsageInfo:
    """Information about a symbol usage."""

    symbol: str  # e.g., "BaseModel", "user.dict()"
    usage_type: str  # "class", "function", "method_call", "attribute", "decorator"
    file_path: Path = field(default_factory=Path)
    line_number: int = 0
    column: int = 0
    context: str = ""  # Surrounding code for context

    @property
    def location(self) -> str:
        """Get a human-readable location string."""
        return f"{self.file_path}:{self.line_number}:{self.column}"


class ImportVisitor(cst.CSTVisitor):
    """Visitor to collect import statements for a specific library."""

    METADATA_DEPENDENCIES = (PositionProvider,)

    def __init__(self, target_library: str):
        self.target_library = target_library
        self.imports: list[ImportInfo] = []
        self._imported_names: set[str] = set()

    def visit_Import(self, node: cst.Import) -> None:
        """Visit import statements like 'import pydantic'."""
        for name in node.names if isinstance(node.names, tuple) else []:
            if isinstance(name, cst.ImportAlias):
                module_name = self._get_name_value(name.name)
                if module_name and module_name.startswith(self.target_library):
                    alias = None
                    if name.asname and isinstance(name.asname, cst.AsName):
                        alias = self._get_name_value(name.asname.name)

                    pos = self.get_metadata(PositionProvider, node)
                    self.imports.append(
                        ImportInfo(
                            module=module_name,
                            names=[module_name],
                            alias=alias,
                            line_number=pos.start.line if pos else 0,
                            is_from_import=False,
                        )
                    )
                    self._imported_names.add(alias or module_name)

    def visit_ImportFrom(self, node: cst.ImportFrom) -> None:
        """Visit from-import statements like 'from pydantic import BaseModel'."""
        if node.module is None:
            return

        module_name = self._get_name_value(node.module)
        if not module_name or not module_name.startswith(self.target_library):
            return

        names = []
        if isinstance(node.names, cst.ImportStar):
            names = ["*"]
            self._imported_names.add("*")
        elif isinstance(node.names, tuple):
            for name in node.names:
                if isinstance(name, cst.ImportAlias):
                    imported_name = self._get_name_value(name.name)
                    if imported_name:
                        names.append(imported_name)
                        if name.asname and isinstance(name.asname, cst.AsName):
                            alias = self._get_name_value(name.asname.name)
                            self._imported_names.add(alias or imported_name)
                        else:
                            self._imported_names.add(imported_name)

        if names:
            pos = self.get_metadata(PositionProvider, node)
            self.imports.append(
                ImportInfo(
                    module=module_name,
                    names=names,
                    line_number=pos.start.line if pos else 0,
                    is_from_import=True,
                )
            )

    def _get_name_value(self, node: cst.BaseExpression) -> str | None:
        """Extract the string value from a Name or Attribute node."""
        if isinstance(node, cst.Name):
            return str(node.value)
        if isinstance(node, cst.Attribute):
            base = self._get_name_value(node.value)
            if base:
                return f"{base}.{node.attr.value}"
        return None

    @property
    def imported_names(self) -> set[str]:
        """Get all imported names from the target library."""
        return self._imported_names


class UsageVisitor(cst.CSTVisitor):
    """Visitor to collect usage of imported symbols."""

    METADATA_DEPENDENCIES = (PositionProvider,)

    def __init__(self, imported_names: set[str], target_library: str):
        self.imported_names = imported_names
        self.target_library = target_library
        self.usages: list[UsageInfo] = []

    def visit_ClassDef(self, node: cst.ClassDef) -> None:
        """Visit class definitions to find BaseModel subclasses."""
        for base in node.bases:
            base_name = self._get_name_value(base.value)
            if base_name and base_name in self.imported_names:
                pos = self.get_metadata(PositionProvider, node)
                self.usages.append(
                    UsageInfo(
                        symbol=base_name,
                        usage_type="class_inheritance",
                        line_number=pos.start.line if pos else 0,
                        context=f"class {node.name.value}({base_name})",
                    )
                )

    def visit_Decorator(self, node: cst.Decorator) -> None:
        """Visit decorators like @validator."""
        decorator_name = self._get_name_value(node.decorator)
        if not decorator_name:
            # Handle decorator calls like @validator("field")
            if isinstance(node.decorator, cst.Call):
                decorator_name = self._get_name_value(node.decorator.func)

        if decorator_name and decorator_name in self.imported_names:
            pos = self.get_metadata(PositionProvider, node)
            self.usages.append(
                UsageInfo(
                    symbol=decorator_name,
                    usage_type="decorator",
                    line_number=pos.start.line if pos else 0,
                    context=f"@{decorator_name}",
                )
            )

    def visit_Call(self, node: cst.Call) -> None:
        """Visit function/method calls."""
        # Handle method calls like .dict(), .json(), etc.
        if isinstance(node.func, cst.Attribute):
            method_name = node.func.attr.value
            if method_name in {
                "dict",
                "json",
                "schema",
                "schema_json",
                "parse_obj",
                "parse_raw",
                "parse_file",
                "copy",
                "update_forward_refs",
            }:
                pos = self.get_metadata(PositionProvider, node)
                self.usages.append(
                    UsageInfo(
                        symbol=f".{method_name}()",
                        usage_type="method_call",
                        line_number=pos.start.line if pos else 0,
                        context=f".{method_name}()",
                    )
                )

        # Handle direct function calls like Field()
        func_name = self._get_name_value(node.func)
        if func_name and func_name in self.imported_names:
            pos = self.get_metadata(PositionProvider, node)
            self.usages.append(
                UsageInfo(
                    symbol=func_name,
                    usage_type="function_call",
                    line_number=pos.start.line if pos else 0,
                    context=f"{func_name}()",
                )
            )

    def visit_Attribute(self, node: cst.Attribute) -> None:
        """Visit attribute access like __fields__."""
        attr_name = node.attr.value
        if attr_name in {"__fields__", "__validators__", "model_fields"}:
            pos = self.get_metadata(PositionProvider, node)
            self.usages.append(
                UsageInfo(
                    symbol=attr_name,
                    usage_type="attribute",
                    line_number=pos.start.line if pos else 0,
                    context=attr_name,
                )
            )

    def _get_name_value(self, node: cst.BaseExpression) -> str | None:
        """Extract the string value from a Name or Attribute node."""
        if isinstance(node, cst.Name):
            return str(node.value)
        if isinstance(node, cst.Attribute):
            base = self._get_name_value(node.value)
            if base:
                return f"{base}.{node.attr.value}"
        return None


@dataclass
class ScanResult:
    """Result of scanning a codebase."""

    imports: list[ImportInfo] = field(default_factory=list)
    usages: list[UsageInfo] = field(default_factory=list)
    files_scanned: int = 0
    files_with_imports: int = 0
    errors: list[tuple[Path, str]] = field(default_factory=list)

    @property
    def has_library_usage(self) -> bool:
        """Check if the library is used in the codebase."""
        return len(self.imports) > 0


class CodeScanner:
    """Scanner for finding library usage in Python code."""

    def __init__(self, target_library: str, exclude_patterns: list[str] | None = None):
        """Initialize the scanner.

        Args:
            target_library: Name of the library to scan for (e.g., "pydantic")
            exclude_patterns: Glob patterns for paths to exclude
        """
        self.target_library = target_library
        self.exclude_patterns = exclude_patterns or []

    def scan_file(self, file_path: Path) -> tuple[list[ImportInfo], list[UsageInfo]]:
        """Scan a single file for library usage.

        Args:
            file_path: Path to the Python file

        Returns:
            Tuple of (imports, usages) found in the file

        Raises:
            SyntaxError: If the file has invalid Python syntax
        """
        source_code = file_path.read_text()

        try:
            tree = cst.parse_module(source_code)
        except cst.ParserSyntaxError as e:
            raise SyntaxError(f"Invalid Python syntax in {file_path}: {e}") from e

        wrapper = MetadataWrapper(tree)

        # First pass: find imports
        import_visitor = ImportVisitor(self.target_library)
        wrapper.visit(import_visitor)

        # Update file paths in imports
        for imp in import_visitor.imports:
            imp.file_path = file_path

        # Second pass: find usages (only if we have imports)
        usages = []
        if import_visitor.imported_names:
            usage_visitor = UsageVisitor(import_visitor.imported_names, self.target_library)
            wrapper.visit(usage_visitor)
            for usage in usage_visitor.usages:
                usage.file_path = file_path
            usages = usage_visitor.usages

        return import_visitor.imports, usages

    def scan_directory(self, directory: Path) -> ScanResult:
        """Scan a directory for library usage.

        Args:
            directory: Path to the directory to scan

        Returns:
            ScanResult containing all imports and usages found
        """
        result = ScanResult()

        # Find all Python files
        python_files = list(directory.rglob("*.py"))

        for file_path in python_files:
            # Check exclude patterns
            relative_path = str(file_path.relative_to(directory))
            if self._should_exclude(relative_path):
                continue

            result.files_scanned += 1

            try:
                imports, usages = self.scan_file(file_path)
                if imports:
                    result.files_with_imports += 1
                    result.imports.extend(imports)
                    result.usages.extend(usages)
            except SyntaxError as e:
                result.errors.append((file_path, str(e)))
            except Exception as e:
                result.errors.append((file_path, f"Error scanning file: {e}"))

        return result

    def _should_exclude(self, path: str) -> bool:
        """Check if a path should be excluded based on patterns."""
        import fnmatch

        for pattern in self.exclude_patterns:
            if fnmatch.fnmatch(path, pattern):
                return True
        return False
