"""
Streamlit UI for the Cost-Center Drill-Down Analyzer.

Presentation layer only: all business logic lives in data_engine.py.
User-facing text is Hebrew (RTL); code, identifiers and data stay English.

Run with:  streamlit run app.py
"""

from __future__ import annotations

import html
import io

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import data_engine as de

# ---------------------------------------------------------------------------
# Design tokens
# ---------------------------------------------------------------------------

# Dark SaaS theme (keep in sync with .streamlit/config.toml)
COLOR_BACKGROUND = "#0a0f1c"
COLOR_SURFACE = "#111827"
COLOR_SURFACE_ALT = "#1f2937"
COLOR_SIDEBAR = "#0d1321"
COLOR_TEXT = "#f8fafc"
COLOR_MUTED = "#94a3b8"
COLOR_BORDER = "rgba(255, 255, 255, 0.1)"
COLOR_GRID = "rgba(255, 255, 255, 0.06)"
COLOR_PINK = "#ec4899"
COLOR_PURPLE = "#a855f7"
COLOR_CYAN = "#22d3ee"
# Variance semantics stay red/green, in neon tones readable on dark
COLOR_OVERSPEND = "#f43f5e"
COLOR_SAVINGS = "#34d399"
GRADIENT = f"linear-gradient(to left, {COLOR_PINK}, {COLOR_PURPLE})"
NEON_SEQUENCE = ["#a855f7", "#ec4899", "#22d3ee", "#6366f1",
                 "#f472b6", "#2dd4bf", "#c084fc", "#67e8f9"]
# Calibri (the Excel default) first; Carlito is its metric-compatible web
# twin for viewers without Office, and Heebo covers Hebrew glyphs Calibri lacks.
FONT_FAMILY = "Calibri, Carlito, Heebo, 'Segoe UI', Arial, sans-serif"

# ---------------------------------------------------------------------------
# Hebrew display labels (data values stay English in the backend)
# ---------------------------------------------------------------------------

MONTH_NAMES_HE = {
    1: "ינואר", 2: "פברואר", 3: "מרץ", 4: "אפריל", 5: "מאי", 6: "יוני",
    7: "יולי", 8: "אוגוסט", 9: "ספטמבר", 10: "אוקטובר", 11: "נובמבר",
    12: "דצמבר",
}

COST_CENTER_HE = {
    "HR": "משאבי אנוש",
    "IT": "מערכות מידע",
    "Marketing": "שיווק",
    "R&D": "מחקר ופיתוח",
    "Operations": "תפעול",
}

CATEGORY_HE = {
    "Payroll": "שכר",
    "Software Licenses": "רישוי תוכנה",
    "Cloud Infrastructure": "תשתיות ענן",
    "Travel": "נסיעות",
    "Consulting": "ייעוץ",
    "Office Supplies": "ציוד משרדי",
    "Advertising": "פרסום",
    "Employee Welfare": "רווחת עובדים",
}

# Status dots rendered with CSS for consistent colors across platforms
STATUS_ICON = {
    de.STATUS_OVERSPEND: '<span class="dot dot-red" title="חריגה"></span>',
    de.STATUS_SAVINGS: '<span class="dot dot-green" title="חיסכון"></span>',
    de.STATUS_ON_TRACK: '<span class="dot dot-gray" title="בתחום"></span>',
}

VIEW_YTD = "מצטבר מתחילת השנה (YTD)"
VIEW_MTD = "חודש בודד"

# Cost-behavior slicer: backend values stay English, labels are Hebrew
BEHAVIOR_ALL = "All"
BEHAVIOR_HE = {
    BEHAVIOR_ALL: "הכל",
    de.BEHAVIOR_FIXED: "קבועה",
    de.BEHAVIOR_VARIABLE: "משתנה",
}

# ---------------------------------------------------------------------------
# Global CSS
# ---------------------------------------------------------------------------

CUSTOM_CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Carlito:wght@400;700&family=Heebo:wght@300;400;500;700;800&display=swap');

/* ---------- Typography: Calibri everywhere ---------- */
html, body, .stApp, .stApp h1, .stApp h2, .stApp h3, .stApp h4,
.stApp p, .stApp span, .stApp div, .stApp label, .stApp li,
.stApp table, .stApp th, .stApp td, .stMarkdown,
button, input, select, textarea {{
    font-family: {FONT_FAMILY} !important;
}}
/* Keep Material icons (sidebar toggle, expander chevrons) as glyphs */
.stApp [data-testid="stIconMaterial"] {{
    font-family: 'Material Symbols Rounded' !important;
}}

/* ---------- Canvas ---------- */
.stApp {{
    background-color: {COLOR_BACKGROUND};
    /* Faint neon glows in the corners for depth */
    background-image:
        radial-gradient(900px 500px at 100% -10%, rgba(168, 85, 247, 0.10), transparent 60%),
        radial-gradient(700px 400px at 0% 0%, rgba(236, 72, 153, 0.06), transparent 60%);
    background-attachment: fixed;
    color: {COLOR_TEXT};
}}
header[data-testid="stHeader"] {{ background: transparent; }}

/* ---------- Global RTL ----------
   direction: rtl on the app root flips every flex row, so the sidebar
   moves to the right and st.columns render right-to-left (col1 = rightmost).
   No row-reverse is needed; adding it would flip the layout back to LTR. */
.stApp, [data-testid="stAppViewContainer"], [data-testid="stSidebar"],
[data-testid="stMain"], [data-testid="stMainBlockContainer"] {{
    direction: rtl;
}}
.stApp p, .stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5, .stApp h6,
.stApp label, .stApp li, .stApp th, .stApp td,
[data-testid="stMarkdownContainer"], [data-testid="stCaptionContainer"],
[data-testid="stWidgetLabel"], .kpi-card, .kpi-card div,
.alert-banner, .section-title, .section-caption,
.page-title, .page-subtitle {{
    text-align: right !important;
}}
[data-testid="stMainBlockContainer"] {{ padding-top: 2rem; max-width: 1400px; }}

/* Financial numbers: isolated LTR run, so the minus sign stays on the left
   of the digits and the ₪ sign stays on their right inside Hebrew text. */
.num-ltr {{ direction: ltr; unicode-bidi: isolate; display: inline-block; }}

/* Keep interactive grids and charts LTR internally to avoid rendering bugs */
[data-testid="stDataFrame"], .js-plotly-plot {{ direction: ltr; }}

/* ---------- Sidebar (on the right; border on its inner/left edge) ---------- */
[data-testid="stSidebar"] {{
    background-color: {COLOR_SIDEBAR};
    border-left: 1px solid {COLOR_BORDER};
    border-right: none;
}}
[data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3, [data-testid="stSidebar"] p,
[data-testid="stSidebar"] label, [data-testid="stSidebar"] span,
[data-testid="stSidebar"] div {{
    color: {COLOR_TEXT};
}}
[data-testid="stSidebar"] hr {{ border-color: {COLOR_BORDER}; }}

/* Collapsed state: Streamlit shrinks the sidebar to 1px and slides it by
   -width, which assumes an LTR (left) sidebar. In RTL that pushes it into the
   main area and the squeezed text wraps letter-by-letter over the dashboard,
   so clip everything and slide it off the right edge instead. */
[data-testid="stSidebar"][aria-expanded="false"] {{
    overflow: hidden !important;
    transform: translateX(100%) !important;
    border-left: none;
}}
[data-testid="stSidebar"][aria-expanded="false"] h1,
[data-testid="stSidebar"][aria-expanded="false"] h2,
[data-testid="stSidebar"][aria-expanded="false"] h3,
[data-testid="stSidebar"][aria-expanded="false"] p,
[data-testid="stSidebar"][aria-expanded="false"] label,
[data-testid="stSidebar"][aria-expanded="false"] div {{
    white-space: nowrap !important;
    overflow: hidden !important;
}}
.sidebar-logo {{
    font-size: 1.35rem; font-weight: 800; line-height: 1.3;
    padding: 0.5rem 0 0.25rem 0;
}}
.sidebar-tagline {{ font-size: 0.85rem; color: {COLOR_MUTED} !important; }}
.sidebar-info {{
    background: rgba(255, 255, 255, 0.04); border: 1px solid {COLOR_BORDER};
    border-radius: 16px; padding: 0.8rem 1rem; font-size: 0.85rem; line-height: 1.8;
}}

/* ---------- Typography ---------- */
.page-title {{
    font-size: 2.4rem; font-weight: 800; color: #ffffff; margin: 0;
    letter-spacing: -0.01em;
}}
.page-subtitle {{ color: {COLOR_MUTED}; font-size: 1rem; margin-bottom: 1.25rem; }}
.section-title {{
    font-size: 1.3rem; font-weight: 800; color: #ffffff;
    margin: 0 0 0.25rem 0;
}}
.section-caption {{ color: {COLOR_MUTED}; font-size: 0.9rem; margin-bottom: 0.75rem; }}
/* Pink-to-purple gradient text for highlights */
.gradient-text {{
    background: {GRADIENT};
    -webkit-background-clip: text;
    background-clip: text;
    -webkit-text-fill-color: transparent;
}}

/* ---------- Cards: any container whose key starts with "card" ---------- */
div[class*="st-key-card"] {{
    background: {COLOR_SURFACE};
    border: 1px solid {COLOR_BORDER};
    border-radius: 20px;
    padding: 1.4rem 1.6rem;
    box-shadow: 0 20px 40px rgba(0, 0, 0, 0.25);
}}

/* ---------- Alert banner ---------- */
.alert-banner {{
    border-radius: 20px; padding: 1rem 1.3rem; margin-bottom: 1.25rem;
    font-size: 1.02rem; line-height: 1.7; border: 1px solid;
}}
.alert-red {{
    background: rgba(244, 63, 94, 0.08); border-color: rgba(244, 63, 94, 0.35);
    color: #fecdd3; box-shadow: 0 0 28px rgba(244, 63, 94, 0.10);
}}
.alert-green {{
    background: rgba(52, 211, 153, 0.07); border-color: rgba(52, 211, 153, 0.35);
    color: #d1fae5; box-shadow: 0 0 28px rgba(52, 211, 153, 0.08);
}}
.alert-banner b {{ font-weight: 700; color: #ffffff; }}

/* ---------- KPI cards (HTML cards + native st.metric, same look) ---------- */
.kpi-card, [data-testid="stMetric"] {{
    background: {COLOR_SURFACE};
    border: 1px solid {COLOR_BORDER};
    border-radius: 20px;
    padding: 1.2rem 1.4rem;
    height: 100%;
}}
/* Variance card: gradient border + soft glow, red or green */
.kpi-glow-red, .kpi-glow-green {{
    border: 1px solid transparent;
    background:
        linear-gradient({COLOR_SURFACE}, {COLOR_SURFACE}) padding-box,
        var(--glow-gradient) border-box;
}}
.kpi-glow-red {{
    --glow-gradient: linear-gradient(to left, {COLOR_OVERSPEND}, {COLOR_PINK});
    box-shadow: 0 0 32px rgba(244, 63, 94, 0.22);
}}
.kpi-glow-green {{
    --glow-gradient: linear-gradient(to left, {COLOR_SAVINGS}, {COLOR_CYAN});
    box-shadow: 0 0 32px rgba(52, 211, 153, 0.18);
}}
.kpi-label, [data-testid="stMetricLabel"] {{
    color: {COLOR_MUTED}; font-size: 0.95rem; font-weight: 500;
}}
.kpi-value, [data-testid="stMetricValue"] {{
    /* Fluid size: five cards share one row on desktop */
    font-size: clamp(1.2rem, 1.55vw, 1.9rem);
    font-weight: 800; color: #ffffff; margin: 0.2rem 0; white-space: nowrap;
}}
.kpi-sub {{ color: {COLOR_MUTED}; font-size: 0.85rem; }}
/* Compact KPI row used inside drill-down cards */
.kpi-mini-row {{ display: flex; gap: 0.75rem; }}
.kpi-mini {{
    flex: 1; background: rgba(255, 255, 255, 0.03); border: 1px solid {COLOR_BORDER};
    border-radius: 16px; padding: 0.75rem 1rem;
}}
.kpi-mini-value {{ font-size: 1.3rem; font-weight: 800; color: #ffffff; }}
.kpi-red {{ color: {COLOR_OVERSPEND} !important; text-shadow: 0 0 18px rgba(244, 63, 94, 0.45); }}
.kpi-green {{ color: {COLOR_SAVINGS} !important; text-shadow: 0 0 18px rgba(52, 211, 153, 0.4); }}

/* ---------- Selectboxes: pill shape ---------- */
[data-testid="stSelectbox"] div[data-baseweb="select"],
[data-testid="stSelectbox"] div[data-baseweb="select"] > div {{
    border-radius: 50px !important;
}}
[data-testid="stSelectbox"] div[data-baseweb="select"] > div {{
    background-color: {COLOR_SURFACE_ALT} !important;
    border: 1px solid rgba(255, 255, 255, 0.2) !important;
    padding-inline: 0.5rem;
    transition: border-color 0.2s, box-shadow 0.2s;
}}
[data-testid="stSelectbox"] div[data-baseweb="select"] > div:hover {{
    border-color: rgba(255, 255, 255, 0.5) !important;
}}
[data-testid="stSelectbox"] div[data-baseweb="select"] > div:focus-within {{
    border-color: {COLOR_PURPLE} !important;
    box-shadow: 0 0 0 3px rgba(168, 85, 247, 0.25);
}}
[data-testid="stSelectbox"] div[data-baseweb="select"] * {{ color: #ffffff !important; }}

/* ---------- Radio (cost-behavior slicer): segmented pills ---------- */
[data-testid="stRadio"] div[role="radiogroup"] {{ gap: 0.4rem; flex-wrap: wrap; }}
[data-testid="stRadio"] label[data-baseweb="radio"] {{
    margin: 0; padding: 0.3rem 1rem;
    border: 1px solid rgba(255, 255, 255, 0.2); border-radius: 50px;
    background: {COLOR_SURFACE_ALT}; cursor: pointer;
    transition: border-color 0.2s, box-shadow 0.2s;
}}
/* Hide the native radio circle: the whole pill is the control */
[data-testid="stRadio"] label[data-baseweb="radio"] > div:first-child {{ display: none; }}
[data-testid="stRadio"] label[data-baseweb="radio"]:hover {{
    border-color: rgba(255, 255, 255, 0.5);
}}
[data-testid="stRadio"] label[data-baseweb="radio"]:has(input:checked) {{
    background: linear-gradient(to right, {COLOR_PINK}, {COLOR_PURPLE});
    border-color: transparent;
    box-shadow: 0 4px 16px rgba(217, 70, 239, 0.35);
}}
[data-testid="stRadio"] label[data-baseweb="radio"]:has(input:checked) p {{
    color: #ffffff; font-weight: 700;
}}

/* ---------- Buttons (incl. CSV download): gradient pill ---------- */
[data-testid="stButton"] button,
[data-testid="stDownloadButton"] button {{
    border-radius: 50px;
    background: linear-gradient(to right, {COLOR_PINK}, {COLOR_PURPLE});
    border: none;
    color: #ffffff;
    font-weight: 700;
    padding: 0.55rem 1.4rem;
    box-shadow: 0 8px 24px rgba(217, 70, 239, 0.25);
    transition: transform 0.15s, box-shadow 0.15s, filter 0.15s;
}}
[data-testid="stButton"] button:hover,
[data-testid="stDownloadButton"] button:hover {{
    color: #ffffff; filter: brightness(1.1); transform: translateY(-1px);
    box-shadow: 0 10px 30px rgba(217, 70, 239, 0.4);
}}
[data-testid="stButton"] button p,
[data-testid="stDownloadButton"] button p {{ color: #ffffff; font-weight: 700; }}

/* ---------- Tables ---------- */
/* st.dataframe cells are canvas-drawn: colors come from config.toml */
[data-testid="stDataFrame"] {{
    border: 1px solid {COLOR_BORDER}; border-radius: 16px; overflow: hidden;
}}
/* HTML tables (red flags, category breakdown) */
.fin-table {{ width: 100%; border-collapse: collapse; font-size: 0.93rem; direction: rtl; }}
.fin-table th {{
    text-align: right; color: rgba(255, 255, 255, 0.55); font-weight: 600;
    border-bottom: 1px solid {COLOR_BORDER}; padding: 0.6rem 0.6rem;
}}
.fin-table td {{
    padding: 0.6rem 0.6rem; border-bottom: 1px solid rgba(255, 255, 255, 0.05);
    color: #e2e8f0;
}}
.fin-table tr:hover td {{ background: rgba(255, 255, 255, 0.03); }}
.fin-table .num {{ white-space: nowrap; }}
.cell-red {{ color: {COLOR_OVERSPEND}; font-weight: 700; }}
.cell-green {{ color: {COLOR_SAVINGS}; font-weight: 700; }}
.rank {{ color: {COLOR_MUTED}; font-weight: 600; }}
.dot {{ display: inline-block; width: 10px; height: 10px; border-radius: 50%; }}
.dot-red {{ background: {COLOR_OVERSPEND}; box-shadow: 0 0 10px {COLOR_OVERSPEND}; }}
.dot-green {{ background: {COLOR_SAVINGS}; box-shadow: 0 0 10px {COLOR_SAVINGS}; }}
.dot-gray {{ background: #475569; }}

/* ---------- Clean app chrome ----------
   Hide the main menu, Deploy button and header for a standalone-app look.
   The "expand sidebar" control lives inside the header, so it is made
   visible again: otherwise a collapsed sidebar (the default on mobile)
   could never be reopened. */
#MainMenu {{ visibility: hidden; }}
header {{ visibility: hidden; }}
[data-testid="stAppDeployButton"] {{ display: none; }}
[data-testid="stExpandSidebarButton"] {{ visibility: visible; }}

/* Compact template buttons so the labels fit on one line */
[data-testid="stSidebar"] [data-testid="stDownloadButton"] button {{
    padding: 0.45rem 0.8rem;
}}
[data-testid="stSidebar"] [data-testid="stDownloadButton"] button p {{
    font-size: 0.85rem; white-space: nowrap;
}}

/* Sidebar expander (data templates) */
[data-testid="stSidebar"] [data-testid="stExpander"] details {{
    border: 1px solid {COLOR_BORDER}; border-radius: 16px;
    background: rgba(255, 255, 255, 0.03);
}}
</style>
"""

# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------


def fmt_ils(value: float, signed: bool = False) -> str:
    """
    Format an amount as ILS: currency sign before the digits, sign before
    the currency (e.g. '₪ 18,185,500', '-₪ 118,446'), no decimals.
    """
    if value < 0 and round(value) != 0:
        sign = "-"
    elif signed and value > 0 and round(value) != 0:
        sign = "+"
    else:
        sign = ""
    return f"{sign}₪ {abs(value):,.0f}"


# Unicode isolates (LRI ... PDI) keep amounts intact inside Plotly SVG text,
# where HTML spans are not available.
LRI, PDI = "⁦", "⁩"
ILS_HOVER = f"{LRI}₪ %{{VALUE}}{PDI}"


def plot_ils(value: float, signed: bool = False) -> str:
    """ILS amount wrapped in a bidi isolate for use in Plotly labels."""
    return f"{LRI}{fmt_ils(value, signed)}{PDI}"


def hover_ils(field: str) -> str:
    """Plotly hover snippet for a non-negative amount field, e.g. '%{y:,.0f}'."""
    return ILS_HOVER.replace("%{VALUE}", field)


def fmt_pct(value: float) -> str:
    """Format a ratio as a signed percentage."""
    return "—" if pd.isna(value) else f"{value:+.1%}"


def fmt_pct_plain(value: float) -> str:
    """Format a ratio as an unsigned percentage (e.g. '5%')."""
    return f"{value:.0%}"


def ltr(text: str) -> str:
    """Wrap a numeric string so signs and symbols render correctly in RTL."""
    return f'<span class="num-ltr" dir="ltr">{html.escape(text)}</span>'


def to_excel_csv(df: pd.DataFrame) -> bytes:
    """
    Serialize a DataFrame to CSV bytes encoded as UTF-8 with BOM (utf-8-sig),
    so Excel opens Hebrew text correctly.

    Writes to a binary buffer on purpose: when to_csv() returns a string
    (no buffer given), pandas silently ignores the encoding argument.
    """
    buffer = io.BytesIO()
    df.to_csv(buffer, index=False, encoding="utf-8-sig")
    return buffer.getvalue()


def month_label(month: str) -> str:
    """Convert '2026-05' to 'מאי 2026'."""
    year, month_num = month.split("-")
    return f"{MONTH_NAMES_HE[int(month_num)]} {year}"


def cc_label(cost_center: str) -> str:
    return COST_CENTER_HE.get(cost_center, cost_center)


def category_label(category: str) -> str:
    return CATEGORY_HE.get(category, category)


def variance_class(variance: float) -> str:
    """CSS class for a variance value: red for overspend, green for savings."""
    if variance > 0:
        return "cell-red"
    return "cell-green" if variance < 0 else ""


def style_figure(fig: go.Figure, height: int) -> go.Figure:
    """Apply the shared dark chart style: transparent background, light text."""
    fig.update_layout(
        height=height,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family=FONT_FAMILY, color=COLOR_TEXT, size=13),
        font_color=COLOR_TEXT,
        margin=dict(l=10, r=10, t=40, b=10),
        hoverlabel=dict(font_family=FONT_FAMILY, bgcolor=COLOR_SURFACE_ALT,
                        bordercolor=COLOR_PURPLE, font_color=COLOR_TEXT),
    )
    fig.update_xaxes(color=COLOR_MUTED, linecolor=COLOR_BORDER)
    fig.update_yaxes(color=COLOR_MUTED, linecolor=COLOR_BORDER)
    return fig


PLOTLY_CONFIG = {"displayModeBar": False}

# ---------------------------------------------------------------------------
# Data access (cached)
# ---------------------------------------------------------------------------


@st.cache_data(show_spinner="טוען נתונים...")
def load_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load actuals and the variance table once per session."""
    _, actuals, table = de.load_all()
    return actuals, table


# ---------------------------------------------------------------------------
# UI sections
# ---------------------------------------------------------------------------


def render_sidebar(closed_months: list[str],
                   last_closed: str) -> tuple[str, str, str | None]:
    """Render the sidebar and return (period, month, cost behavior or None)."""
    with st.sidebar:
        st.markdown(
            '<div class="sidebar-logo">📊 מערכת בקרת תקציב - Drill-Down</div>'
            '<div class="sidebar-tagline">ניתוח תקציב מול ביצוע ברמת מרכז עלות</div>',
            unsafe_allow_html=True,
        )
        st.divider()
        view = st.selectbox("סוג תצוגה", [VIEW_YTD, VIEW_MTD], key="view")
        is_ytd = view == VIEW_YTD
        month = st.selectbox(
            "עד חודש" if is_ytd else "חודש",
            options=list(reversed(closed_months)),
            format_func=month_label,
            key="month",
        )
        behavior = st.radio(
            "סוג הוצאה",
            list(BEHAVIOR_HE),
            format_func=BEHAVIOR_HE.get,
            horizontal=True,
            key="cost_behavior",
        )
        st.divider()
        st.markdown(
            f'<div class="sidebar-info">'
            f'🗓️ שנת תקציב: <b>{last_closed[:4]}</b><br>'
            f'🔒 חודש סגור אחרון: <b>{month_label(last_closed)}</b><br>'
            f'⚖️ סף מהותיות: <b>{ltr(fmt_pct_plain(de.MATERIALITY_PCT))}</b> וגם '
            f'<b>{ltr(fmt_ils(de.MATERIALITY_ABS))}</b>'
            f'</div>',
            unsafe_allow_html=True,
        )
        st.write("")
        render_data_templates()
    period = de.PERIOD_YTD if is_ytd else de.PERIOD_MTD
    return period, month, None if behavior == BEHAVIOR_ALL else behavior


def render_data_templates() -> None:
    """Sidebar expander with empty CSV templates matching the data schema."""
    with st.expander("עדכון נתונים - תבניות להורדה"):
        st.caption("קובצי CSV ריקים עם שמות העמודות שמנוע הנתונים מצפה להם.")
        # Column lists come from data_engine, so templates never drift
        # from what the loader validates
        st.download_button(
            "הורד תבנית תקציב (CSV)",
            data=to_excel_csv(pd.DataFrame(columns=de.BUDGET_COLUMNS)),
            file_name="budget_template.csv",
            mime="text/csv",
            width="stretch",
            key="template_budget",
        )
        st.download_button(
            "הורד תבנית פקודות יומן (CSV)",
            data=to_excel_csv(pd.DataFrame(columns=de.ACTUALS_COLUMNS)),
            file_name="actuals_gl_template.csv",
            mime="text/csv",
            width="stretch",
            key="template_gl",
        )


def period_label(period: str, month: str) -> str:
    """Human-readable Hebrew description of the selected period."""
    if period == de.PERIOD_YTD:
        return f"מצטבר ינואר–{month_label(month)}"
    return month_label(month)


def render_alert_banner(totals: dict, flag_count: int, label: str) -> None:
    """Top banner: overall status for the period plus hidden red flags."""
    variance, pct = totals["variance"], totals["variance_pct"]
    if variance > 0:
        css, icon = "alert-red", "⚠️"
        headline = (f"<b>חריגה מהתקציב</b> בתקופה ({label}): "
                    f"{ltr(fmt_ils(variance, signed=True))} ({ltr(fmt_pct(pct))}).")
    else:
        css, icon = "alert-green", "✅"
        headline = (f"<b>הביצוע בתוך התקציב</b> בתקופה ({label}): "
                    f"חיסכון של {ltr(fmt_ils(abs(variance)))} ({ltr(fmt_pct(pct))}).")

    if flag_count:
        detail = (f"<br>🔎 עם זאת, זוהו <b>{flag_count}</b> חריגות מהותיות ברמת "
                  f"חודש וקטגוריה, שמקוזזות בסיכום הכולל — ראו \"דגלים אדומים\".")
    else:
        detail = "<br>לא זוהו חריגות מהותיות ברמת חודש וקטגוריה."
    st.markdown(f'<div class="alert-banner {css}">{icon} {headline}{detail}</div>',
                unsafe_allow_html=True)


def kpi_card(label: str, value: str, sub: str, value_class: str = "",
             card_class: str = "") -> str:
    """HTML for a single KPI card (card_class adds e.g. a glow border)."""
    return (f'<div class="kpi-card {card_class}"><div class="kpi-label">{label}</div>'
            f'<div class="kpi-value {value_class}">{value}</div>'
            f'<div class="kpi-sub">{sub}</div></div>')


def run_rate_card(rr: dict) -> str:
    """KPI card for the straight-line run-rate forecast, with status glow."""
    projected = rr["projected_variance"]
    # Sign-based glow, like the total-variance card: any projected overrun
    # is red, any projected saving is green
    is_over = projected > 0
    projected_text = (f'{fmt_ils(projected, signed=True)} '
                      f'({fmt_pct(rr["projected_variance_pct"])})')
    return kpi_card(
        # Isolated so "(Run-Rate)" never breaks across lines
        f'תחזית גמר שנה {ltr("(Run-Rate)")}',
        ltr(fmt_ils(rr["run_rate"])),
        f'סטייה צפויה <span class="{variance_class(projected)}">'
        f'{ltr(projected_text)}</span><br>'
        f'לפי קצב שריפה ממוצע של {ltr(fmt_ils(rr["avg_monthly"]))} לחודש',
        value_class="kpi-red" if is_over else "kpi-green",
        card_class="kpi-glow-red" if is_over else "kpi-glow-green",
    )


def render_kpis(totals: dict, full_year: pd.DataFrame, rr: dict, label: str,
                last_closed: str) -> None:
    """KPI cards: budget, actual, variance and two year-end forecasts."""
    annual_budget = full_year["Annual_Budget"].sum()
    forecast = full_year["Forecast"].sum()
    forecast_var = forecast - annual_budget
    variance = totals["variance"]

    cards = [
        kpi_card("סך תקציב", ltr(fmt_ils(totals["budget"])), label),
        kpi_card("סך ביצוע", ltr(fmt_ils(totals["actual"])),
                 f'{totals["entries"]:,} פקודות יומן'),
        kpi_card('<span class="gradient-text">סך סטייה</span>',
                 ltr(fmt_ils(variance, signed=True)),
                 f'{ltr(fmt_pct(totals["variance_pct"]))} מהתקציב · '
                 f'{"חריגה" if variance > 0 else "חיסכון"}',
                 value_class="kpi-red" if variance > 0 else "kpi-green",
                 card_class="kpi-glow-red" if variance > 0 else "kpi-glow-green"),
        kpi_card("תחזית גמר שנה (תקציבית)", ltr(fmt_ils(forecast)),
                 f'תקציב שנתי {ltr(fmt_ils(annual_budget))}<br>סטייה צפויה '
                 f'<span class="{variance_class(forecast_var)}">'
                 f'{ltr(fmt_ils(forecast_var, signed=True))}</span>'),
        run_rate_card(rr),
    ]
    for column, card in zip(st.columns(len(cards)), cards):
        column.markdown(card, unsafe_allow_html=True)
    st.caption(
        f"תחזית תקציבית: ביצוע בפועל עד {month_label(last_closed)} + יתרת התקציב "
        f"לחודשים שטרם נסגרו. · Run-Rate: ממוצע חודשי בתקופה הנבחרת × 12, "
        f"בקו ישר וללא עונתיות."
    )


def render_red_flags(flags: pd.DataFrame, label: str) -> None:
    """Top material overspends at month x cost center x category level."""
    with st.container(key="card_red_flags"):
        st.markdown(
            f'<div class="section-title">🚩 <span class="gradient-text">דגלים אדומים'
            f'</span> — 10 החריגות המהותיות הגדולות</div>'
            f'<div class="section-caption">ברמת חודש × מחלקה × '
            f'קטגוריה · {label} · חריגות אלו עלולות להיות מוסתרות בסיכום '
            f'המצטבר</div>',
            unsafe_allow_html=True,
        )
        if flags.empty:
            st.success("לא נמצאו חריגות מהותיות בתקופה שנבחרה.")
            return

        header = ("<tr><th>#</th><th>חודש</th><th>מחלקה</th><th>קטגוריה</th>"
                  "<th>תקציב</th><th>ביצוע</th><th>סטייה</th><th>סטייה %</th></tr>")
        rows = []
        for rank, row in enumerate(flags.itertuples(index=False), start=1):
            rows.append(
                f'<tr><td class="rank">{rank}</td>'
                f'<td>{month_label(row.Month)}</td>'
                f'<td>{html.escape(cc_label(row.Cost_Center))}</td>'
                f'<td>{html.escape(category_label(row.Expense_Category))}</td>'
                f'<td class="num">{ltr(fmt_ils(row.Budget_Amount))}</td>'
                f'<td class="num">{ltr(fmt_ils(row.Actual_Amount))}</td>'
                f'<td class="num cell-red">🔴 {ltr(fmt_ils(row.Variance, signed=True))}</td>'
                f'<td class="num cell-red">{ltr(fmt_pct(row.Variance_Pct))}</td></tr>'
            )
        st.markdown(f'<table class="fin-table">{header}{"".join(rows)}</table>',
                    unsafe_allow_html=True)


def render_variance_waterfall(cc_summary: pd.DataFrame, label: str) -> None:
    """
    Drill-down level 1: variance bridge by cost center.

    Each cost center is a relative step (red = overspend, green = savings);
    the final bar is the total period variance they add up to.
    """
    with st.container(key="card_level1"):
        st.markdown(
            f'<div class="section-title">רמה 1 · גשר סטיות לפי מרכז עלות</div>'
            f'<div class="section-caption">{label} · כיצד כל מחלקה תורמת לסטייה '
            f'הכוללת · אדום = חריגה, ירוק = חיסכון</div>',
            unsafe_allow_html=True,
        )
        # Overspends first, then savings: the bridge climbs and then descends
        steps = cc_summary.sort_values("Variance", ascending=False)
        total_variance = steps["Variance"].sum()
        values = steps["Variance"].tolist() + [total_variance]
        labels = [plot_ils(v, signed=True) for v in values]

        waterfall = go.Figure(go.Waterfall(
            x=steps["Cost_Center"].map(cc_label).tolist() + ["סך סטייה"],
            y=values,
            measure=["relative"] * len(steps) + ["total"],
            increasing=dict(marker=dict(color=COLOR_OVERSPEND)),
            decreasing=dict(marker=dict(color=COLOR_SAVINGS)),
            totals=dict(marker=dict(color=COLOR_PURPLE)),
            connector=dict(line=dict(color="rgba(255,255,255,0.25)", width=1,
                                     dash="dot")),
            text=labels,
            textposition="outside",
            cliponaxis=False,
            # Variance can be negative, so the hover uses preformatted text
            customdata=labels,
            hovertemplate="%{x}<br>סטייה: %{customdata}<extra></extra>",
        ))
        # Pad the y-range so outside labels are never clipped
        running = pd.Series(values[:-1]).cumsum()
        low = min(running.min(), total_variance, 0)
        high = max(running.max(), total_variance, 0)
        pad = (high - low) * 0.18 or 1
        waterfall.update_layout(showlegend=False)
        waterfall.update_yaxes(title="סטייה (₪)", gridcolor=COLOR_GRID,
                               zeroline=True, zerolinecolor=COLOR_MUTED,
                               tickformat=",.0f", side="right",
                               range=[low - pad, high + pad])
        # RTL reading order: the bridge starts on the right, total on the left
        waterfall.update_xaxes(autorange="reversed")
        st.plotly_chart(style_figure(waterfall, 400), width="stretch",
                        config=PLOTLY_CONFIG)


def mini_kpi_row(budget: float, actual: float, variance: float,
                 variance_pct: float) -> str:
    """HTML for a compact row of budget / actual / variance KPI cards."""
    color = variance_class(variance)
    cards = [
        ("תקציב", ltr(fmt_ils(budget)), ""),
        ("ביצוע", ltr(fmt_ils(actual)), ""),
        ("סטייה", ltr(fmt_ils(variance, signed=True)),
         f'<div class="kpi-sub {color}">{ltr(fmt_pct(variance_pct))}</div>'),
    ]
    items = "".join(
        f'<div class="kpi-mini"><div class="kpi-label">{name}</div>'
        f'<div class="kpi-mini-value {color if name == "סטייה" else ""}">{value}</div>'
        f'{extra}</div>'
        for name, value, extra in cards
    )
    return f'<div class="kpi-mini-row">{items}</div>'


def render_cost_center_analysis(table: pd.DataFrame, cc_summary: pd.DataFrame,
                                period: str, month: str,
                                label: str) -> tuple[str, pd.DataFrame]:
    """
    Drill-down level 2: KPIs and category mix of one cost center.

    Returns the selected cost center and its category summary, which is
    sorted by variance (largest overspend first) for level 3 defaults.
    """
    with st.container(key="card_level2"):
        st.markdown(
            f'<div class="section-title">רמה 2 · ניתוח מרכז עלות</div>'
            f'<div class="section-caption">{label} · ברירת המחדל: המחלקה עם '
            f'החריגה הגדולה ביותר</div>',
            unsafe_allow_html=True,
        )
        # cc_summary is sorted by variance, so the first option is the
        # cost center with the largest overspend
        options = cc_summary["Cost_Center"].tolist()
        cost_center = st.selectbox("בחר מרכז עלות לחקירה", options,
                                   format_func=cc_label, key="cost_center")
        cc_row = cc_summary.set_index("Cost_Center").loc[cost_center]
        categories = de.summarize_by_category(table, cost_center, period, month)

        # First column renders on the right (RTL): KPIs + category table
        right, left = st.columns([1.25, 1])
        right.markdown(
            mini_kpi_row(cc_row["Budget_Amount"], cc_row["Actual_Amount"],
                         cc_row["Variance"], cc_row["Variance_Pct"]),
            unsafe_allow_html=True,
        )
        donut = go.Figure(go.Pie(
            labels=categories["Expense_Category"].map(category_label),
            values=categories["Actual_Amount"],
            hole=0.58,
            sort=True,
            direction="clockwise",
            # Slice borders in the card color create clean gaps on dark
            marker=dict(colors=NEON_SEQUENCE, line=dict(color=COLOR_SURFACE, width=3)),
            textinfo="percent",
            textposition="inside",
            insidetextfont=dict(color="#ffffff"),
            hovertemplate=(f"%{{label}}<br>ביצוע: {hover_ils('%{value:,.0f}')}"
                           "<br>%{percent}<extra></extra>"),
        ))
        donut.update_layout(
            title=f"תמהיל ביצוע · {cc_label(cost_center)}",
            # Hide labels of slices too small to fit them
            uniformtext=dict(minsize=11, mode="hide"),
            legend=dict(orientation="h", x=0.5, xanchor="center", y=-0.05,
                        yanchor="top"),
            annotations=[dict(text=f"<b>{plot_ils(categories['Actual_Amount'].sum())}</b>"
                                   "<br>סך ביצוע",
                              showarrow=False, font=dict(size=14))],
        )
        left.plotly_chart(style_figure(donut, 430), width="stretch",
                          config=PLOTLY_CONFIG)

        header = ("<tr><th>קטגוריה</th><th>תקציב</th><th>ביצוע</th>"
                  "<th>סטייה</th><th>סטייה %</th><th>סטטוס</th></tr>")
        rows = []
        for row in categories.itertuples(index=False):
            css = {de.STATUS_OVERSPEND: "cell-red",
                   de.STATUS_SAVINGS: "cell-green"}.get(row.Status, "")
            rows.append(
                f'<tr><td>{html.escape(category_label(row.Expense_Category))}</td>'
                f'<td class="num">{ltr(fmt_ils(row.Budget_Amount))}</td>'
                f'<td class="num">{ltr(fmt_ils(row.Actual_Amount))}</td>'
                f'<td class="num {css}">{ltr(fmt_ils(row.Variance, signed=True))}</td>'
                f'<td class="num {css}">{ltr(fmt_pct(row.Variance_Pct))}</td>'
                f'<td>{STATUS_ICON.get(row.Status, "")}</td></tr>'
            )
        right.markdown(
            f'<div class="section-caption" style="margin-top:1rem">פירוק לפי '
            f'קטגוריה · ממוין לפי גודל הסטייה</div>'
            f'<table class="fin-table">{header}{"".join(rows)}</table>',
            unsafe_allow_html=True,
        )
        # MoM slicer: full card width below the donut and category table
        render_monthly_trend(table, cost_center, period, month)
    return cost_center, categories


def trend_diagnosis(overspend_months: int, total_months: int) -> str:
    """Classify a monthly overspend pattern as isolated or recurring."""
    if overspend_months == 0:
        return f"אין חודשים בחריגה מהותית מתוך {total_months}"
    if overspend_months == 1:
        return f"חריגה נקודתית: חודש אחד מתוך {total_months}"
    if overspend_months == 2:
        return f"חריגות חוזרות: 2 חודשים מתוך {total_months}"
    return f"דפוס מתמשך: {overspend_months} חודשים מתוך {total_months}"


def render_monthly_trend(table: pd.DataFrame, cost_center: str, period: str,
                         month: str) -> None:
    """
    MoM volatility slicer: monthly actuals vs. budget of one cost center.

    Materially overspent months get large red markers, so a one-off spike
    is easy to tell apart from a consistent burn-rate problem.
    """
    trend = de.summarize_monthly_trend(table, cost_center)
    months = [MONTH_NAMES_HE[int(m[-2:])] for m in trend["Month"]]
    is_over = (trend["Status"] == de.STATUS_OVERSPEND).tolist()
    hover_data = [
        [plot_ils(a), plot_ils(b), plot_ils(v, signed=True)]
        for a, b, v in zip(trend["Actual_Amount"], trend["Budget_Amount"],
                           trend["Variance"])
    ]

    fig = go.Figure([
        # Wide translucent underlay = neon glow effect
        go.Scatter(x=months, y=trend["Actual_Amount"], mode="lines",
                   line=dict(color="rgba(34, 211, 238, 0.18)", width=12,
                             shape="linear"),
                   hoverinfo="skip", showlegend=False),
        go.Scatter(x=months, y=trend["Budget_Amount"], name="תקציב",
                   mode="lines", hoverinfo="skip",
                   line=dict(color="rgba(255, 255, 255, 0.4)", width=1.5,
                             dash="dash")),
        go.Scatter(x=months, y=trend["Actual_Amount"], name="ביצוע",
                   mode="lines+markers",
                   line=dict(color=COLOR_CYAN, width=3, shape="linear"),
                   marker=dict(size=[13 if o else 7 for o in is_over],
                               color=[COLOR_OVERSPEND if o else COLOR_CYAN
                                      for o in is_over],
                               line=dict(color=COLOR_SURFACE, width=2)),
                   customdata=hover_data,
                   hovertemplate=("%{x}<br>ביצוע: %{customdata[0]}"
                                  "<br>תקציב: %{customdata[1]}"
                                  "<br>סטייה: %{customdata[2]}<extra></extra>")),
    ])
    # Mark the month selected in the sidebar when viewing a single month
    if period == de.PERIOD_MTD and month in trend["Month"].values:
        idx = trend["Month"].tolist().index(month)
        fig.add_vrect(x0=idx - 0.5, x1=idx + 0.5, line_width=0,
                      fillcolor="rgba(168, 85, 247, 0.14)")
    fig.update_layout(
        title="מגמה חודשית · ביצוע מול תקציב",
        legend=dict(orientation="h", x=0, xanchor="left", y=1.12),
    )
    fig.update_yaxes(tickformat=",.0f", gridcolor=COLOR_GRID, side="right")
    # RTL reading order: January on the right
    fig.update_xaxes(autorange="reversed", showgrid=False)
    # Keep edge markers (first/last month) from being clipped
    fig.update_traces(cliponaxis=False)
    st.plotly_chart(style_figure(fig, 290), width="stretch", config=PLOTLY_CONFIG)

    over_count = sum(is_over)
    css = "cell-red" if over_count else "cell-green"
    st.markdown(
        f'<div class="section-caption">🔴 = חודש בחריגה מהותית · '
        f'<span class="{css}">{trend_diagnosis(over_count, len(trend))}</span>'
        f'</div>',
        unsafe_allow_html=True,
    )


PARETO_COLORS = ["#ec4899", "#d946ef", "#c026d3", "#a855f7", "#8b5cf6"]


def render_vendor_pareto(entries: pd.DataFrame, category: str) -> None:
    """Pareto view: top 5 vendors by spend in the selected category."""
    vendors = de.top_vendors(entries, n=5)
    if vendors.empty:
        return
    top_share = vendors["Cumulative_Pct"].iloc[-1]
    labels = [f"{plot_ils(a)}  ·  {LRI}{s:.0%}{PDI}"
              for a, s in zip(vendors["Actual_Amount"], vendors["Share_Pct"])]

    fig = go.Figure(go.Bar(
        x=vendors["Actual_Amount"],
        y=vendors["Vendor_Name"],
        orientation="h",
        marker=dict(color=PARETO_COLORS[:len(vendors)],
                    line=dict(color="rgba(255, 255, 255, 0.15)", width=1)),
        text=labels,
        textposition="outside",
        cliponaxis=False,
        customdata=[[plot_ils(a), c] for a, c in
                    zip(vendors["Actual_Amount"], vendors["Entry_Count"])],
        hovertemplate=("%{y}<br>הוצאה: %{customdata[0]}"
                       "<br>%{customdata[1]} תנועות<extra></extra>"),
    ))
    # No digits at the start of the title: Plotly's LTR SVG text would
    # move a leading number to the end of a Hebrew line
    fig.update_layout(title=f"הספקים המובילים לפי היקף הוצאה · "
                            f"{category_label(category)}", bargap=0.35)
    # Bars grow right-to-left (RTL); extra range leaves room for the labels
    fig.update_xaxes(range=[vendors["Actual_Amount"].max() * 1.6, 0],
                     showgrid=False, showticklabels=False, zeroline=False)
    fig.update_yaxes(autorange="reversed", side="right", ticklabelstandoff=10)
    st.plotly_chart(style_figure(fig, 90 + 46 * len(vendors)), width="stretch",
                    config=PLOTLY_CONFIG)
    total_vendors = entries["Vendor_Name"].nunique()
    if total_vendors > len(vendors):
        concentration = (f'{len(vendors)} הספקים המובילים מרכזים '
                         f'<b>{ltr(f"{top_share:.0%}")}</b> מההוצאה בקטגוריה '
                         f'(מתוך {total_vendors} ספקים)')
    else:
        # With 5 vendors or fewer the "top 5" always covers 100%
        concentration = f'כל ההוצאה בקטגוריה מתחלקת בין {total_vendors} ספקים'
    st.markdown(
        f'<div class="section-caption">ריכוזיות ספקים: {concentration}</div>',
        unsafe_allow_html=True,
    )


def render_gl_entries(actuals: pd.DataFrame, cost_center: str,
                      categories: pd.DataFrame, period: str, month: str,
                      label: str) -> None:
    """Drill-down level 3: GL journal entries of one cost center + category."""
    with st.container(key="card_level3"):
        st.markdown(
            f'<div class="section-title">רמה 3 · פקודות יומן (GL) · '
            f'{cc_label(cost_center)}</div>'
            f'<div class="section-caption">ברירת המחדל: הקטגוריה עם החריגה '
            f'הגדולה ביותר במחלקה</div>',
            unsafe_allow_html=True,
        )
        # categories is sorted by variance: first option = biggest overspend.
        # The key includes the cost center so the choice resets on change.
        category = st.selectbox(
            "בחר קטגוריית הוצאה",
            categories["Expense_Category"].tolist(),
            format_func=category_label,
            # Key includes the cost behavior too: switching the slicer can
            # remove the previously selected category from the options
            key=f"gl_category_{cost_center}_{st.session_state.get('cost_behavior')}",
        )
        cat_row = categories.set_index("Expense_Category").loc[category]
        st.markdown(
            mini_kpi_row(cat_row["Budget_Amount"], cat_row["Actual_Amount"],
                         cat_row["Variance"], cat_row["Variance_Pct"]),
            unsafe_allow_html=True,
        )

        entries = de.get_gl_entries(actuals, cost_center, category, period, month)
        # Pareto of vendors, computed from the same filtered entries as the table
        render_vendor_pareto(entries, category)
        vendor_count = entries["Vendor_Name"].nunique()
        st.markdown(
            f'<div class="section-caption" style="margin-top:0.75rem">{label} · '
            f'{len(entries):,} תנועות · {vendor_count} ספקים · '
            f'ממוין מהסכום הגבוה לנמוך</div>',
            unsafe_allow_html=True,
        )

        display = pd.DataFrame({
            "מזהה תנועה": entries["Transaction_ID"],
            "תאריך": entries["Date"].dt.strftime("%d/%m/%Y"),
            "ספק": entries["Vendor_Name"],
            "תיאור": entries["Description"],
            "סכום (₪)": entries["Actual_Amount"],
        })
        # The data grid is LTR-only: reverse columns so the ID is rightmost
        display = display[display.columns[::-1]]
        styled = (
            display.style
            .format({"סכום (₪)": "{:,.2f}"})
            .set_properties(subset=["סכום (₪)"], **{"font-weight": "600"})
        )
        st.dataframe(styled, width="stretch", hide_index=True, height=420)

        st.download_button(
            "⬇️ הורדת התנועות (CSV)",
            data=to_excel_csv(entries),
            file_name=(f"gl_{cost_center}_{category}_{period}_{month}.csv"
                       .replace(" ", "_").replace("&", "and")),
            mime="text/csv",
        )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def compute_totals(cc_summary: pd.DataFrame) -> dict:
    """Aggregate period totals for the banner and KPI cards."""
    budget = cc_summary["Budget_Amount"].sum()
    actual = cc_summary["Actual_Amount"].sum()
    variance = actual - budget
    return {
        "budget": budget,
        "actual": actual,
        "variance": variance,
        "variance_pct": variance / budget if budget else float("nan"),
        "entries": int(cc_summary["Entry_Count"].sum()),
    }


def main() -> None:
    st.set_page_config(page_title="בקרת תקציב - Drill-Down", page_icon="📊",
                       layout="wide")
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

    all_actuals, all_table = load_data()
    last_closed = de.get_last_closed_month(all_actuals)
    closed_months = sorted(all_table.loc[all_table["Is_Closed"], "Month"].unique())

    period, month, behavior = render_sidebar(closed_months, last_closed)
    label = period_label(period, month)

    # Global cost-behavior slicer: filter once here, so every section below
    # (KPIs, flags, waterfall, trend, Pareto, GL) recalculates on the subset
    actuals = de.filter_cost_behavior(all_actuals, behavior)
    table = de.filter_cost_behavior(all_table, behavior)
    if behavior is not None:
        label = f"{label} · הוצאות {BEHAVIOR_HE[behavior]} בלבד"

    cc_summary = de.summarize_by_cost_center(table, period, month)
    totals = compute_totals(cc_summary)
    full_year = de.build_full_year_view(table)
    run_rate = de.run_rate_forecast(table, period, month)
    period_cells = de.filter_period(table.loc[table["Is_Closed"]], period, month)
    flags = de.top_variances(period_cells, n=10)
    flag_count = int((period_cells["Status"] == de.STATUS_OVERSPEND).sum())

    st.markdown(
        f'<div class="page-title">בקרת תקציב <span class="gradient-text">מול ביצוע'
        f'</span></div>'
        f'<div class="page-subtitle">שנת תקציב {last_closed[:4]} · '
        f'נתונים סגורים עד {month_label(last_closed)} · תצוגה: {label}</div>',
        unsafe_allow_html=True,
    )
    render_alert_banner(totals, flag_count, label)
    render_kpis(totals, full_year, run_rate, label, last_closed)
    st.write("")
    render_red_flags(flags, label)
    st.write("")
    render_variance_waterfall(cc_summary, label)
    st.write("")
    cost_center, categories = render_cost_center_analysis(
        table, cc_summary, period, month, label)
    st.write("")
    render_gl_entries(actuals, cost_center, categories, period, month, label)


if __name__ == "__main__":
    main()
