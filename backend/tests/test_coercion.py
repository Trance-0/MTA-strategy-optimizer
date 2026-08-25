"""Reader tests for the committed CSV artifacts.

These cover what `read_csv` must do to a file before any column is coerced:
drop the Chinese field-description row, survive a byte-order mark, and keep
quoting, embedded newlines, and CRLF intact. They were ported from the Node
suite that tested `dashboard/server/csv.js` before the Flask backend replaced
it, so removing that module did not remove the contract it proved.

Data flow:
    modules/&#42;/data and outputs -> backend/repository/coercion.py -> here
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from backend.repository.coercion import read_csv


class ReadCsvTests(unittest.TestCase):
    """Check the row-level contract every artifact reader depends on."""

    def _write(self, text: str, name: str = "sample.csv") -> Path:
        directory = Path(tempfile.mkdtemp(prefix="csv-"))
        path = directory / name
        # `newline=""` keeps a CRLF terminator in the bytes rather than letting
        # Python translate it, which is the case the reader must handle.
        path.write_text(text, encoding="utf-8", newline="")
        return path

    def test_quoted_field_keeps_commas_and_newlines(self) -> None:
        path = self._write('a,b\n"x,1","line\nbreak"\n')

        rows = read_csv(path)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["a"], "x,1")
        self.assertEqual(rows[0]["b"], "line\nbreak")

    def test_doubled_quote_reads_as_one_literal_quote(self) -> None:
        path = self._write('a\n"say ""hi"""\n')

        self.assertEqual(read_csv(path)[0]["a"], 'say "hi"')

    def test_crlf_is_one_row_terminator(self) -> None:
        path = self._write("a,b\r\n1,2\r\n")

        rows = read_csv(path)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0], {"a": "1", "b": "2"})

    def test_byte_order_mark_is_stripped_from_the_first_header(self) -> None:
        # Without this, every lookup of the first column misses: the header is
        # named "﻿date" rather than "date".
        path = self._write("﻿date,cost\n2026-01-01,5\n")

        rows = read_csv(path)

        self.assertIn("date", rows[0])
        self.assertEqual(rows[0]["date"], "2026-01-01")

    def test_description_row_is_dropped_but_real_rows_are_kept(self) -> None:
        path = self._write("报告日期,cost\n报告日期,花费\n2026-01-01,5\n")

        rows = read_csv(path)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["报告日期"], "2026-01-01")

    def test_a_file_without_a_description_row_keeps_its_first_row(self) -> None:
        # The marker is matched exactly rather than guessed. An earlier
        # heuristic that dropped any first row without digits also discarded a
        # real data row from the files that carry no description row.
        path = self._write("touchpoint,cost\nSPONSORED_PRODUCTS:X,5\n")

        self.assertEqual(len(read_csv(path)), 1)

    def test_trailing_newline_does_not_produce_an_empty_row(self) -> None:
        path = self._write("a,b\n1,2\n\n")

        self.assertEqual(len(read_csv(path)), 1)

    def test_an_absent_file_is_no_rows_rather_than_an_error(self) -> None:
        # An artifact that has not been produced is a state the views render,
        # not a failure that should reach the client as a 500.
        self.assertEqual(read_csv(Path(tempfile.mkdtemp()) / "absent.csv"), [])


if __name__ == "__main__":
    unittest.main()
