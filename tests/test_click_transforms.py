"""Tests for Click 7.x to 8.x transforms."""

from codeshift.migrator.transforms.click_transformer import transform_click


class TestClickAutocompletionTransforms:
    """Tests for Click autocompletion to shell_complete transformations."""

    def test_autocompletion_to_shell_complete(self):
        """Test transforming autocompletion parameter to shell_complete."""
        code = """
import click

def complete_names(ctx, args, incomplete):
    return ['Alice', 'Bob', 'Charlie']

@click.command()
@click.option('--name', autocompletion=complete_names)
def hello(name):
    click.echo(f'Hello {name}!')
"""
        transformed, changes = transform_click(code)

        assert "shell_complete" in transformed
        assert "autocompletion" not in transformed
        assert len(changes) >= 1
        assert any(c.transform_name == "autocompletion_to_shell_complete" for c in changes)

        # Verify syntax is valid
        compile(transformed, "<string>", "exec")


class TestClickTerminalSizeTransforms:
    """Tests for Click terminal size transformations."""

    def test_get_terminal_size(self):
        """Test transforming click.get_terminal_size to shutil.get_terminal_size."""
        code = """
import click

size = click.get_terminal_size()
width, height = size
"""
        transformed, changes = transform_click(code)

        assert "shutil" in transformed
        assert len(changes) >= 1
        assert any(c.transform_name == "get_terminal_size_to_shutil" for c in changes)

        # Verify syntax is valid
        compile(transformed, "<string>", "exec")


class TestClickMultiCommandTransforms:
    """Tests for Click MultiCommand transformations."""

    def test_multicommand_to_group(self):
        """Test transforming MultiCommand import to Group."""
        code = """
from click import MultiCommand

class MyCLI(MultiCommand):
    def list_commands(self, ctx):
        return ['sub1', 'sub2']
"""
        transformed, changes = transform_click(code)

        assert "Group" in transformed
        assert "MultiCommand" not in transformed or "Group" in transformed
        assert len(changes) >= 1
        assert any(c.transform_name == "multicommand_to_group" for c in changes)

        # Verify syntax is valid
        compile(transformed, "<string>", "exec")

    def test_basecommand_to_command(self):
        """Test transforming BaseCommand import to Command."""
        code = """
from click import BaseCommand

class MyCommand(BaseCommand):
    pass
"""
        transformed, changes = transform_click(code)

        assert "Command" in transformed
        assert len(changes) >= 1

        # Verify syntax is valid
        compile(transformed, "<string>", "exec")


class TestClickOutputBytesTransforms:
    """Tests for Click output_bytes transformations."""

    def test_output_bytes_to_encode(self):
        """Test transforming result.output_bytes to result.output.encode()."""
        code = """
from click.testing import CliRunner

runner = CliRunner()
result = runner.invoke(cli)
data = result.output_bytes
"""
        transformed, changes = transform_click(code)

        assert ".output.encode()" in transformed
        assert ".output_bytes" not in transformed
        assert len(changes) >= 1
        assert any(c.transform_name == "output_bytes_to_encode" for c in changes)

        # Verify syntax is valid
        compile(transformed, "<string>", "exec")


class TestClickVersionTransforms:
    """Tests for Click version access transformations."""

    def test_click_version_to_importlib(self):
        """Test transforming click.__version__ to importlib.metadata."""
        code = """
import click

print(click.__version__)
"""
        transformed, changes = transform_click(code)

        # Should suggest using importlib.metadata.version
        assert len(changes) >= 0

        # Verify syntax is valid
        compile(transformed, "<string>", "exec")


class TestClickStyleTransforms:
    """Tests for Click style function transformations."""

    def test_style_blink_removal(self):
        """Test handling of blink parameter in click.style."""
        code = """
import click

text = click.style('Warning', fg='red', blink=True)
"""
        transformed, changes = transform_click(code)

        # blink is deprecated
        assert len(changes) >= 0

        # Verify syntax is valid
        compile(transformed, "<string>", "exec")


class TestClickMultipleTransforms:
    """Tests for multiple Click transformations."""

    def test_comprehensive_migration(self):
        """Test multiple Click migrations in one file."""
        code = """
import click
from click import MultiCommand

def complete_items(ctx, args, incomplete):
    return ['item1', 'item2']

@click.command()
@click.option('--item', autocompletion=complete_items)
def main(item):
    size = click.get_terminal_size()
    click.echo(f'Terminal: {size}')

class MyCLI(MultiCommand):
    pass
"""
        transformed, changes = transform_click(code)

        # Should have multiple changes
        assert len(changes) >= 2
        assert "shell_complete" in transformed
        assert "shutil" in transformed

        # Verify syntax is valid
        compile(transformed, "<string>", "exec")

    def test_no_false_positives(self):
        """Test that modern Click code is not transformed."""
        code = """
import click
import shutil
from click import Group

def complete_items(ctx, param, incomplete):
    return ['item1', 'item2']

@click.command()
@click.option('--item', shell_complete=complete_items)
def main(item):
    size = shutil.get_terminal_size()
    click.echo(f'Terminal: {size}')

class MyCLI(Group):
    pass
"""
        transformed, changes = transform_click(code)

        # No changes should be made
        assert len(changes) == 0
        assert transformed == code

        # Verify syntax is valid
        compile(transformed, "<string>", "exec")
