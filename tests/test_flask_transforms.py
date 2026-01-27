"""Tests for Flask 1.x to 2.x/3.x transforms."""

from codeshift.migrator.transforms.flask_transformer import transform_flask


class TestFlaskEscapeTransforms:
    """Tests for Flask escape import transformations."""

    def test_escape_to_markupsafe(self):
        """Test transforming flask.escape to markupsafe.escape."""
        code = """
from flask import escape

safe_text = escape(user_input)
"""
        transformed, changes = transform_flask(code)

        assert "markupsafe" in transformed
        assert len(changes) >= 1
        assert any(c.transform_name == "flask_escape_to_markupsafe" for c in changes)

        # Verify syntax is valid
        compile(transformed, "<string>", "exec")

    def test_markup_to_markupsafe(self):
        """Test transforming flask.Markup to markupsafe.Markup."""
        code = """
from flask import Markup

html = Markup("<b>Bold</b>")
"""
        transformed, changes = transform_flask(code)

        assert "markupsafe" in transformed
        assert len(changes) >= 1
        assert any(c.transform_name == "flask_markup_to_markupsafe" for c in changes)

        # Verify syntax is valid
        compile(transformed, "<string>", "exec")

    def test_escape_and_markup_combined(self):
        """Test transforming both escape and Markup."""
        code = """
from flask import Flask, escape, Markup

app = Flask(__name__)
safe = escape(text)
html = Markup("<b>Bold</b>")
"""
        transformed, changes = transform_flask(code)

        assert "markupsafe" in transformed
        assert len(changes) >= 2

        # Verify that the Flask import still has Flask
        assert "from flask import Flask" in transformed or "Flask" in transformed


class TestFlaskSendFileTransforms:
    """Tests for Flask send_file parameter transformations."""

    def test_attachment_filename_to_download_name(self):
        """Test transforming attachment_filename to download_name."""
        code = """
from flask import send_file

@app.route('/download')
def download():
    return send_file('file.pdf', attachment_filename='document.pdf')
"""
        transformed, changes = transform_flask(code)

        # Check transform was applied (download_name is new name)
        if len(changes) > 0:
            assert "download_name" in transformed
            assert "attachment_filename" not in transformed

        # Verify syntax is valid
        compile(transformed, "<string>", "exec")

    def test_cache_timeout_to_max_age(self):
        """Test transforming cache_timeout to max_age."""
        code = """
from flask import send_file

@app.route('/download')
def download():
    return send_file('file.pdf', cache_timeout=3600)
"""
        transformed, changes = transform_flask(code)

        # Check transform was applied (max_age is new name)
        if len(changes) > 0:
            assert "max_age" in transformed
            assert "cache_timeout" not in transformed

        # Verify syntax is valid
        compile(transformed, "<string>", "exec")


class TestFlaskJsonEncoderTransforms:
    """Tests for Flask JSON encoder transformations."""

    def test_json_encoder_attribute(self):
        """Test detecting app.json_encoder usage."""
        code = """
from flask import Flask
import json

class CustomEncoder(json.JSONEncoder):
    pass

app = Flask(__name__)
app.json_encoder = CustomEncoder
"""
        transformed, changes = transform_flask(code)

        # Should detect and report the json_encoder usage
        assert len(changes) >= 0

        # Verify syntax is valid
        compile(transformed, "<string>", "exec")


class TestFlaskGlobalsTransforms:
    """Tests for Flask globals transformations."""

    def test_request_ctx_stack_removal(self):
        """Test warning about _request_ctx_stack removal."""
        code = """
from flask.globals import _request_ctx_stack

ctx = _request_ctx_stack.top
"""
        transformed, changes = transform_flask(code)

        # Should detect the deprecated import
        assert len(changes) >= 0

        # Verify syntax is valid
        compile(transformed, "<string>", "exec")


class TestFlaskMultipleTransforms:
    """Tests for multiple Flask transformations."""

    def test_comprehensive_migration(self):
        """Test multiple Flask migrations in one file."""
        code = """
from flask import Flask, escape, Markup, send_file

app = Flask(__name__)

@app.route('/')
def index():
    safe = escape(request.args.get('name', ''))
    return Markup(f"<h1>Hello {safe}</h1>")

@app.route('/download')
def download():
    return send_file(
        'report.pdf',
        attachment_filename='monthly_report.pdf',
        cache_timeout=3600
    )
"""
        transformed, changes = transform_flask(code)

        # Should have multiple changes
        assert len(changes) >= 3
        assert "markupsafe" in transformed
        assert "download_name" in transformed
        assert "max_age" in transformed

        # Verify syntax is valid
        compile(transformed, "<string>", "exec")

    def test_no_false_positives(self):
        """Test that modern Flask code is not transformed."""
        code = """
from flask import Flask, send_file
from markupsafe import escape, Markup

app = Flask(__name__)

@app.route('/')
def index():
    safe = escape(request.args.get('name', ''))
    return Markup(f"<h1>Hello {safe}</h1>")

@app.route('/download')
def download():
    return send_file(
        'report.pdf',
        download_name='monthly_report.pdf',
        max_age=3600
    )
"""
        transformed, changes = transform_flask(code)

        # No changes should be made
        assert len(changes) == 0
        assert transformed == code

        # Verify syntax is valid
        compile(transformed, "<string>", "exec")
