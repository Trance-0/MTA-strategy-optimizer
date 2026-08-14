"""Dashboard entry point: page shell, navigation, and the settings module.

Run from the repository root:

    uv run --extra dashboard streamlit run dashboard/app.py

The six views mirror the reference design in `external/UI_design`. Each lives
in `dashboard/views/` and receives no arguments: every view pulls what it needs
from `dashboard.data_source`, which hides whether the numbers came from the
PostgreSQL mirror or from the committed files.

The sidebar reproduces the reference design's navigation rail: grouped section
labels over stacked icon buttons, with a settings module pinned to the foot.
Streamlit has no icon-button widget, so each item is a real `st.button` whose
icon is painted as a background image on the button itself -- see `_icon_css`
for why the icon cannot be a separate element -- and the selection is held in
session state rather than by a radio group.
"""

from __future__ import annotations

import sys
from pathlib import Path
from urllib.parse import quote

import streamlit as st

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dashboard import config, data_source, settings, theme  # noqa: E402
from dashboard.views import (  # noqa: E402
    budget_manager,
    campaign_optimizer,
    campaigns,
    command_center,
    knowledge_base,
    optimization_log,
)

#: Inline SVG for each rail item, taken from the reference design so the rail
#: reads the same. `currentColor` is a placeholder: `_icon_css` substitutes the
#: resting and active colours, because a colour keyword does not inherit into a
#: background image.
ICONS = {
    "Command Center": (
        '<path d="M4 4h6v6H4V4zm10 0h6v10h-6V4zM4 14h6v6H4v-6zm10 4h6v2h-6v-2z" '
        'stroke="currentColor" stroke-width="1.6"/>'
    ),
    "Budget Manager": (
        '<path d="M4 6h16v12H4V6zm0 4h16M8 15h4" stroke="currentColor" '
        'stroke-width="1.6"/>'
    ),
    "Campaigns": (
        '<path d="M4 12l15-7v14L4 13v-1zm4 3v4l4 1" stroke="currentColor" '
        'stroke-width="1.6"/>'
    ),
    "Campaign Optimizer": (
        '<path d="M5 17l4-5 3 2 6-8M15 6h3v3" stroke="currentColor" '
        'stroke-width="1.7"/>'
    ),
    "Optimization Log": (
        '<path d="M5 5h14v14H5V5zm3 4h8m-8 3h8m-8 3h5" stroke="currentColor" '
        'stroke-width="1.6"/>'
    ),
    "Knowledge Base": (
        '<path d="M4 5h7v14H4V5zm9 0h7v14h-7V5zM7 9h1m8 0h1" '
        'stroke="currentColor" stroke-width="1.6"/>'
    ),
    "Reload data": (
        '<path d="M20 12a8 8 0 11-2.34-5.66M20 4v4h-4" stroke="currentColor" '
        'stroke-width="1.7" stroke-linecap="round"/>'
    ),
    "Settings": (
        '<path d="M12 15.2a3.2 3.2 0 100-6.4 3.2 3.2 0 000 6.4z" '
        'stroke="currentColor" stroke-width="1.6"/>'
        '<path d="M18.7 14.4a1.5 1.5 0 00.3 1.65l.05.06a1.8 1.8 0 11-2.55 2.55l'
        "-.05-.06a1.5 1.5 0 00-1.65-.3 1.5 1.5 0 00-.9 1.37v.16a1.8 1.8 0 "
        "11-3.6 0v-.09a1.5 1.5 0 00-.98-1.37 1.5 1.5 0 00-1.65.3l-.06.06a1.8 "
        "1.8 0 11-2.55-2.55l.06-.06a1.5 1.5 0 00.3-1.65 1.5 1.5 0 "
        "00-1.38-.9h-.15a1.8 1.8 0 010-3.6h.09a1.5 1.5 0 001.37-.98 1.5 1.5 0 "
        "00-.3-1.65l-.06-.06a1.8 1.8 0 112.55-2.55l.06.06a1.5 1.5 0 001.65.3h"
        ".07a1.5 1.5 0 00.9-1.38v-.15a1.8 1.8 0 013.6 0v.09a1.5 1.5 0 00.9 "
        "1.37 1.5 1.5 0 001.65-.3l.06-.06a1.8 1.8 0 112.55 2.55l-.06.06a1.5 "
        "1.5 0 00-.3 1.65v.07a1.5 1.5 0 001.38.9h.15a1.8 1.8 0 010 3.6h-.09a"
        '1.5 1.5 0 00-1.37.9z" stroke="currentColor" stroke-width="1.35"/>'
    ),
}

#: Section label -> the views beneath it, in the reference design's order.
NAV_GROUPS = {
    "OVERVIEW": {"Command Center": command_center.render},
    "PLANNING": {
        "Budget Manager": budget_manager.render,
        "Campaigns": campaigns.render,
        "Campaign Optimizer": campaign_optimizer.render,
    },
    "INSIGHTS": {
        "Optimization Log": optimization_log.render,
        "Knowledge Base": knowledge_base.render,
    },
}

#: Flattened view registry, for dispatch and for tests.
VIEWS = {name: render for group in NAV_GROUPS.values() for name, render in group.items()}

DEFAULT_VIEW = next(iter(VIEWS))

#: Items that sit in the foot of the rail rather than in a navigation group.
FOOT_ITEMS = ("Settings", "Reload data")

#: Where the app points a reader who wants the source or the specification.
REPO_URL = "https://github.com/Trance-0/MTA-strategy-optimizer"
DOCS_URL = "https://trance-0.github.io/MTA-strategy-optimizer/docs"


def rail_key(name: str) -> str:
    """Return the widget key for a rail item.

    Streamlit turns a widget key into a `st-key-<key>` class on that element's
    container. That class is the only stable hook the stylesheet has for
    addressing one specific button, so this spelling is shared between the
    widget and the generated CSS. Spaces are avoided because Streamlit rewrites
    them to hyphens in the class name.
    """
    return f"nav_{name.replace(' ', '_')}"


def _icon_data_uri(name: str, color: str) -> str:
    """Return one icon as a colour-baked `data:` URI."""
    svg = (
        "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' "
        f"fill='none'>{ICONS[name]}</svg>"
    ).replace('"', "'").replace("currentColor", color)
    return f"data:image/svg+xml,{quote(svg, safe='')}"


def _icon_css(active_view: str) -> str:
    """Return per-item rules that paint each rail button's icon.

    An inline `<svg>` cannot live inside a Streamlit button label, and a marker
    element drawn above the button cannot be reached from it: Streamlit wraps
    every element in its own container, so the two are never DOM siblings and
    no CSS combinator spans them. Painting the icon as a background image on
    the button keeps glyph and label in a single element, which is also what
    makes the whole tile one hit target.

    The active item is styled here rather than by a class, for the same reason:
    the app cannot add a class to a container Streamlit owns, but it can emit a
    rule naming that container's key.

    The selector goes through `.stButton` deliberately. Without it these rules
    tie on specificity with the shared button rule in `theme.py`, and the tie
    breaks by document order -- which the sidebar loses, because Streamlit puts
    the sidebar's markup ahead of the main pane's. The extra class wins outright
    instead of relying on where Streamlit chose to place a `<style>` tag.
    """
    rules = []
    for name in list(VIEWS) + list(FOOT_ITEMS):
        item = (
            f'section[data-testid="stSidebar"] '
            f".st-key-{rail_key(name)} .stButton > button"
        )
        rest = _icon_data_uri(name, theme.RAIL_ICON)
        lit = _icon_data_uri(name, theme.RAIL_ICON_ACTIVE)
        rules.append(f'{item} {{ background-image: url("{rest}"); }}')
        rules.append(f'{item}:hover, {item}:focus {{ background-image: url("{lit}"); }}')
        if name == active_view:
            rules.append(
                f'{item}, {item}:hover, {item}:focus {{ '
                f'background-image: url("{lit}"); '
                f"background-color: {theme.RAIL_ACTIVE}; color: #fff; }}"
            )
            rules.append(f"{item} p {{ color: #fff; font-weight: 600; }}")
    return "<style>\n" + "\n".join(rules) + "\n</style>"


def _brand() -> None:
    """The logo block at the head of the rail."""
    st.markdown(
        """
        <div class="rail-brand">
          <div class="rail-logo">M</div>
          <b>AI-MTA</b>
          <span>MARKETING ROI</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _nav() -> None:
    """Draw the grouped icon buttons and record the selection."""
    for label, views in NAV_GROUPS.items():
        st.markdown(f'<div class="rail-label">{label}</div>', unsafe_allow_html=True)
        for name in views:
            if st.button(name, key=rail_key(name), width="stretch"):
                st.session_state["view"] = name
                st.rerun()


def _settings_module() -> None:
    """The settings block pinned to the foot of the rail.

    Everything here is about the dashboard's own plumbing -- which source the
    numbers came from, whether streaming is being logged, and the controls that
    change both -- so it is kept apart from the view navigation above it.
    """
    label, colour, detail = settings.status()
    logging_on = settings.logging_enabled()

    # A keyed container is what `margin-top: auto` is applied to; that is the
    # supported way to name a block Streamlit renders.
    with st.container(key="rail_foot"):
        st.markdown(
            f"""
            <div class="rail-status">
              <span class="rail-dot" style="background:{colour}"></span>
              <span class="rail-status-label">{label}</span>
            </div>
            <div class="rail-status-detail" title="{detail}">{detail}</div>
            <div class="rail-log {"on" if logging_on else ""}">
              LOGGING {"ON" if logging_on else "OFF"}
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button("Settings", key=rail_key("Settings"), width="stretch"):
            settings.settings_dialog()
        if st.button("Reload data", key=rail_key("Reload data"), width="stretch"):
            data_source.clear_caches()
            st.rerun()
        _outbound_links()


def _outbound_links() -> None:
    """Links out of the app, at the very foot of the rail.

    A reader who arrives at the published dashboard has no other route to the
    specification or the source, so the app carries them. The documentation
    link is relative in the published build, where the site serves the
    dashboard at its root and the documentation one level down at `/docs/`;
    a local run has no such sibling and so points at the published site.
    """
    docs_href = "./docs/" if config.is_hosted() else f"{DOCS_URL}/"
    st.markdown(
        f"""
        <div class="rail-links">
          <a href="{docs_href}" target="_blank" rel="noopener">Docs</a>
          <span>·</span>
          <a href="{REPO_URL}" target="_blank" rel="noopener">Repo</a>
        </div>
        """,
        unsafe_allow_html=True,
    )


def sidebar() -> str:
    """Draw the navigation rail and return the selected view name."""
    st.session_state.setdefault("view", DEFAULT_VIEW)
    with st.sidebar:
        st.markdown(_icon_css(st.session_state["view"]), unsafe_allow_html=True)
        _brand()
        _nav()
        _settings_module()
    return st.session_state["view"]


def main() -> None:
    st.set_page_config(
        page_title="AI-MTA | Marketing ROI Analysis",
        page_icon="📊",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    theme.inject_css()

    selected = sidebar()

    # A database that is configured but unreachable would otherwise surface as
    # a stack trace inside whichever chart read it first.
    if config.use_database():
        usable, message = data_source.database_available()
        if not usable:
            st.error(
                f"**DATABASE=true, but the database cannot be used.** {message}\n\n"
                "Open **Settings** in the sidebar to correct the credentials or "
                "switch back to the committed files, or run "
                "`uv run --extra dashboard python script/import_to_database.py` "
                "to populate the database."
            )
            return

    VIEWS[selected]()


if __name__ == "__main__":
    main()
