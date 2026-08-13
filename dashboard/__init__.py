"""Local Streamlit dashboard for attribution evidence and budget strategy.

This package is the presentation layer. It reads the artifacts the pipeline
already produces and never computes attribution or budget values itself, so
the dashboard cannot become a second, divergent implementation.

Data flow:
    modules/*/data and outputs  ->  dashboard/data_source.py  ->  views
    (or the PostgreSQL mirror when DATABASE=true)

Run it from the repository root:
    uv run --extra dashboard streamlit run dashboard/app.py
"""
