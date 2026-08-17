"""Database schema and configuration shared by the dashboard and the importer.

The dashboard itself is a Vue client over a Node API and holds no Python: see
`dashboard/server/` and `dashboard/src/`. What remains here is the part
`script/import_to_database.py` needs — the `.env` contract in `config.py` and
the PostgreSQL schema in `models.py` — kept in this package because the
dashboard's own reader is the only consumer of the tables it defines.

Data flow:
    .env -> config.py -> script/import_to_database.py -> the PostgreSQL mirror
    models.py declares the eighteen tables that import writes

Run the dashboard from the repository root:
    ./dashboard/run.sh          # dashboard\\run.bat on Windows
"""
