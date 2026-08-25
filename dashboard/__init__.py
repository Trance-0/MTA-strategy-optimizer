"""Database schema and configuration shared by Flask and the importer.

The dashboard is a Vue client over the Flask API in `backend/`: `src/` calls
`/api/*` and holds no database code of its own. This package owns the shared
`.env` contract in `config.py` and PostgreSQL schema in `models.py`; both the
Flask repositories and `script/import_to_database.py` import those definitions.

Data flow:
    .env -> config.py -> Flask repositories and script/import_to_database.py
    models.py declares the eighteen tables that the importer writes and Flask reads

Run the dashboard from the repository root:
    ./dashboard/run.sh          # dashboard\\run.bat on Windows
"""
