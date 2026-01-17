"""CLI commands for PyResolve."""

from pyresolve.cli.commands.apply import apply
from pyresolve.cli.commands.diff import diff
from pyresolve.cli.commands.upgrade import upgrade

__all__ = ["upgrade", "diff", "apply"]
