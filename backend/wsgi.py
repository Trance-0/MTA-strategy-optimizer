"""The entry point a production server imports.

Gunicorn, uWSGI, and every other Web Server Gateway Interface server expects a
module-level callable. Keeping it in its own file means the application is
built once at import rather than on every worker's first request, and means
`backend/app.py` stays runnable directly for development without the two
disagreeing about how the app is constructed.

    uv run --extra backend gunicorn --bind 0.0.0.0:8501 backend.wsgi:application

Data flow:
    a WSGI server -> here -> backend/app.py -> the blueprints
"""

from __future__ import annotations

from backend.app import create_app

application = create_app()

#: Gunicorn's documentation and most process managers use `app`; both names
#: refer to the same object so neither convention needs a wrapper.
app = application
