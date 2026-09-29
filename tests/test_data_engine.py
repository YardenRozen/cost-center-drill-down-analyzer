"""Unit tests for data_engine business logic."""

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import data_engine as de  # noqa: E402


def _make_actuals(rows: list[tuple]) -> pd.DataFrame:
    """Build a minimal actuals frame from (date, cc, category, amount) tuples."""
    df = pd.DataFrame(rows, columns=["Date", "Cost_Center",
                                     "Expense_Category", "Actual_Amount"])
    df["Transaction_ID"] = [f"T{i}" for i in range(len(df))]
    df["Vendor_Name"] = "Vendor"
    df["Description"] = "Desc"
    df["Date"] = pd.to_datetime(df["Date"])
    df["Month"] = df["Date"].dt.strftime("%Y-%m")
    return df


@pytest.fixture
def small_case() -> tuple[pd.DataFrame, pd.DataFrame]:
    budget = pd.DataFrame({
        "Month": ["2026-01", "2026-01", "2026-02", "2026-03"],
        "Cost_Center": ["IT", "HR", "IT", "IT"],
        "Expense_Category": ["Travel", "Travel", "Travel", "Travel"],
        "Budget_Amount": [100_000.0, 10_000.0, 100_000.0, 100_000.0],
    })
    actuals = _make_actuals([
        ("2026-01-05", "IT", "Travel", 60_000.0),
        ("2026-01-20", "IT", "Travel", 60_000.0),    # IT Jan: +20k, +20%
        ("2026-01-10", "HR", "Travel", 13_000.0),    # HR Jan: +3k -> below abs
        ("2026-02-10", "IT", "Travel", 80_000.0),    # IT Feb: -20k savings
        ("2026-02-11", "IT", "Consulting", 7_000.0), # unbudgeted
    ])
    return budget, actuals


def test_outer_merge_keeps_unbudgeted_and_open_months(small_case):
    budget, actuals = small_case
    table = de.build_variance_table(budget, actuals)
    unbudgeted = table[table["Merge_Flag"] == de.MERGE_UNBUDGETED]
    assert len(unbudgeted) == 1
    assert unbudgeted.iloc[0]["Status"] == de.STATUS_OVERSPEND
    march = table[table["Month"] == "2026-03"].iloc[0]
    assert not march["Is_Closed"] and march["Status"] == de.STATUS_OPEN


def test_dual_materiality_threshold(small_case):
    budget, actuals = small_case
    table = de.build_variance_table(budget, actuals).set_index(
        ["Month", "Cost_Center", "Expense_Category"])
    assert table.loc[("2026-01", "IT", "Travel"), "Status"] == de.STATUS_OVERSPEND
    # 30% over but only 3,000 ILS -> not material
    assert table.loc[("2026-01", "HR", "Travel"), "Status"] == de.STATUS_ON_TRACK
    assert table.loc[("2026-02", "IT", "Travel"), "Status"] == de.STATUS_SAVINGS


def test_ytd_equals_sum_of_months_and_forecast(small_case):
    budget, actuals = small_case
    table = de.build_variance_table(budget, actuals)
    ytd = de.summarize_by_cost_center(table, de.PERIOD_YTD, "2026-02")
    it_ytd = ytd.set_index("Cost_Center").loc["IT", "Variance"]
    monthly = table[table["Is_Closed"] & (table["Cost_Center"] == "IT")]
    assert it_ytd == pytest.approx(monthly["Variance"].sum())

    full_year = de.build_full_year_view(table).set_index("Cost_Center")
    # IT: YTD actual 207k + open March budget 100k
    assert full_year.loc["IT", "Forecast"] == pytest.approx(307_000.0)


def test_reconciliation_ties_on_generated_data():
    _, actuals, table = de.load_all()
    assert de.reconcile(actuals, table)["difference"] == 0


def test_all_planned_overspend_scenarios_are_flagged():
    from generate_mock_data import OVERSPEND_SCENARIOS

    _, _, table = de.load_all()
    flagged = de.top_variances(table, n=100)
    flagged_keys = {
        (r.Cost_Center, r.Expense_Category, int(r.Month[-2:]))
        for r in flagged.itertuples()
    }
    assert set(OVERSPEND_SCENARIOS) <= flagged_keys
