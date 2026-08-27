"""Which schemas the connected database offers, and what each one can serve.

One PostgreSQL instance commonly holds several schemas -- one per simulation
scenario -- and they are not interchangeable. A schema written by the external
simulator carries the `mta_sim_*` tables but none of this project's own; a
schema populated by `script/import_to_database.py` or
`script/derive_scenario_schemas.py` carries the model in `dashboard/models.py`.
Selecting the first as though it were the second gives a dashboard whose every
view is empty, with nothing on the page saying why.

So this module reports a capability rather than a name. Each schema is
enumerated with the tables it actually holds, which decides whether it can be
selected at all and, when it cannot, what is missing and which command would
populate it. The dialog renders that as a disabled option carrying its own
reason, so a reader learns why a scenario is unavailable at the moment they
would have chosen it.

Enumeration is restricted to schemas the connected role may actually read:
`has_schema_privilege` is asked for each, so the list never advertises a
schema whose selection would fail with a permission error.

Data flow:
    the settings dialog -> GET /api/settings -> here -> information_schema
"""

from __future__ import annotations

from typing import Any

from backend.config import DEFAULT_SCHEMA, database_settings, valid_schema_name

#: The tables a schema must hold before the whole dashboard can read it. Not
#: the full eighteen: these are the ones the loaders in `backend/repository/`
#: read directly, so a schema holding them serves every view. `attribution_run`
#: is included because `comparison_summary()` joins it for the report window.
REQUIRED_TABLES: tuple[str, ...] = (
    "advertiser",
    "campaign_group",
    "campaign",
    "touchpoint",
    "ads_daily_performance",
    "path_report",
    "touchpoint_entity_bridge",
    "attribution_run",
    "attribution_result",
    "model_comparison_touchpoint",
    "model_comparison_summary",
    "recommended_attribution",
    "budget_recommendation_run",
    "campaign_budget_recommendation",
)

#: The simulator's own tables. A schema holding these carries research history
#: even when it carries none of the model above, which is worth reporting: it
#: tells a reader the schema is a real scenario awaiting an import rather than
#: an unrelated schema that happens to be visible.
RESEARCH_TABLES: tuple[str, ...] = (
    "mta_simulation_run",
    "mta_sim_campaign",
    "mta_sim_delivery_observation",
    "mta_sim_budget_observation",
)

#: The complete source contract consumed by
#: `script/derive_scenario_schemas.py`. Keeping the census aware of all of it
#: prevents a schema with only a few similarly named research tables from
#: being offered a parse action that can only fail after a process starts.
SIMULATOR_SOURCE_TABLES: tuple[str, ...] = (
    "mta_simulation_run",
    "mta_sim_campaign",
    "mta_sim_ad_group",
    "mta_sim_touchpoint",
    "mta_sim_product",
    "mta_sim_campaign_product_link",
    "mta_sim_delivery_observation",
    "mta_sim_outcome_observation",
    "amc_path_report",
    "amazon_ads_daily_touchpoint_performance",
)

#: How a reader populates a schema that carries research history but not the
#: dashboard's model. Deriving reads the scenario's own advertisers and
#: marketplaces; the fixture importer would write the demo account's entities
#: over them, so the remedy offered here is deliberately the derivation.
#: Each scenario becomes its own schema, which is why no target is named.
DERIVE_COMMAND = (
    "uv run --extra dashboard python script/derive_scenario_schemas.py "
    "--source {schema} --all --replace"
)

#: How a reader populates an empty schema: the committed fixture, which brings
#: its own account with it and so must never be pointed at a schema that
#: already holds someone else's data.
IMPORT_COMMAND = (
    "uv run --extra dashboard python script/import_to_database.py "
    "--schema {schema} --replace"
)


def _describe(
    schema: str, present: set[str], total: int, selected: str
) -> dict[str, Any]:
    """Turn one schema's table census into the option the dialog renders."""
    missing = [table for table in REQUIRED_TABLES if table not in present]
    research = [table for table in RESEARCH_TABLES if table in present]
    complete = not missing
    source_missing = [
        table for table in SIMULATOR_SOURCE_TABLES if table not in present
    ]
    parse_source = not source_missing

    if complete:
        detail = f"{total} table(s). Serves every view."
        kind = "dashboard"
    elif parse_source:
        detail = (
            f"{total} table(s). Complete source model; parse its scenarios "
            "into dashboard schemas."
        )
        kind = "source"
    elif research:
        # Worded without naming the research pipeline: this string is rendered
        # in the settings dialog, and the dashboard does not describe the
        # account it reports on in terms of how its history was produced.
        detail = (
            f"Carries {len(research)} research history table(s) but none of the "
            f"attribution or strategy model. Derive a schema per scenario "
            f"with: {DERIVE_COMMAND.format(schema=schema)}"
        )
        kind = "partial_source"
    elif total:
        detail = (
            f"{total} table(s), none of them the dashboard's. This schema "
            "belongs to another application."
        )
        kind = "other"
    else:
        detail = (
            "Empty. Load the committed sample with: "
            f"{IMPORT_COMMAND.format(schema=schema)}"
        )
        kind = "empty"

    return {
        "name": schema,
        "selectable": complete,
        "selected": schema == selected,
        "tableCount": total,
        # Bounded: a schema missing everything would otherwise send the whole
        # required list, which the dialog cannot usefully render in a tooltip.
        "missingTables": missing[:8],
        "missingCount": len(missing),
        "hasResearchTables": bool(research),
        "kind": kind,
        "canInitialize": total == 0 or complete,
        "canDerive": parse_source and not complete,
        "sourceMissingCount": len(source_missing),
        "detail": detail,
    }


def available_schemas() -> dict[str, Any]:
    """Every readable schema on the connected database, with its capability.

    Returns `{schemas, selected, error}` rather than raising, so a database
    that is unreachable renders as a dialog that says so and keeps its stored
    selection, instead of a settings page that fails to load at all.
    """
    selected = DEFAULT_SCHEMA
    try:
        selected = database_settings().schema
    except RuntimeError:
        # Not configured yet. The dialog still opens, and offers no schema
        # until a connection is entered and tested.
        return {"schemas": [], "selected": selected, "error": None}

    try:
        return {
            "schemas": _read_schemas(selected),
            "selected": selected,
            "error": None,
        }
    except Exception as error:  # noqa: BLE001 - reported to the dialog, not raised
        return {
            "schemas": [],
            "selected": selected,
            "error": f"{type(error).__name__}: {str(error)[:180]}",
        }


def _read_schemas(selected: str) -> list[dict[str, Any]]:
    """Enumerate readable schemas through the service's own engine."""
    from backend.database import sql

    return _census(
        sql(
            _CENSUS_STATEMENT,
            {
                "required": list(
                    dict.fromkeys(
                        REQUIRED_TABLES + RESEARCH_TABLES + SIMULATOR_SOURCE_TABLES
                    )
                )
            },
        ),
        selected,
    )


#: One round trip: every readable non-system schema, with both the subset of
#: the tables we care about that it holds and how many relations it holds in
#: total. Two numbers rather than one, because they answer different questions:
#: the subset decides selectability, while the total is what a reader compares
#: against the database they think they are looking at. Reporting the subset as
#: though it were the total would describe a 53-table schema as holding 18.
#: Schemas are filtered by the same privilege check the reader would need, so
#: the list cannot advertise a schema whose selection would fail.
_CENSUS_STATEMENT = """
    select n.nspname as schema_name,
           coalesce(array_agg(c.relname order by c.relname)
                    filter (where c.relname = any(:required)), '{}') as tables,
           count(c.relname) as table_total
      from pg_namespace n
      left join pg_class c
        on c.relnamespace = n.oid
       and c.relkind in ('r', 'v', 'm', 'p', 'f')
     where n.nspname not like 'pg\\_%'
       and n.nspname <> 'information_schema'
       and has_schema_privilege(current_user, n.nspname, 'USAGE')
     group by n.nspname
     order by n.nspname
"""


def _census(rows: list[dict], selected: str) -> list[dict[str, Any]]:
    """Describe each enumerated schema, complete ones first."""
    described = [
        _describe(
            row["schema_name"],
            set(row["tables"] or []),
            int(row["table_total"] or 0),
            selected,
        )
        for row in rows
        if valid_schema_name(row["schema_name"])
    ]
    # A selectable schema sorts first: the list is a menu, and the entries a
    # reader can act on belong at the top of it. Names sort within each group,
    # so the order does not move as tables are added.
    described.sort(key=lambda item: (not item["selectable"], item["name"]))
    return described


def probe_schemas(updates: dict[str, str]) -> dict[str, Any]:
    """Enumerate schemas on a connection that has been typed but not saved.

    Separate from `available_schemas()` because the dialog fills its dropdown
    from a successful connection test, before anything is written to `.env`.
    Tests what was typed rather than what is stored, and closes the probe
    connection whether or not it succeeded.
    """
    from sqlalchemy import create_engine, text

    from dashboard.config import DatabaseSettings

    settings = DatabaseSettings(
        host=updates.get("PG_HOST", ""),
        port=int(updates.get("PG_PORT") or "5432"),
        database=updates.get("PG_DATABASE", ""),
        user=updates.get("PG_USER", ""),
        password=updates.get("PG_PASSWORD", ""),
        sslmode=updates.get("PG_SSLMODE") or "prefer",
    )
    selected = (updates.get("PG_SCHEMA") or "").strip() or DEFAULT_SCHEMA

    probe = None
    try:
        # The probe deliberately does not pin a search path: it is asking which
        # schemas exist, which must not depend on the answer.
        probe = create_engine(settings.url(), connect_args={"connect_timeout": 10})
        with probe.connect() as connection:
            rows = connection.execute(
                text(_CENSUS_STATEMENT),
                {
                    "required": list(
                        dict.fromkeys(
                            REQUIRED_TABLES + RESEARCH_TABLES + SIMULATOR_SOURCE_TABLES
                        )
                    )
                },
            ).mappings()
            return {
                "schemas": _census([dict(row) for row in rows], selected),
                "selected": selected,
                "error": None,
            }
    except Exception as error:  # noqa: BLE001 - reported to the dialog, not raised
        return {
            "schemas": [],
            "selected": selected,
            "error": f"{type(error).__name__}: {str(error)[:180]}",
        }
    finally:
        if probe is not None:
            probe.dispose()
