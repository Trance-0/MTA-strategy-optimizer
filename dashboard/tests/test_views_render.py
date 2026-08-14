"""Tests that every dashboard view renders without raising.

A view is a page of chart and table calls with no return value, so an error
inside one surfaces only when a reader opens it. Streamlit's `AppTest` runs the
real app headlessly and collects any exception, which turns that into a test.

These tests run against `DATABASE=false` only. File mode needs nothing beyond
the repository, so the suite stays runnable in a clean checkout and in CI.
Database mode is covered by `script/verify_source_parity.py`, which needs a
populated instance and is therefore a command rather than a test.
"""

from __future__ import annotations

import logging
import os
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

try:
    from streamlit.testing.v1 import AppTest
except ImportError:  # pragma: no cover - reported by setUpModule instead
    AppTest = None

APP_FILE = REPO_ROOT / "dashboard" / "app.py"

#: Rendering the whole app once per view is slow enough to be worth doing once.
_app: "AppTest | None" = None


def setUpModule() -> None:
    """Fix the data source, then start the app once for every test."""
    global _app
    if AppTest is None:
        raise unittest.SkipTest(
            "Streamlit is not installed. Run `uv sync --extra dashboard`."
        )
    # The mode is read through an lru_cache at first use, so it must be set
    # before the dashboard package is imported anywhere in this process.
    os.environ["DATABASE"] = "false"
    _app = AppTest.from_file(str(APP_FILE), default_timeout=120)
    _app.run()


class ViewRenderTests(unittest.TestCase):
    """Every view in the sidebar renders without raising."""

    def test_app_starts(self) -> None:
        self.assertFalse(
            _app.exception, f"App failed to start: {[e.value for e in _app.exception]}"
        )

    def test_sidebar_offers_the_six_views(self) -> None:
        """The rail is icon buttons, not a radio group, so check the keys."""
        from dashboard.app import FOOT_ITEMS, VIEWS, rail_key

        keys = {button.key for button in _app.sidebar.button}
        for name in list(VIEWS) + list(FOOT_ITEMS):
            with self.subTest(item=name):
                self.assertIn(rail_key(name), keys)

    def test_rail_keys_survive_streamlit_class_mangling(self) -> None:
        """The generated CSS names `st-key-<key>`, which must match the widget.

        Streamlit rewrites spaces in a key to hyphens in the class name, so a
        key containing a space would silently lose its icon.
        """
        from dashboard.app import FOOT_ITEMS, VIEWS, rail_key

        for name in list(VIEWS) + list(FOOT_ITEMS):
            with self.subTest(item=name):
                self.assertNotIn(" ", rail_key(name))

    def test_every_rail_item_has_an_icon(self) -> None:
        from dashboard.app import FOOT_ITEMS, ICONS, VIEWS

        for name in list(VIEWS) + list(FOOT_ITEMS):
            with self.subTest(item=name):
                self.assertIn(name, ICONS)

    def test_every_view_renders(self) -> None:
        from dashboard.app import VIEWS

        for name in VIEWS:
            with self.subTest(view=name):
                # Clicking the rail button sets session state and reruns, which
                # is the same path a reader takes.
                _app.session_state["view"] = name
                _app.run()
                self.assertFalse(
                    _app.exception,
                    f"{name} raised: {[str(e.value)[:400] for e in _app.exception]}",
                )
                self.assertTrue(
                    _app.markdown, f"{name} rendered no content."
                )


class DataSourceContractTests(unittest.TestCase):
    """The loaders expose the columns the views read by name."""

    def test_loaders_return_expected_columns(self) -> None:
        from dashboard import data_source

        expected = {
            "load_ads_daily": {"report_date", "touchpoint", "cost", "sales"},
            "load_attribution_results": {
                "attribution_model",
                "touchpoint",
                "attributed_revenue",
                "ad_product",
            },
            "load_comparison_touchpoints": {
                "touchpoint",
                "outcome",
                "markov_share",
                "shapley_share",
            },
            "load_recommended_attribution": {
                "touchpoint",
                "outcome",
                "official_share",
                "recommended_value",
            },
            "load_entity_bridge": {"campaign_id", "ad_group_id", "assisted_revenue"},
            "load_path_report": {"path", "path_length", "converted_users"},
        }
        for name, columns in expected.items():
            with self.subTest(loader=name):
                frame = getattr(data_source, name)()
                self.assertTrue(
                    columns.issubset(frame.columns),
                    f"{name} is missing {sorted(columns - set(frame.columns))}",
                )

    def test_reliability_flags_are_booleans(self) -> None:
        """The pipeline writes `true`/`false` strings, and `"false"` is truthy."""
        from dashboard import data_source

        frame = data_source.load_comparison_touchpoints()
        for column in (
            "calculation_valid",
            "data_support_sufficient",
            "models_consistent",
        ):
            with self.subTest(column=column):
                self.assertEqual(frame[column].dtype, bool)


class SettingsTests(unittest.TestCase):
    """The settings module edits `.env` without losing unrelated content."""

    def test_write_env_preserves_comments_and_other_keys(self) -> None:
        import tempfile

        from dashboard import settings

        original = settings.ENV_PATH
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / ".env"
            path.write_text(
                "# a comment\nDATABASE=false\nUNRELATED=keep-me\nPG_HOST=old\n",
                encoding="utf-8",
            )
            settings.ENV_PATH = path
            try:
                settings.write_env({"DATABASE": "true", "PG_HOST": "new-host"})
                written = path.read_text(encoding="utf-8")
            finally:
                settings.ENV_PATH = original
                # write_env exports into the process; undo so later tests and
                # the module-level app still read file mode.
                os.environ["DATABASE"] = "false"
                from dashboard import config

                config.use_database.cache_clear()
                config.database_settings.cache_clear()

        self.assertIn("# a comment", written)
        self.assertIn("UNRELATED=keep-me", written)
        self.assertIn("DATABASE=true", written)
        self.assertIn("PG_HOST=new-host", written)
        self.assertNotIn("PG_HOST=old", written)

    def test_write_env_appends_missing_keys(self) -> None:
        import tempfile

        from dashboard import settings

        original = settings.ENV_PATH
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / ".env"
            path.write_text("DATABASE=false\n", encoding="utf-8")
            settings.ENV_PATH = path
            try:
                settings.write_env({"DATABASE": "false", "PG_SSLMODE": "require"})
                written = path.read_text(encoding="utf-8")
            finally:
                settings.ENV_PATH = original
                os.environ["DATABASE"] = "false"
                from dashboard import config

                config.use_database.cache_clear()
                config.database_settings.cache_clear()

        self.assertIn("PG_SSLMODE=require", written)
        self.assertEqual(written.count("DATABASE="), 1)

    def test_hosted_mode_forces_file_reads(self) -> None:
        """The published build cannot open a socket, so it must never try.

        `DASHBOARD_HOSTED` is set by `web/index.html`. A `.env` carried into the
        virtual filesystem, or a stale `DATABASE=true` in the environment, must
        not be able to flip the browser build into a mode it cannot serve.
        """
        from dashboard import config

        os.environ["DASHBOARD_HOSTED"] = "true"
        os.environ["DATABASE"] = "true"
        config.is_hosted.cache_clear()
        config.use_database.cache_clear()
        try:
            self.assertTrue(config.is_hosted())
            self.assertFalse(config.use_database())
        finally:
            os.environ.pop("DASHBOARD_HOSTED", None)
            os.environ["DATABASE"] = "false"
            config.is_hosted.cache_clear()
            config.use_database.cache_clear()

    def test_log_handler_is_bounded(self) -> None:
        """A long session must not grow the capture without limit."""
        from dashboard.settings import LOG_CAPACITY, RingBufferHandler

        handler = RingBufferHandler(capacity=5)
        for index in range(20):
            handler.emit(
                logging.LogRecord(
                    "dashboard", logging.INFO, __file__, index, "row %d", (index,), None
                )
            )
        self.assertEqual(len(handler.records), 5)
        self.assertEqual(handler.records[-1].message, "row 19")
        self.assertGreater(LOG_CAPACITY, 0)


if __name__ == "__main__":
    unittest.main()
