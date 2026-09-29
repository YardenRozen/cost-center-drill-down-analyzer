"""
Data engine for the Cost-Center Drill-Down Analyzer.

Pure Pandas business logic, with no UI dependencies:
    1. Load and validate the budget and GL actuals files.
    2. Merge budget with aggregated actuals (outer merge, so unbudgeted
       spend and unused budget lines are never dropped).
    3. Compute variances and classify them by a dual materiality threshold.
    4. Provide period views (MTD / YTD / full year with forecast) and the
       drill-down path: Cost Center -> Expense Category -> GL entries.

Conventions:
    - Variance = Actual - Budget  (positive = overspend, negative = savings)
    - A variance is material only if it exceeds BOTH the percentage and the
      absolute threshold.
    - Year-end forecast = YTD actuals + budget of the months not yet closed.
    - Month keys are "YYYY-MM" strings, so they sort and compare correctly.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DATA_DIR = Path(__file__).resolve().parent / "data"
BUDGET_FILE = DATA_DIR / "budget_2026.csv"
ACTUALS_FILE = DATA_DIR / "actuals_gl_2026.csv"

# Dual materiality threshold: both conditions must hold
MATERIALITY_PCT = 0.05
MATERIALITY_ABS = 5_000.0

STATUS_OVERSPEND = "Overspend"
STATUS_SAVINGS = "Savings"
STATUS_ON_TRACK = "On Track"
STATUS_OPEN = "Open"  # month not closed yet, variance not applicable

MERGE_MATCHED = "Matched"
MERGE_UNBUDGETED = "Unbudgeted"   # actuals with no budget line
MERGE_NO_ACTUALS = "No Actuals"   # budget line with no postings

PERIOD_MTD = "MTD"
PERIOD_YTD = "YTD"

KEYS = ["Month", "Cost_Center", "Expense_Category"]

BUDGET_COLUMNS = ["Month", "Cost_Center", "Expense_Category", "Budget_Amount"]
ACTUALS_COLUMNS = [
    "Transaction_ID", "Date", "Cost_Center", "Expense_Category",
    "Vendor_Name", "Description", "Actual_Amount",
]


# ---------------------------------------------------------------------------
# Loading and validation
# ---------------------------------------------------------------------------

def _validate_columns(df: pd.DataFrame, required: list[str], name: str) -> None:
    """Raise a clear error if any required column is missing."""
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise ValueError(f"{name} is missing required columns: {missing}")


def load_budget(path: Path = BUDGET_FILE) -> pd.DataFrame:
    """Load and validate the monthly budget table."""
    budget = pd.read_csv(path, dtype={"Month": str})
    _validate_columns(budget, BUDGET_COLUMNS, "Budget file")
    budget["Budget_Amount"] = pd.to_numeric(budget["Budget_Amount"], errors="raise")
    # Collapse potential duplicate budget lines into one row per key
    return budget.groupby(KEYS, as_index=False)["Budget_Amount"].sum()


def load_actuals(path: Path = ACTUALS_FILE) -> pd.DataFrame:
    """Load and validate the GL actuals, adding a Month key."""
    actuals = pd.read_csv(path)
    _validate_columns(actuals, ACTUALS_COLUMNS, "Actuals file")
    actuals["Date"] = pd.to_datetime(actuals["Date"], errors="raise")
    actuals["Actual_Amount"] = pd.to_numeric(actuals["Actual_Amount"], errors="raise")
    actuals["Month"] = actuals["Date"].dt.strftime("%Y-%m")
    return actuals


def get_last_closed_month(actuals: pd.DataFrame) -> str:
    """Return the latest month with GL postings (the last closed period)."""
    return str(actuals["Month"].max())


# ---------------------------------------------------------------------------
# Merge and variance calculation
# ---------------------------------------------------------------------------

def aggregate_actuals(actuals: pd.DataFrame) -> pd.DataFrame:
    """Aggregate GL entries to Month x Cost Center x Expense Category."""
    return (
        actuals.groupby(KEYS, as_index=False)
        .agg(Actual_Amount=("Actual_Amount", "sum"),
             Entry_Count=("Transaction_ID", "count"))
    )


def classify_variance(variance: pd.Series, budget: pd.Series) -> pd.Series:
    """
    Classify variances using the dual materiality threshold.

    Unbudgeted spend (budget = 0) is treated as an infinite percentage
    deviation, so it is flagged whenever it exceeds the absolute threshold.
    """
    with np.errstate(divide="ignore", invalid="ignore"):
        pct = np.where(budget != 0, variance / budget, np.sign(variance) * np.inf)
    overspend = (variance > MATERIALITY_ABS) & (pct > MATERIALITY_PCT)
    savings = (variance < -MATERIALITY_ABS) & (pct < -MATERIALITY_PCT)
    status = np.select([overspend, savings], [STATUS_OVERSPEND, STATUS_SAVINGS],
                       default=STATUS_ON_TRACK)
    return pd.Series(status, index=variance.index)


def add_variance_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """Add Variance, Variance_Pct and Status columns to an aggregated table."""
    df = df.copy()
    df["Variance"] = df["Actual_Amount"] - df["Budget_Amount"]
    df["Variance_Pct"] = np.where(
        df["Budget_Amount"] != 0, df["Variance"] / df["Budget_Amount"], np.nan)
    df["Status"] = classify_variance(df["Variance"], df["Budget_Amount"])
    return df


def build_variance_table(
    budget: pd.DataFrame,
    actuals: pd.DataFrame,
    last_closed_month: str | None = None,
) -> pd.DataFrame:
    """
    Build the base variance table at Month x Cost Center x Category level.

    Uses an outer merge so both unbudgeted spend and budget lines without
    postings are kept. Months after the last closed month are flagged as
    open: their actuals are zero by definition and no variance is reported.
    """
    if last_closed_month is None:
        last_closed_month = get_last_closed_month(actuals)

    merged = budget.merge(aggregate_actuals(actuals), on=KEYS,
                          how="outer", indicator=True)
    merged["Merge_Flag"] = merged["_merge"].map({
        "both": MERGE_MATCHED,
        "left_only": MERGE_NO_ACTUALS,
        "right_only": MERGE_UNBUDGETED,
    }).astype(str)
    merged = merged.drop(columns="_merge")

    merged["Budget_Amount"] = merged["Budget_Amount"].fillna(0.0)
    merged["Actual_Amount"] = merged["Actual_Amount"].fillna(0.0)
    merged["Entry_Count"] = merged["Entry_Count"].fillna(0).astype(int)
    merged["Is_Closed"] = merged["Month"] <= last_closed_month

    merged = add_variance_metrics(merged)
    # Variance is meaningless for periods that have not been closed yet
    open_rows = ~merged["Is_Closed"]
    merged.loc[open_rows, ["Variance", "Variance_Pct"]] = np.nan
    merged.loc[open_rows, "Status"] = STATUS_OPEN

    return merged.sort_values(KEYS).reset_index(drop=True)


# ---------------------------------------------------------------------------
# Period views
# ---------------------------------------------------------------------------

def filter_period(table: pd.DataFrame, period: str, month: str) -> pd.DataFrame:
    """
    Filter a Month-level table to a reporting period.

    MTD: only the selected month. YTD: from January up to the selected month.
    """
    if period == PERIOD_MTD:
        mask = table["Month"] == month
    elif period == PERIOD_YTD:
        year_start = f"{month[:4]}-01"
        mask = table["Month"].between(year_start, month)
    else:
        raise ValueError(f"Unknown period '{period}', expected MTD or YTD")
    return table.loc[mask]


def summarize(
    table: pd.DataFrame,
    group_by: list[str],
    period: str,
    month: str,
) -> pd.DataFrame:
    """
    Aggregate the variance table for a period and grouping level.

    Variance metrics are recomputed after aggregation (percentages are never
    summed), so each level is classified on its own totals.
    """
    closed = table.loc[table["Is_Closed"]]
    subset = filter_period(closed, period, month)
    grouped = (
        subset.groupby(group_by, as_index=False)
        .agg(Budget_Amount=("Budget_Amount", "sum"),
             Actual_Amount=("Actual_Amount", "sum"),
             Entry_Count=("Entry_Count", "sum"))
    )
    grouped = add_variance_metrics(grouped)
    return grouped.sort_values("Variance", ascending=False).reset_index(drop=True)


def summarize_by_cost_center(table: pd.DataFrame, period: str,
                             month: str) -> pd.DataFrame:
    """Drill-down level 1: Budget vs. Actual per cost center."""
    return summarize(table, ["Cost_Center"], period, month)


def summarize_by_category(table: pd.DataFrame, cost_center: str, period: str,
                          month: str) -> pd.DataFrame:
    """Drill-down level 2: Budget vs. Actual per category of one cost center."""
    subset = table.loc[table["Cost_Center"] == cost_center]
    return summarize(subset, ["Expense_Category"], period, month)


def summarize_monthly_trend(table: pd.DataFrame,
                            cost_center: str | None = None) -> pd.DataFrame:
    """Monthly Budget vs. Actual for all closed months (optional filter)."""
    subset = table if cost_center is None else table.loc[
        table["Cost_Center"] == cost_center]
    last_month = subset.loc[subset["Is_Closed"], "Month"].max()
    return summarize(subset, ["Month"], PERIOD_YTD, last_month).sort_values(
        "Month").reset_index(drop=True)


def build_full_year_view(table: pd.DataFrame,
                         group_by: list[str] | None = None) -> pd.DataFrame:
    """
    Full-year view with a year-end forecast.

    Forecast = YTD actuals + budget of open (not yet closed) months.
    Forecast_Variance = Forecast - Annual_Budget (positive = expected overrun).
    """
    group_by = group_by or ["Cost_Center"]
    df = table.assign(
        YTD_Budget=np.where(table["Is_Closed"], table["Budget_Amount"], 0.0),
        YTD_Actual=np.where(table["Is_Closed"], table["Actual_Amount"], 0.0),
        Remaining_Budget=np.where(table["Is_Closed"], 0.0, table["Budget_Amount"]),
    )
    view = (
        df.groupby(group_by, as_index=False)
        .agg(Annual_Budget=("Budget_Amount", "sum"),
             YTD_Budget=("YTD_Budget", "sum"),
             YTD_Actual=("YTD_Actual", "sum"),
             Remaining_Budget=("Remaining_Budget", "sum"))
    )
    view["Available_Budget"] = view["Annual_Budget"] - view["YTD_Actual"]
    view["Budget_Utilization_Pct"] = np.where(
        view["Annual_Budget"] != 0, view["YTD_Actual"] / view["Annual_Budget"], np.nan)
    view["Forecast"] = view["YTD_Actual"] + view["Remaining_Budget"]
    view["Forecast_Variance"] = view["Forecast"] - view["Annual_Budget"]
    view["Forecast_Status"] = classify_variance(
        view["Forecast_Variance"], view["Annual_Budget"])
    return view.sort_values("Forecast_Variance", ascending=False).reset_index(drop=True)


# ---------------------------------------------------------------------------
# Drill-down to GL and exception reporting
# ---------------------------------------------------------------------------

def get_gl_entries(
    actuals: pd.DataFrame,
    cost_center: str,
    category: str | None = None,
    period: str = PERIOD_YTD,
    month: str | None = None,
) -> pd.DataFrame:
    """Drill-down level 3: the GL journal entries behind a variance."""
    month = month or get_last_closed_month(actuals)
    subset = actuals.loc[actuals["Cost_Center"] == cost_center]
    if category is not None:
        subset = subset.loc[subset["Expense_Category"] == category]
    subset = filter_period(subset, period, month)
    return (
        subset[ACTUALS_COLUMNS]
        .sort_values("Actual_Amount", ascending=False)
        .reset_index(drop=True)
    )


def top_variances(
    table: pd.DataFrame,
    n: int = 10,
    status: str = STATUS_OVERSPEND,
) -> pd.DataFrame:
    """
    Return the largest material variances at monthly cell level.

    For overspend the biggest positive variances come first; for savings the
    most negative ones.
    """
    flagged = table.loc[table["Is_Closed"] & (table["Status"] == status)]
    ascending = status == STATUS_SAVINGS
    columns = KEYS + ["Budget_Amount", "Actual_Amount", "Variance",
                      "Variance_Pct", "Entry_Count", "Merge_Flag"]
    return (
        flagged.sort_values("Variance", ascending=ascending)
        .head(n)[columns]
        .reset_index(drop=True)
    )


def reconcile(actuals: pd.DataFrame, table: pd.DataFrame) -> dict[str, float | int]:
    """
    Data-quality checks: GL totals must tie to the variance table, and
    any unbudgeted spend or closed budget lines without postings are counted.
    """
    gl_total = round(float(actuals["Actual_Amount"].sum()), 2)
    table_total = round(float(table["Actual_Amount"].sum()), 2)
    closed = table["Is_Closed"]
    return {
        "gl_total": gl_total,
        "table_total": table_total,
        "difference": round(gl_total - table_total, 2),
        "gl_entry_count": int(len(actuals)),
        "unbudgeted_lines": int((table["Merge_Flag"] == MERGE_UNBUDGETED).sum()),
        "closed_lines_without_actuals": int(
            (closed & (table["Merge_Flag"] == MERGE_NO_ACTUALS)).sum()),
    }


def load_all() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Convenience loader: returns (budget, actuals, variance_table)."""
    budget = load_budget()
    actuals = load_actuals()
    return budget, actuals, build_variance_table(budget, actuals)


# ---------------------------------------------------------------------------
# Quick smoke run
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    pd.set_option("display.width", 200)
    pd.set_option("display.float_format", "{:,.2f}".format)

    _, gl, variance_table = load_all()
    last_month = get_last_closed_month(gl)

    print("Reconciliation:", reconcile(gl, variance_table))
    print(f"\nTop overspends (monthly cells, closed through {last_month}):")
    print(top_variances(variance_table).to_string(index=False))
    print(f"\nCost centers - YTD through {last_month}:")
    print(summarize_by_cost_center(variance_table, PERIOD_YTD, last_month)
          .to_string(index=False))
    print("\nFull-year view with forecast:")
    print(build_full_year_view(variance_table).to_string(index=False))
