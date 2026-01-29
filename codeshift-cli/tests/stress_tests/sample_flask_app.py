"""
Sample Flask Application for CLI migration testing.
This file contains Flask 2.x code that needs migration to 3.x.
"""

import os
from datetime import datetime

from flask import (
    Blueprint,
    Flask,
    Markup,
    escape,
    flash,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    send_from_directory,
    url_for,
)
from flask.globals import _app_ctx_stack, _request_ctx_stack


# Configuration
class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-key")
    DATABASE_URI = os.environ.get("DATABASE_URL", "sqlite:///app.db")


# App initialization
def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Load JSON config (deprecated in Flask 2.3+)
    if os.path.exists("config.json"):
        app.config.from_json("config.json")

    # Register blueprints
    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp)

    return app


# Main Blueprint
main_bp = Blueprint("main", __name__)


@main_bp.before_request
def before_request():
    """Set up request context."""
    g.start_time = datetime.utcnow()
    # Using deprecated context stack
    ctx = _request_ctx_stack.top
    if ctx:
        g.ctx = ctx


@main_bp.route("/")
def index():
    """Home page."""
    user_name = request.args.get("name", "World")
    # Using deprecated escape from flask
    safe_name = escape(user_name)
    # Using deprecated Markup from flask
    greeting = Markup(f"<h1>Hello, {safe_name}!</h1>")
    return greeting


@main_bp.route("/contact", methods=["GET", "POST"])
def contact():
    """Contact form."""
    if request.method == "POST":
        name = escape(request.form.get("name", ""))
        email = request.form.get("email", "")
        message = escape(request.form.get("message", ""))

        flash("Message received!", "success")
        return redirect(url_for("main.index"))

    return render_template("contact.html")


@main_bp.route("/download/<filename>")
def download_file(filename):
    """Download a file with deprecated parameters."""
    return send_file(
        f"files/{filename}",
        attachment_filename=filename,  # Deprecated: now download_name
        cache_timeout=3600,  # Deprecated: now max_age
        as_attachment=True
    )


@main_bp.route("/static/<path:filename>")
def serve_static(filename):
    """Serve static files with deprecated parameter."""
    return send_from_directory(
        "static",
        filename=filename  # Deprecated: now path
    )


@main_bp.route("/export")
def export_data():
    """Export data with deprecated send_file params."""
    data = {"key": "value"}
    return send_file(
        "export.json",
        attachment_filename="data_export.json",
        cache_timeout=0,
        add_etags=True  # Deprecated: now etag
    )


# API Blueprint
api_bp = Blueprint("api", __name__, url_prefix="/api")


@api_bp.before_request
def api_before_request():
    """Set up API context."""
    g.api_version = "v1"
    # Using deprecated app context stack
    ctx = _app_ctx_stack.top
    if ctx:
        g.app_ctx = ctx


@api_bp.route("/health")
def health():
    """Health check endpoint."""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat()
    })


@api_bp.route("/users", methods=["GET"])
def list_users():
    """List users."""
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)

    return jsonify({
        "users": [],
        "page": page,
        "per_page": per_page
    })


@api_bp.route("/users/<int:user_id>", methods=["GET"])
def get_user(user_id):
    """Get user by ID."""
    return jsonify({"id": user_id, "name": "Test User"})


@api_bp.route("/users", methods=["POST"])
def create_user():
    """Create a new user."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    # Using escape on user input
    safe_name = str(escape(data.get("name", "")))

    return jsonify({
        "id": 1,
        "name": safe_name
    }), 201


@api_bp.route("/posts", methods=["GET"])
def list_posts():
    """List posts."""
    return jsonify({"posts": []})


@api_bp.route("/posts/<int:post_id>", methods=["GET", "PUT", "DELETE"])
def manage_post(post_id):
    """Manage a single post."""
    if request.method == "GET":
        return jsonify({"id": post_id, "title": "Test Post"})
    elif request.method == "PUT":
        data = request.get_json()
        return jsonify({"id": post_id, **data})
    else:
        return jsonify({"deleted": True}), 200


# Error handlers
def register_error_handlers(app):
    """Register error handlers."""

    @app.errorhandler(404)
    def not_found(error):
        if request.is_json:
            return jsonify({"error": "Not found"}), 404
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def internal_error(error):
        if request.is_json:
            return jsonify({"error": "Internal server error"}), 500
        return render_template("errors/500.html"), 500


# App instance
app = create_app()

# Check deprecated app.env property
if app.env == "development":
    app.debug = True

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
