"""Schema discovery, validation, and the connection option they produce.

The schema selection reaches PostgreSQL as an identifier inside a libpq
connect option rather than as a bound value, so what may be placed there is a
contract worth proving rather than a detail. These tests cover the three
decisions that contract rests on: which names are accepted at all, that the
selected schema is the whole search path with no fallback behind it, and that a
schema is offered to the reader only when it can actually serve every view.

The census is exercised against recorded rows rather than a live server, so the
suite proves the classification without requiring a database.

Data flow:
    backend/services/schemas.py, dashboard/config.py -> here
"""

from __future__ import annotations

import unittest

from backend.services.schemas import (
    REQUIRED_TABLES,
    RESEARCH_TABLES,
    SIMULATOR_SOURCE_TABLES,
    _census,
    _describe,
)
from dashboard.config import DEFAULT_SCHEMA, DatabaseSettings, valid_schema_name


def _row(name: str, tables: tuple[str, ...], total: int) -> dict:
    """One census row, shaped as `_CENSUS_STATEMENT` returns it."""
    return {"schema_name": name, "tables": list(tables), "table_total": total}


def _settings(schema: str) -> DatabaseSettings:
    return DatabaseSettings(
        host="db.example.com",
        port=5432,
        database="mta_data",
        user="reader",
        password="secret",
        sslmode="prefer",
        schema=schema,
    )


class SchemaNameTests(unittest.TestCase):
    """Check which names may become part of a connect option."""

    def test_ordinary_identifiers_are_accepted(self) -> None:
        for name in ("public", "mta", "_private", "scenario_2026", "a$b"):
            self.assertTrue(valid_schema_name(name), name)

    def test_a_name_that_could_close_the_option_is_refused(self) -> None:
        # Each of these would end `-csearch_path=<name>` and begin something
        # else, which is the reason the name is validated rather than escaped.
        for name in (
            "public -c log_statement=all",
            "public;drop",
            'pub"lic',
            "public'",
            "public\nmta",
            "",
            "2026_scenario",
        ):
            self.assertFalse(valid_schema_name(name), name)

    def test_a_name_longer_than_an_identifier_is_refused(self) -> None:
        self.assertFalse(valid_schema_name("s" * 64))
        self.assertTrue(valid_schema_name("s" * 63))


class ConnectArgumentTests(unittest.TestCase):
    """Check the connection carries the selection, and nothing behind it."""

    def test_the_default_schema_sets_no_option(self) -> None:
        # `public` is what the server searches anyway, so the option is omitted
        # rather than set redundantly on every connection.
        self.assertNotIn("options", _settings(DEFAULT_SCHEMA).connect_args())

    def test_a_selected_schema_is_the_whole_search_path(self) -> None:
        arguments = _settings("mta").connect_args()

        # No `,public` behind it: a schema holding only the simulator's research
        # tables must fail to find `attribution_result` rather than resolve it
        # from another scenario's data.
        self.assertEqual(arguments["options"], "-csearch_path=mta")

    def test_an_invalid_schema_fails_before_a_connection_is_opened(self) -> None:
        with self.assertRaises(ValueError):
            _settings("mta -c log_statement=all").connect_args()

    def test_the_summary_names_a_non_default_schema_and_never_the_password(
        self,
    ) -> None:
        self.assertIn("(mta)", _settings("mta").safe_summary())
        self.assertNotIn("secret", _settings("mta").safe_summary())
        self.assertNotIn("(", _settings(DEFAULT_SCHEMA).safe_summary())


class SchemaDescriptionTests(unittest.TestCase):
    """Check what a reader is told about each schema they could choose."""

    def test_a_complete_schema_is_selectable(self) -> None:
        described = _describe("public", set(REQUIRED_TABLES), 53, "public")

        self.assertTrue(described["selectable"])
        self.assertTrue(described["selected"])
        self.assertEqual(described["missingCount"], 0)
        self.assertEqual(described["databaseRevision"], "not tracked")

    def test_artifact_schema_version_is_not_reported_as_database_revision(self) -> None:
        described = _describe("public", set(REQUIRED_TABLES), 53, "public")

        # No migration ledger exists yet. A strategy artifact happens to carry
        # its own schema_version, but using it here would claim columns and
        # constraints were migrated when nothing has checked them.
        self.assertNotIn("schema_version", described)
        self.assertEqual(described["databaseRevision"], "not tracked")

    def test_the_count_is_the_whole_schema_not_the_matched_subset(self) -> None:
        # The census matches only the tables selectability turns on, so the
        # matched set is far smaller than the schema. Reporting the subset here
        # would tell a reader their 53-table schema holds fourteen, and they
        # would reasonably conclude the connection was pointing somewhere else.
        described = _describe("public", set(REQUIRED_TABLES), 53, "public")

        self.assertEqual(described["tableCount"], 53)
        self.assertIn("53 table(s)", described["detail"])

    def test_a_research_only_schema_is_disabled_and_names_the_remedy(self) -> None:
        described = _describe("mta", set(RESEARCH_TABLES), 14, "public")

        self.assertFalse(described["selectable"])
        self.assertTrue(described["hasResearchTables"])
        self.assertEqual(described["missingCount"], len(REQUIRED_TABLES))
        # The reason and the fix travel with the option, so the dialog does not
        # have to reconstruct either.
        self.assertIn("derive_scenario_schemas.py --source mta", described["detail"])

    def test_a_complete_source_is_parseable_but_not_selectable(self) -> None:
        described = _describe("mta", set(SIMULATOR_SOURCE_TABLES), 19, "public")

        self.assertFalse(described["selectable"])
        self.assertTrue(described["canDerive"])
        self.assertFalse(described["canInitialize"])
        self.assertEqual(described["kind"], "source")

    def test_a_partial_source_is_not_offered_a_parser(self) -> None:
        described = _describe(
            "mta", set(SIMULATOR_SOURCE_TABLES) - {"amc_path_report"}, 18, "public"
        )

        self.assertFalse(described["canDerive"])
        self.assertGreater(described["sourceMissingCount"], 0)

    def test_a_populated_schema_is_never_told_to_run_the_fixture_import(self) -> None:
        # The fixture importer writes its own advertiser, campaign group, and
        # campaigns. Pointed at a schema that already holds a different
        # account's history, it would staple the demo entities onto that
        # account's observations, so it is only ever offered for an empty one.
        described = _describe("mta", set(RESEARCH_TABLES), 14, "public")

        self.assertNotIn("import_to_database", described["detail"])

    def test_an_empty_schema_is_offered_the_fixture_import(self) -> None:
        described = _describe("blank", set(), 0, "public")

        self.assertIn(
            "script/import_to_database.py --schema blank", described["detail"]
        )
        self.assertTrue(described["canInitialize"])

    def test_no_description_names_the_research_pipeline(self) -> None:
        # These strings are rendered in the settings dialog, which the client
        # suite holds to describing a live advertising account rather than how
        # its history was produced.
        for present, total in (
            (set(RESEARCH_TABLES), 14),
            (set(REQUIRED_TABLES), 29),
            (set(), 0),
        ):
            detail = _describe("s", present, total, "public")["detail"].lower()
            for forbidden in ("simulator", "simulated", "synthetic", "mta_sim"):
                self.assertNotIn(forbidden, detail)

    def test_a_schema_missing_one_table_is_not_selectable(self) -> None:
        present = set(REQUIRED_TABLES) - {"attribution_result"}

        described = _describe("partial", present, 13, "public")

        self.assertFalse(described["selectable"])
        self.assertEqual(described["missingTables"], ["attribution_result"])

    def test_the_missing_list_is_bounded_but_the_count_is_not(self) -> None:
        described = _describe("empty", set(), 0, "public")

        # A tooltip cannot usefully carry fourteen names, so the list is capped
        # while the count still states the true size.
        self.assertEqual(len(described["missingTables"]), 8)
        self.assertEqual(described["missingCount"], len(REQUIRED_TABLES))

    def test_an_unrelated_schema_does_not_claim_an_import_would_help(self) -> None:
        described = _describe("billing", {"clients", "invoices"}, 2, "public")

        self.assertFalse(described["hasResearchTables"])
        self.assertNotIn("import_to_database", described["detail"])
        self.assertNotIn("derive_scenario_schemas", described["detail"])


class CensusTests(unittest.TestCase):
    """Check the ordering and filtering of the list the dropdown renders."""

    def test_selectable_schemas_sort_first_then_by_name(self) -> None:
        rows = [
            _row("mta", RESEARCH_TABLES, 14),
            _row("public", REQUIRED_TABLES, 53),
            _row("archive", (), 0),
            _row("backup", REQUIRED_TABLES, 29),
        ]

        names = [item["name"] for item in _census(rows, "public")]

        self.assertEqual(names, ["backup", "public", "archive", "mta"])

    def test_a_schema_whose_name_is_not_an_identifier_is_dropped(self) -> None:
        # A quoted schema name may hold characters the connect option cannot
        # carry, so it is not offered rather than offered and then refused.
        rows = [
            _row("my schema", REQUIRED_TABLES, 29),
            _row("public", REQUIRED_TABLES, 53),
        ]

        self.assertEqual([item["name"] for item in _census(rows, "public")], ["public"])

    def test_the_selected_schema_is_marked_even_when_it_cannot_be_chosen(self) -> None:
        described = _census([_row("mta", RESEARCH_TABLES, 14)], "mta")[0]

        self.assertTrue(described["selected"])
        self.assertFalse(described["selectable"])


if __name__ == "__main__":
    unittest.main()
