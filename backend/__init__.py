"""The Flask backend: the only process that opens a database connection.

Every database read and write the dashboard performs goes through this
package. The browser client issues no SQL and holds no credential; it calls
the HTTP routes here, and this package decides whether the answer comes from
PostgreSQL or from the repository's committed files.

Data flow:
    .env -> backend/config.py -> backend/repository/&#42; -> backend/api/&#42;
         -> HTTP -> dashboard/src/api/client.js -> the views
"""
