"""Visual tokens and shared display components.

Every colour, chart default, and card in the dashboard comes from here, so a
change lands everywhere at once and no view invents its own styling.

The palette is the reference design's (`external/UI_design`): navy sidebar,
blue accent, and a light plane. The categorical series colours are a separate,
validated set -- the reference design contains no real charts, so its three
brand colours could not supply one. The eight series hues pass the lightness
band, chroma floor, colourblind separation, and normal-vision floor against
this dashboard's white chart surface.

Two rules the views rely on:

* Series colour follows the entity, never its rank, so filtering a chart never
  repaints the rows that survive. `series_colors` maps names to fixed slots.
* Status colour is reserved for reliability state and is always paired with a
  word, never carried by colour alone.
"""

from __future__ import annotations

import streamlit as st

# ---------------------------------------------------------------------------
# Brand, taken from the reference design
# ---------------------------------------------------------------------------

NAVY = "#071a3d"
BLUE = "#2456a6"
PALE_BLUE = "#eaf1fb"
PLANE = "#f5f6f8"
SURFACE = "#ffffff"
LINE = "#dfe3ea"
TEXT = "#161a22"
MUTED = "#667085"
SUBTLE = "#8a94a6"

#: Navigation rail. `RAIL_ICON` is also baked into the icon data URIs in
#: `app.py`, because a colour keyword does not inherit into a background image.
RAIL_TEXT = "#bac6df"
RAIL_ICON = "#bac6df"
RAIL_ICON_ACTIVE = "#ffffff"
RAIL_ACTIVE = "#143a79"
RAIL_DIM = "#8294b9"
RAIL_RULE = "#ffffff24"

#: Reliability states. Each is shown with its word, never colour alone.
GREEN = "#18794e"
AMBER = "#946200"
RED = "#b42318"

STATUS_COLORS = {
    "RELIABLE": GREEN,
    "UNRELIABLE": RED,
    "PARTIAL": AMBER,
}

# ---------------------------------------------------------------------------
# Chart palette
# ---------------------------------------------------------------------------

#: Fixed categorical order. Assigned by slot and never cycled: a ninth series
#: would be folded into "Other" rather than given a generated hue.
SERIES = (
    "#2a78d6",  # blue
    "#eb6834",  # orange
    "#1baf7a",  # aqua
    "#eda100",  # yellow
    "#e87ba4",  # magenta
    "#008300",  # green
    "#4a3aa7",  # violet
    "#e34948",  # red
)

#: One hue, light to dark, for magnitude. Never a rainbow.
SEQUENTIAL = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95"]

#: Warm and cool poles with a neutral midpoint, for above/below comparisons.
DIVERGING = ["#184f95", "#6da7ec", "#f0efec", "#eb8f7a", "#d03b3b"]

GRID = "#e8ebf0"
AXIS = "#c8cfda"

#: The two attribution models always keep the same colours across every view,
#: so a reader who learns "Markov is blue" is never contradicted.
MODEL_COLORS = {
    "markov": SERIES[0],
    "shapley": SERIES[1],
    "recommended": SERIES[6],
}

#: The three outcomes, likewise fixed.
OUTCOME_COLORS = {
    "converted_users": SERIES[0],
    "purchase_count": SERIES[2],
    "revenue": SERIES[3],
}

FONT = 'system-ui, -apple-system, "Segoe UI", sans-serif'


def series_colors(names) -> dict:
    """Map each name to a fixed palette slot, in the order given.

    The mapping is built from a stable ordering of the names, so the same
    entity keeps its colour no matter which subset a filter leaves on screen.
    """
    return {name: SERIES[index % len(SERIES)] for index, name in enumerate(names)}


def style_figure(figure, height: int = 320, legend: bool = True):
    """Apply the shared chart chrome: hairline grid, no chart junk.

    Height includes the axis band, so a card never needs an inner scrollbar.
    """
    figure.update_layout(
        height=height,
        margin=dict(l=8, r=8, t=28, b=8),
        paper_bgcolor=SURFACE,
        plot_bgcolor=SURFACE,
        font=dict(family=FONT, size=12, color=TEXT),
        # Every chart is titled by the markdown heading above it, so the figure
        # carries no title of its own. The text must still be set: styling a
        # title that has no text leaves Plotly drawing the string "undefined".
        title=dict(text="", font=dict(size=13, color=TEXT)),
        hoverlabel=dict(font_family=FONT, font_size=12, bgcolor=SURFACE),
        showlegend=legend,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="left",
            x=0,
            title_text="",
            font=dict(size=11, color=MUTED),
        ),
        bargap=0.28,
    )
    figure.update_xaxes(
        showgrid=False,
        showline=True,
        linecolor=AXIS,
        linewidth=1,
        ticks="outside",
        tickcolor=AXIS,
        tickfont=dict(size=11, color=MUTED),
        title_font=dict(size=11, color=MUTED),
    )
    figure.update_yaxes(
        showgrid=True,
        gridcolor=GRID,
        gridwidth=1,
        zeroline=False,
        showline=False,
        tickfont=dict(size=11, color=MUTED),
        title_font=dict(size=11, color=MUTED),
    )
    return figure


# ---------------------------------------------------------------------------
# Page styling
# ---------------------------------------------------------------------------

_CSS = f"""
<style>
  .stApp {{ background: {PLANE}; }}

  /* -------------------------------------------------------------------
     Navigation rail.

     The reference design's rail is a column of icon buttons. Streamlit has no
     icon-button widget, so each item is a real st.button carrying its icon as
     a background image (see `app.py::_icon_css` for why the icon cannot be a
     separate element) with the label beneath it. The button keeps its
     accessible name and keyboard behaviour, and the whole tile is one target.

     Pinning the foot needs an unbroken flex column from the sidebar down to
     the block that holds the items. Streamlit leaves two wrappers as
     `display:block` in between, so both are restated here; without them
     `margin-top:auto` on the foot has no flex parent to push against.
     ------------------------------------------------------------------- */
  section[data-testid="stSidebar"] {{ width: 138px !important; min-width: 138px !important; }}
  section[data-testid="stSidebar"] > div {{
    background: {NAVY};
    display: flex; flex-direction: column;
    padding: 0; height: 100%;
  }}
  section[data-testid="stSidebar"] * {{ color: {RAIL_TEXT}; }}
  section[data-testid="stSidebar"] [data-testid="stSidebarContent"] {{
    display: flex; flex-direction: column; height: 100%; padding: 0 7px 10px 7px;
  }}
  section[data-testid="stSidebar"] [data-testid="stSidebarUserContent"] {{
    display: flex; flex-direction: column; flex: 1 1 auto; min-height: 0;
    padding: 0;
  }}
  section[data-testid="stSidebar"] [data-testid="stSidebarUserContent"] > div {{
    display: flex; flex-direction: column; flex: 1 1 auto; min-height: 0;
  }}
  /* Streamlit reserves a 60px header row above the content for its logo and
     collapse control; the rail supplies its own brand block instead. */
  section[data-testid="stSidebar"] [data-testid="stSidebarHeader"] {{
    padding: 0; height: 0; min-height: 0;
  }}
  section[data-testid="stSidebar"] [data-testid="stSidebarCollapseButton"] {{
    position: absolute; top: 6px; right: 6px; z-index: 3;
  }}
  section[data-testid="stSidebar"] [data-testid="stSidebarCollapseButton"] button {{
    background: transparent; padding: 0; min-height: 0;
  }}

  .rail-brand {{
    height: 74px; border-bottom: 1px solid {RAIL_RULE}; display: grid;
    place-items: center; text-align: center; margin: 0 -7px 4px -7px;
  }}
  .rail-logo {{
    width: 31px; height: 31px; border: 1.5px solid #fff; border-radius: 50%;
    display: grid; place-items: center; font-weight: 800; color: #fff;
    font-size: 0.86rem; margin: auto;
  }}
  .rail-brand b {{ display: block; font-size: 11px; color: #fff; margin-top: 4px; }}
  .rail-brand span {{ display: block; font-size: 8px; letter-spacing: .8px; color: {RAIL_DIM}; }}

  .rail-label {{
    font-size: 8px; letter-spacing: .9px; color: {RAIL_DIM}; text-align: center;
    margin: 11px 0 4px;
  }}

  /* One tile: icon in the top band, label centred beneath it. The fixed height
     keeps one- and two-line labels on the same grid, which a padding-only rule
     could not do. */
  section[data-testid="stSidebar"] .stButton > button {{
    display: flex; align-items: flex-end; justify-content: center;
    width: 100%; height: 62px; min-height: 62px;
    border: 0; background-color: transparent; color: {RAIL_TEXT};
    padding: 0 3px 8px 3px; border-radius: 8px; margin: 0 0 2px 0;
    font-size: 10.5px; line-height: 1.2; font-weight: 500;
    box-shadow: none; transition: background-color .12s ease;
    background-repeat: no-repeat; background-position: center 11px;
    background-size: 19px 19px;
  }}
  section[data-testid="stSidebar"] .stButton > button p {{
    font-size: 10.5px; line-height: 1.2; margin: 0; text-align: center;
  }}
  section[data-testid="stSidebar"] .stButton > button:hover,
  section[data-testid="stSidebar"] .stButton > button:focus {{
    background-color: #ffffff12; color: #fff; box-shadow: none;
  }}
  section[data-testid="stSidebar"] .stButton > button:hover p,
  section[data-testid="stSidebar"] .stButton > button:focus p {{ color: #fff; }}

  /* The settings module: pinned to the foot and ruled off from the views, so
     dashboard plumbing never reads as a seventh place to navigate to.

     `st.container(key=...)` puts the key on an inner block and wraps it in a
     layout div. The wrapper is the flex item, so `margin-top: auto` has to go
     there -- on the keyed block it has no effect, because its parent is not
     the column doing the distributing. */
  section[data-testid="stSidebar"]
    [data-testid="stLayoutWrapper"]:has(> .st-key-rail_foot) {{
    margin-top: auto; flex: 0 0 auto;
  }}
  section[data-testid="stSidebar"] .st-key-rail_foot {{
    border-top: 1px solid {RAIL_RULE};
    padding: 10px 0 6px 0; text-align: center; gap: 0;
  }}
  .rail-status {{ display: flex; align-items: center; justify-content: center; gap: 5px; }}
  .rail-dot {{ width: 7px; height: 7px; border-radius: 50%; display: inline-block;
               flex: none; }}
  .rail-status-label {{ font-size: 10px; color: #fff; font-weight: 600; }}
  .rail-status-detail {{
    font-size: 8.5px; color: {RAIL_DIM}; line-height: 1.35; margin-top: 2px;
    overflow: hidden; display: -webkit-box;
    -webkit-line-clamp: 2; -webkit-box-orient: vertical;
  }}
  .rail-log {{
    font-size: 8px; letter-spacing: .7px; color: {RAIL_DIM}; margin: 6px 0 0;
    border: 1px solid {RAIL_RULE}; border-radius: 999px; padding: 2px 0;
  }}
  .rail-log.on {{ color: #7ee0b0; border-color: #7ee0b055; }}
  /* The foot's two buttons are shorter: no group label separates them. The
     status block above them is markdown, whose container collapses its own
     height, so the buttons need their own top gap or the gear rides up into
     the logging pill. */
  section[data-testid="stSidebar"] .st-key-rail_foot .stButton > button {{
    height: 50px; min-height: 50px; padding-bottom: 6px;
    background-position: center 7px; background-size: 17px 17px;
  }}
  /* The status block is markdown, whose container collapses to its content
     height; without this gap the gear icon rides up into the logging pill.
     `:first-child` keeps the gap off the outbound links, which are also
     markdown but close the rail and need no space beneath the pill. */
  section[data-testid="stSidebar"] .st-key-rail_foot
    [data-testid="stElementContainer"]:first-child [data-testid="stMarkdown"] {{
    margin-bottom: 16px;
  }}
  .rail-links {{
    display: flex; align-items: center; justify-content: center; gap: 6px;
    font-size: 9px; padding: 6px 0 0; border-top: 1px solid {RAIL_RULE};
    margin-top: 2px; color: {RAIL_DIM};
  }}
  .rail-links a {{ color: {RAIL_DIM}; text-decoration: none; }}
  .rail-links a:hover {{ color: #fff; text-decoration: underline; }}

  .block-container {{ padding-top: 2.2rem; max-width: 1400px; }}

  h1, h2, h3, h4 {{ color: {TEXT}; font-family: {FONT}; }}
  h1 {{ font-size: 1.5rem !important; font-weight: 650; }}
  h2 {{ font-size: 1.12rem !important; font-weight: 620; margin-top: 0.4rem; }}
  h3 {{ font-size: 0.98rem !important; font-weight: 600; }}

  /* Metric tiles: a card, not a bare number on the plane. */
  div[data-testid="stMetric"] {{
    background: {SURFACE};
    border: 1px solid {LINE};
    border-radius: 10px;
    padding: 14px 16px;
  }}
  div[data-testid="stMetricLabel"] p {{
    color: {MUTED}; font-size: 0.76rem; font-weight: 550;
    text-transform: uppercase; letter-spacing: 0.03em;
  }}
  div[data-testid="stMetricValue"] {{
    color: {TEXT}; font-size: 1.5rem; font-weight: 620;
  }}

  div[data-testid="stDataFrame"], div[data-testid="stPlotlyChart"] {{
    background: {SURFACE};
    border: 1px solid {LINE};
    border-radius: 10px;
    padding: 6px;
  }}

  .stTabs [data-baseweb="tab-list"] {{ gap: 18px; border-bottom: 1px solid {LINE}; }}
  .stTabs [data-baseweb="tab"] {{ font-size: 0.88rem; color: {MUTED}; }}
  .stTabs [aria-selected="true"] {{ color: {BLUE}; }}

  .panel {{
    background: {SURFACE}; border: 1px solid {LINE}; border-radius: 10px;
    padding: 16px 18px; margin-bottom: 12px;
  }}
  .panel-title {{
    font-size: 0.76rem; font-weight: 600; color: {MUTED};
    text-transform: uppercase; letter-spacing: 0.04em; margin-bottom: 10px;
  }}
  .kv {{ display: flex; justify-content: space-between; padding: 5px 0;
         border-bottom: 1px solid {PLANE}; font-size: 0.86rem; }}
  .kv:last-child {{ border-bottom: none; }}
  .kv span:first-child {{ color: {MUTED}; }}
  .kv span:last-child {{ color: {TEXT}; font-weight: 550; }}

  .pill {{
    display: inline-block; padding: 2px 9px; border-radius: 999px;
    font-size: 0.74rem; font-weight: 600; letter-spacing: 0.02em;
  }}
  .caption {{ color: {SUBTLE}; font-size: 0.78rem; line-height: 1.5; }}
</style>
"""


def inject_css() -> None:
    """Apply the dashboard stylesheet once per page load."""
    st.markdown(_CSS, unsafe_allow_html=True)


def status_pill(status: str) -> str:
    """Return a coloured pill that always carries the status word itself."""
    status = str(status or "UNKNOWN").upper()
    color = STATUS_COLORS.get(status, MUTED)
    tint = {"RELIABLE": "#eaf7f0", "UNRELIABLE": "#fdf0ef", "PARTIAL": "#fff5d8"}.get(
        status, PLANE
    )
    return f'<span class="pill" style="background:{tint};color:{color}">{status}</span>'


def panel(title: str, rows: list[tuple[str, str]]) -> None:
    """Render a titled card of label/value pairs."""
    items = "".join(
        f'<div class="kv"><span>{label}</span><span>{value}</span></div>'
        for label, value in rows
    )
    st.markdown(
        f'<div class="panel"><div class="panel-title">{title}</div>{items}</div>',
        unsafe_allow_html=True,
    )


def caption(text: str) -> None:
    """Render explanatory text below a chart or table."""
    st.markdown(f'<p class="caption">{text}</p>', unsafe_allow_html=True)


def money(value: float, currency: str = "$") -> str:
    """Format a currency amount for display."""
    try:
        return f"{currency}{float(value):,.2f}"
    except (TypeError, ValueError):
        return "--"


def number(value: float, digits: int = 0) -> str:
    """Format a count for display."""
    try:
        return f"{float(value):,.{digits}f}"
    except (TypeError, ValueError):
        return "--"


def percent(value: float, digits: int = 1) -> str:
    """Format a 0-1 share as a percentage."""
    try:
        return f"{float(value) * 100:.{digits}f}%"
    except (TypeError, ValueError):
        return "--"
