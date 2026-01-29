"""
Old Click patterns that need migration.
Uses deprecated patterns from Click 7.x that changed in Click 8.x+
"""
import click
from click import command, option, group, argument

# Old pattern: Using deprecated autocompletion parameter
@click.command()
@click.option(
    '--name', '-n',
    # Deprecated: autocompletion renamed to shell_complete in Click 8.0
    autocompletion=lambda: ['Alice', 'Bob', 'Charlie']
)
def greet(name):
    """Old autocompletion pattern."""
    click.echo(f'Hello, {name}!')

# Old pattern: Using deprecated result_callback with old signature
@click.group()
@click.pass_context
def cli(ctx):
    """Old group pattern."""
    ctx.ensure_object(dict)

# Deprecated: Using @cli.resultcallback without proper pass_context
@cli.resultcallback()
def process_result(result):
    """Old result callback pattern."""
    click.echo(f'Result: {result}')

# Old pattern: Using deprecated prompt with old parameters
@cli.command()
@click.option(
    '--password',
    prompt=True,
    hide_input=True,
    # Deprecated: confirmation_prompt used differently
    confirmation_prompt=True
)
def login(password):
    """Old password prompt pattern."""
    click.echo('Logged in!')

# Old pattern: Using deprecated file handling
@cli.command()
@click.argument('input', type=click.File('r'))
@click.argument('output', type=click.File('w'))
def process(input, output):
    """Old file handling pattern."""
    # Deprecated: Using atomic writes without proper context
    for line in input:
        output.write(line.upper())

# Old pattern: Using deprecated Path type parameters
@cli.command()
@click.argument(
    'path',
    type=click.Path(
        exists=True,
        # Deprecated: Using file_okay/dir_okay separately
        file_okay=True,
        dir_okay=False,
        # Deprecated: readable/writable parameters
        readable=True,
        resolve_path=True
    )
)
def read_file(path):
    """Old path handling pattern."""
    with open(path) as f:
        click.echo(f.read())

# Old pattern: Using deprecated echo parameters
def output_old_style(message, is_error=False):
    """Old echo pattern."""
    # Deprecated: Using color parameter style
    click.echo(message, err=is_error, color=True)
    # Old pattern: Using click.secho with old parameters
    click.secho(message, fg='green', bold=True, blink=True)  # blink deprecated

# Old pattern: Using deprecated progressbar
@cli.command()
def long_process():
    """Old progressbar pattern."""
    items = range(100)
    # Deprecated: Using old progressbar parameters
    with click.progressbar(
        items,
        label='Processing',
        # Deprecated parameters
        show_eta=True,
        show_percent=True,
        show_pos=True,
        item_show_func=str
    ) as bar:
        for item in bar:
            pass

# Old pattern: Using deprecated Choice with case sensitivity
@cli.command()
@click.option(
    '--size',
    type=click.Choice(['small', 'medium', 'large']),
    # Deprecated: case_sensitive default changed
    case_sensitive=True
)
def order(size):
    """Old Choice pattern."""
    click.echo(f'Ordered: {size}')

# Old pattern: Using deprecated IntRange/FloatRange
@cli.command()
@click.option(
    '--count',
    # Deprecated: Using IntRange with old parameters
    type=click.IntRange(0, 100, clamp=True)  # clamp behavior changed
)
def count_items(count):
    """Old IntRange pattern."""
    click.echo(f'Count: {count}')

# Old pattern: Using deprecated testing with CliRunner
def test_cli_old():
    """Old testing pattern."""
    from click.testing import CliRunner
    runner = CliRunner()
    # Deprecated: Using mix_stderr parameter
    result = runner.invoke(cli, ['--help'], mix_stderr=False)
    return result.output

# Old pattern: Using deprecated exception handling
@cli.command()
def risky_operation():
    """Old exception handling pattern."""
    try:
        raise ValueError('Something went wrong')
    except ValueError as e:
        # Deprecated: Using click.ClickException with old patterns
        raise click.ClickException(str(e))

if __name__ == '__main__':
    cli()
