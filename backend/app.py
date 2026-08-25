"""The Flask application: the JSON API, and the built client beside it.

One process serves both, so a deployment is one service and one port. This is
the only process that opens a database connection; the Vue client is static
assets that fetch from the routes registered here.

Run it from the repository root:

    uv run --extra backend python -m backend.app

or under a production server:

    uv run --extra backend gunicorn --bind 0.0.0.0:8501 backend.wsgi:application

Data flow:
    backend/repository/&#42; -> backend/api/&#42; -> here -> dashboard/src/api/client.js
"""

from __future__ import annotations

import sys
import threading
import webbrowser
from pathlib import Path

# The module layer is imported as `modules.*`, which resolves only from the
# repository root. A service started from anywhere else -- a systemd unit, a
# container working directory, a process manager -- would otherwise fail on the
# first model import rather than at startup.
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from flask import Flask, jsonify, send_from_directory  # noqa: E402

from backend.api import dashboard as dashboard_api  # noqa: E402
from backend.api import jobs as jobs_api  # noqa: E402
from backend.api import models as models_api  # noqa: E402
from backend.api import settings as settings_api  # noqa: E402
from backend.config import (  # noqa: E402
    client_dist_directory,
    open_browser,
    server_host,
    server_port,
)

#: Requests larger than this are refused. The largest legitimate body is a
#: master-object draft, which is a few kilobytes; the model routes take paths
#: and options rather than data.
MAX_CONTENT_LENGTH = 256 * 1024


def create_app() -> Flask:
    """Build the application with every blueprint registered."""
    app = Flask(__name__, static_folder=None)
    app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH
    # Keys are emitted in the order the loaders produced them rather than
    # alphabetically, so the payload a reader inspects matches the order this
    # project's own documentation lists.
    app.config["JSON_SORT_KEYS"] = False

    app.register_blueprint(dashboard_api.blueprint)
    app.register_blueprint(jobs_api.blueprint)
    app.register_blueprint(settings_api.blueprint)
    app.register_blueprint(models_api.blueprint)

    _register_client(app)
    _register_error_handlers(app)
    return app


def _register_client(app: Flask) -> None:
    """Serve the built client, when one has been built beside this service.

    `vite build` writes it to `dashboard/dist`. A development run serves the
    sources from Vite instead and proxies `/api` here, so this branch is simply
    absent then. The client routes on the hash, so every non-API path resolves
    to the one document.
    """
    dist = client_dist_directory()
    if dist is None:
        return

    @app.get("/")
    def index():
        return send_from_directory(dist, "index.html")

    @app.get("/<path:requested>")
    def client(requested: str):
        if requested.startswith("api/"):
            return jsonify({"error": "not_found"}), 404
        candidate = dist / requested
        if candidate.is_file():
            return send_from_directory(dist, requested)
        return send_from_directory(dist, "index.html")


def _register_error_handlers(app: Flask) -> None:
    """Answer every error as JSON, because every client here speaks JSON.

    Flask's defaults are HTML pages. The client parses each response as JSON
    and reports a parse failure naming character 0, which hides the status that
    actually explains what went wrong.
    """

    @app.errorhandler(404)
    def not_found(error):
        return jsonify({"error": "not_found", "message": str(error)}), 404

    @app.errorhandler(405)
    def not_allowed(error):
        return jsonify({"error": "method_not_allowed", "message": str(error)}), 405

    @app.errorhandler(413)
    def too_large(error):
        return (
            jsonify(
                {
                    "error": "payload_too_large",
                    "message": (
                        f"The request body exceeds {MAX_CONTENT_LENGTH} bytes."
                    ),
                }
            ),
            413,
        )

    @app.errorhandler(500)
    def server_error(error):
        return jsonify({"error": "internal_error", "message": str(error)}), 500


def main() -> None:
    """Run the development server.

    Flask's own server is single-threaded by default, and this service polls
    job state while a stage runs, so threading is on. A production deployment
    runs the same application object under Gunicorn through `backend/wsgi.py`.
    """
    host = server_host()
    port = server_port()
    display = f"[{host}]" if ":" in host else host

    from backend.config import source_label

    print(f"[backend] Reading from {source_label()}")
    print(f"[backend] Listening on http://{display}:{port}")
    print("[backend] Press Ctrl+C to stop.")
    if open_browser():
        # Let Flask bind before the browser asks for the page. A missing GUI is
        # harmless: webbrowser returns False and the printed URL remains usable.
        threading.Timer(
            0.8, webbrowser.open, args=(f"http://localhost:{port}",)
        ).start()
    create_app().run(host=host, port=port, threaded=True)


if __name__ == "__main__":
    main()
