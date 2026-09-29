"""
Streamlit UI for the Cost-Center Drill-Down Analyzer.

Presentation layer only: all business logic lives in data_engine.py.
User-facing text is Hebrew (RTL); code, identifiers and data stay English.

Run with:  streamlit run app.py
"""

from __future__ import annotations

import html

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import data_engine as de

# ---------------------------------------------------------------------------
# Design tokens
# ---------------------------------------------------------------------------

COLOR_SIDEBAR = "#009688"
COLOR_SAVINGS = "#2e7d32"
COLOR_OVERSPEND = "#d32f2f"
COLOR_BACKGROUND = "#f5f7f8"
COLOR_TEXT = "#1f2d3d"
COLOR_MUTED = "#6b7c8f"
COLOR_BLUE_LIGHT = "#64b5f6"
COLOR_BLUE_DARK = "#0d47a1"
BLUE_SEQUENCE = ["#0d47a1", "#1565c0", "#1e88e5", "#42a5f5",
                 "#64b5f6", "#90caf9", "#bbdefb", "#e3f2fd"]
FONT_FAMILY = "Heebo, 'Segoe UI', Arial, sans-serif"

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

# ---------------------------------------------------------------------------
# Global CSS
# ---------------------------------------------------------------------------

CUSTOM_CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Heebo:wght@300;400;500;700;800&display=swap');

html, body, .stApp, .stMarkdown, button, input, select, textarea {{
    font-family: {FONT_FAMILY};
}}
.stApp {{ background-color: {COLOR_BACKGROUND}; }}
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

/* Sidebar (now on the right): move its border to the inner (left) edge */
[data-testid="stSidebar"] {{
    background-color: {COLOR_SIDEBAR};
    border-left: 1px solid rgba(0,0,0,0.08);
    border-right: none;
}}
[data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3, [data-testid="stSidebar"] p,
[data-testid="stSidebar"] label, [data-testid="stSidebar"] span,
[data-testid="stSidebar"] div {{
    color: #ffffff;
}}
[data-testid="stSidebar"] [data-baseweb="select"] * {{ color: {COLOR_TEXT}; }}
[data-testid="stSidebar"] hr {{ border-color: rgba(255,255,255,0.3); }}
.sidebar-logo {{
    font-size: 1.35rem; font-weight: 800; line-height: 1.3;
    padding: 0.5rem 0 0.25rem 0;
}}
.sidebar-tagline {{ font-size: 0.85rem; opacity: 0.85; }}
.sidebar-info {{
    background: rgba(255,255,255,0.12); border-radius: 10px;
    padding: 0.75rem 0.9rem; font-size: 0.85rem; line-height: 1.7;
}}

/* Cards: any container whose key starts with "card" */
div[class*="st-key-card"] {{
    background: #ffffff;
    border-radius: 16px;
    box-shadow: 0 2px 14px rgba(16, 42, 67, 0.08);
    border: 1px solid #e6ecef;
    padding: 1.25rem 1.5rem;
}}

/* Page header */
.page-title {{ font-size: 2rem; font-weight: 800; color: {COLOR_TEXT}; margin: 0; }}
.page-subtitle {{ color: {COLOR_MUTED}; font-size: 1rem; margin-bottom: 1rem; }}
.section-title {{
    font-size: 1.2rem; font-weight: 700; color: {COLOR_TEXT};
    margin: 0 0 0.25rem 0;
}}
.section-caption {{ color: {COLOR_MUTED}; font-size: 0.9rem; margin-bottom: 0.75rem; }}

/* Alert banner */
.alert-banner {{
    border-radius: 14px; padding: 1rem 1.25rem; margin-bottom: 1.25rem;
    font-size: 1.02rem; line-height: 1.7; border-right: 6px solid;
}}
.alert-red {{ background: #fdecea; border-color: {COLOR_OVERSPEND}; color: #7f1d1d; }}
.alert-green {{ background: #e8f5e9; border-color: {COLOR_SAVINGS}; color: #1b4d20; }}
.alert-banner b {{ font-weight: 700; }}

/* KPI cards */
.kpi-card {{
    background: #ffffff; border-radius: 16px; padding: 1.1rem 1.3rem;
    box-shadow: 0 2px 14px rgba(16, 42, 67, 0.08);
    border: 1px solid #e6ecef; border-top: 4px solid {COLOR_BLUE_DARK};
    height: 100%;
}}
.kpi-label {{ color: {COLOR_MUTED}; font-size: 0.95rem; font-weight: 500; }}
.kpi-value {{ font-size: 1.85rem; font-weight: 800; color: {COLOR_TEXT}; margin: 0.2rem 0; }}
.kpi-sub {{ color: {COLOR_MUTED}; font-size: 0.85rem; }}
/* Compact KPI row used inside drill-down cards */
.kpi-mini-row {{ display: flex; gap: 0.75rem; }}
.kpi-mini {{
    flex: 1; background: {COLOR_BACKGROUND}; border: 1px solid #e6ecef;
    border-radius: 12px; padding: 0.7rem 0.9rem;
}}
.kpi-mini-value {{ font-size: 1.3rem; font-weight: 800; color: {COLOR_TEXT}; }}
.kpi-red {{ color: {COLOR_OVERSPEND} !important; }}
.kpi-green {{ color: {COLOR_SAVINGS} !important; }}

/* HTML tables (red flags, category breakdown) */
.fin-table {{ width: 100%; border-collapse: collapse; font-size: 0.93rem; direction: rtl; }}
.fin-table th {{
    text-align: right; color: {COLOR_MUTED}; font-weight: 600;
    border-bottom: 2px solid #e6ecef; padding: 0.55rem 0.6rem;
}}
.fin-table td {{ padding: 0.55rem 0.6rem; border-bottom: 1px solid #f0f3f5; color: {COLOR_TEXT}; }}
.fin-table tr:hover td {{ background: #f8fafb; }}
.fin-table .num {{ white-space: nowrap; }}
.cell-red {{ color: {COLOR_OVERSPEND}; font-weight: 700; }}
.cell-green {{ color: {COLOR_SAVINGS}; font-weight: 700; }}
.rank {{ color: {COLOR_MUTED}; font-weight: 600; }}
.dot {{ display: inline-block; width: 11px; height: 11px; border-radius: 50%; }}
.dot-red {{ background: {COLOR_OVERSPEND}; }}
.dot-green {{ background: {COLOR_SAVINGS}; }}
.dot-gray {{ background: #b0bec5; }}

/* Hide the floating Deploy button that overlaps RTL content */
[data-testid="stAppDeployButton"] {{ display: none; }}
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
    """Apply the shared chart style: transparent background, Heebo font."""
    fig.update_layout(
        height=height,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family=FONT_FAMILY, color=COLOR_TEXT, size=13),
        margin=dict(l=10, r=10, t=40, b=10),
        hoverlabel=dict(font_family=FONT_FAMILY),
    )
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


def render_sidebar(closed_months: list[str], last_closed: str) -> tuple[str, str]:
    """Render the sidebar and return the selected (period, month)."""
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
    return (de.PERIOD_YTD if is_ytd else de.PERIOD_MTD), month


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


def kpi_card(label: str, value: str, sub: str, value_class: str = "") -> str:
    """HTML for a single KPI card."""
    return (f'<div class="kpi-card"><div class="kpi-label">{label}</div>'
            f'<div class="kpi-value {value_class}">{value}</div>'
            f'<div class="kpi-sub">{sub}</div></div>')


def render_kpis(totals: dict, full_year: pd.DataFrame, label: str,
                last_closed: str) -> None:
    """Four KPI cards: budget, actual, variance, year-end forecast."""
    annual_budget = full_year["Annual_Budget"].sum()
    forecast = full_year["Forecast"].sum()
    forecast_var = forecast - annual_budget
    variance = totals["variance"]

    cards = [
        kpi_card("סך תקציב", ltr(fmt_ils(totals["budget"])), label),
        kpi_card("סך ביצוע", ltr(fmt_ils(totals["actual"])),
                 f'{totals["entries"]:,} פקודות יומן'),
        kpi_card("סך סטייה", ltr(fmt_ils(variance, signed=True)),
                 f'{ltr(fmt_pct(totals["variance_pct"]))} מהתקציב · '
                 f'{"חריגה" if variance > 0 else "חיסכון"}',
                 "kpi-red" if variance > 0 else "kpi-green"),
        kpi_card("תחזית סוף שנה", ltr(fmt_ils(forecast)),
                 f'תקציב שנתי {ltr(fmt_ils(annual_budget))} · סטייה צפויה '
                 f'<span class="{variance_class(forecast_var)}">'
                 f'{ltr(fmt_ils(forecast_var, signed=True))}</span>'),
    ]
    for column, card in zip(st.columns(4), cards):
        column.markdown(card, unsafe_allow_html=True)
    st.caption(f"התחזית: ביצוע בפועל עד {month_label(last_closed)} "
               f"+ יתרת התקציב לחודשים שטרם נסגרו.")


def render_red_flags(flags: pd.DataFrame, label: str) -> None:
    """Top material overspends at month x cost center x category level."""
    with st.container(key="card_red_flags"):
        st.markdown(
            f'<div class="section-title">🚩 דגלים אדומים — 10 החריגות המהותיות '
            f'הגדולות</div><div class="section-caption">ברמת חודש × מחלקה × '
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
            totals=dict(marker=dict(color=COLOR_BLUE_DARK)),
            connector=dict(line=dict(color="#b0bec5", width=1, dash="dot")),
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
        waterfall.update_yaxes(title="סטייה (₪)", gridcolor="#eef2f4",
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
            marker=dict(colors=BLUE_SEQUENCE, line=dict(color="#ffffff", width=2)),
            textinfo="percent",
            textposition="inside",
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
    return cost_center, categories


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
            key=f"gl_category_{cost_center}",
        )
        cat_row = categories.set_index("Expense_Category").loc[category]
        st.markdown(
            mini_kpi_row(cat_row["Budget_Amount"], cat_row["Actual_Amount"],
                         cat_row["Variance"], cat_row["Variance_Pct"]),
            unsafe_allow_html=True,
        )

        entries = de.get_gl_entries(actuals, cost_center, category, period, month)
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
            data=entries.to_csv(index=False).encode("utf-8-sig"),
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

    actuals, table = load_data()
    last_closed = de.get_last_closed_month(actuals)
    closed_months = sorted(table.loc[table["Is_Closed"], "Month"].unique())

    period, month = render_sidebar(closed_months, last_closed)
    label = period_label(period, month)

    cc_summary = de.summarize_by_cost_center(table, period, month)
    totals = compute_totals(cc_summary)
    full_year = de.build_full_year_view(table)
    period_cells = de.filter_period(table.loc[table["Is_Closed"]], period, month)
    flags = de.top_variances(period_cells, n=10)
    flag_count = int((period_cells["Status"] == de.STATUS_OVERSPEND).sum())

    st.markdown(
        f'<div class="page-title">בקרת תקציב מול ביצוע</div>'
        f'<div class="page-subtitle">שנת תקציב {last_closed[:4]} · '
        f'נתונים סגורים עד {month_label(last_closed)} · תצוגה: {label}</div>',
        unsafe_allow_html=True,
    )
    render_alert_banner(totals, flag_count, label)
    render_kpis(totals, full_year, label, last_closed)
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
