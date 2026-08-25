"""Environment-file writing and the in-memory diagnostic log.

`write_env` rewrites the operator's real `.env`, so its contract is narrow: a
key already present is replaced in place, a missing one is appended exactly
once, comments and unrelated keys survive, and repeated saves do not grow the
file. Every test here writes to a temporary path; none touches the repository's
own `.env`.

Ported from the Node suite that tested `dashboard/server/settings.js` before
the Flask backend replaced it, so removing that module did not remove the
contract it proved.

Data flow:
    backend/services/settings.py -> here
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from backend.services.settings import (
    ENV_KEYS,
    LOG_CAPACITY,
    apply_logging,
    clear_log,
    log,
    log_state,
    write_env,
)


def _env_file(contents: str = "") -> Path:
    path = Path(tempfile.mkdtemp(prefix="env-")) / ".env"
    path.write_text(contents, encoding="utf-8", newline="\n")
    return path


class WriteEnvTests(unittest.TestCase):
    """Check that rewriting `.env` preserves everything it does not own."""

    def test_a_key_is_replaced_in_place_and_comments_survive(self) -> None:
        path = _env_file("# a comment\nDATABASE=false\nUNRELATED=keep\n")

        write_env({"DATABASE": "true"}, path)

        text = path.read_text(encoding="utf-8")
        self.assertIn("# a comment", text)
        self.assertIn("UNRELATED=keep", text)
        self.assertIn("DATABASE=true", text)
        # Replaced, not appended: two values for one key would leave the winner
        # decided by read order.
        self.assertEqual(text.count("DATABASE="), 1)

    def test_a_missing_key_is_appended_exactly_once(self) -> None:
        path = _env_file("DATABASE=false\n")

        write_env({"PG_HOST": "db.example.com"}, path)
        write_env({"PG_HOST": "db2.example.com"}, path)

        text = path.read_text(encoding="utf-8")
        self.assertEqual(text.count("PG_HOST="), 1)
        self.assertIn("PG_HOST=db2.example.com", text)

    def test_repeated_saves_do_not_grow_a_blank_line(self) -> None:
        path = _env_file("DATABASE=false\n")

        for _ in range(5):
            write_env({"DATABASE": "false"}, path)

        self.assertEqual(path.read_text(encoding="utf-8"), "DATABASE=false\n")

    def test_every_key_the_settings_dialog_sends_is_written(self) -> None:
        path = _env_file("")

        write_env({key: "v" for key in ENV_KEYS}, path)

        text = path.read_text(encoding="utf-8")
        for key in ENV_KEYS:
            self.assertIn(f"{key}=v", text)

    def test_a_password_containing_an_equals_sign_survives(self) -> None:
        # `partition("=")` splits on the first separator only, so a password
        # that contains one must not be truncated on the next read.
        path = _env_file("PG_PASSWORD=old\n")

        write_env({"PG_PASSWORD": "a=b=c"}, path)

        self.assertIn("PG_PASSWORD=a=b=c", path.read_text(encoding="utf-8"))


class DiagnosticLogTests(unittest.TestCase):
    """Check that capture is opt-in, level-filtered, and bounded."""

    def tearDown(self) -> None:
        apply_logging(False)
        clear_log()

    def test_logging_is_off_by_default_and_records_nothing(self) -> None:
        clear_log()

        log("INFO", "test", "before")

        self.assertEqual(log_state()["records"], [])

    def test_a_record_below_the_active_level_is_dropped(self) -> None:
        clear_log()
        apply_logging(True, "INFO")
        log("INFO", "test", "after")
        self.assertEqual(len(log_state()["records"]), 1)

        # Dropped rather than stored and filtered on display, so raising the
        # level actually reduces the work done.
        apply_logging(True, "ERROR")
        log("INFO", "test", "too quiet")

        self.assertEqual(len(log_state()["records"]), 1)

    def test_one_record_cannot_dominate_the_buffer(self) -> None:
        clear_log()
        apply_logging(True, "INFO")

        log("INFO", "test", "x" * 5000)

        self.assertEqual(len(log_state()["records"][-1]["message"]), 400)

    def test_the_buffer_stays_bounded(self) -> None:
        clear_log()
        apply_logging(True, "INFO")

        for index in range(LOG_CAPACITY + 50):
            log("INFO", "test", index)

        # The deque is capped at LOG_CAPACITY; the state view returns the most
        # recent slice of it, which is what the dialog renders.
        records = log_state()["records"]
        self.assertLessEqual(len(records), LOG_CAPACITY)
        self.assertEqual(records[-1]["message"], str(LOG_CAPACITY + 49))


if __name__ == "__main__":
    unittest.main()
