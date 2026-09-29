"""
Mock data generator for the Cost-Center Drill-Down Analyzer.

Creates two CSV files for fiscal year 2026 under ./data:
    - budget_2026.csv      : full-year monthly budget (Jan-Dec) per cost
                             center and expense category
    - actuals_gl_2026.csv  : General Ledger (GL) journal entries (actual spend)
                             year-to-date only, up to the last closed month
                             (September), enabling YTD vs. full-year analysis

The actuals are built "top-down": for every (month, cost center, category)
cell we first decide a target spend relative to budget (on-budget, savings,
or a deliberate overspend scenario), and then split that target into several
realistic journal entries with vendors, descriptions and posting dates.

All amounts are in ILS. A fixed random seed keeps the output reproducible.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SEED = 42
YEAR = 2026
OUTPUT_DIR = Path(__file__).resolve().parent / "data"
BUDGET_FILE = OUTPUT_DIR / f"budget_{YEAR}.csv"
ACTUALS_FILE = OUTPUT_DIR / f"actuals_gl_{YEAR}.csv"

# Last closed month: actuals are generated only up to (and including) it
LAST_CLOSED_MONTH = 9

# Base monthly budget (ILS) per cost center. Only categories relevant to each
# department are included, reflecting its real cost structure.
BASE_MONTHLY_BUDGET: dict[str, dict[str, int]] = {
    "HR": {
        "Payroll": 185_000,
        "Employee Welfare": 22_000,
        "Consulting": 18_000,
        "Software Licenses": 6_000,
        "Travel": 4_000,
        "Office Supplies": 3_500,
    },
    "IT": {
        "Payroll": 240_000,
        "Software Licenses": 95_000,
        "Cloud Infrastructure": 70_000,
        "Consulting": 30_000,
        "Travel": 5_000,
        "Office Supplies": 4_000,
    },
    "Marketing": {
        "Payroll": 160_000,
        "Advertising": 120_000,
        "Consulting": 35_000,
        "Travel": 18_000,
        "Software Licenses": 12_000,
        "Office Supplies": 3_000,
    },
    "R&D": {
        "Payroll": 520_000,
        "Cloud Infrastructure": 85_000,
        "Software Licenses": 45_000,
        "Consulting": 40_000,
        "Travel": 22_000,
        "Office Supplies": 5_000,
    },
    "Operations": {
        "Payroll": 210_000,
        "Consulting": 25_000,
        "Office Supplies": 15_000,
        "Travel": 12_000,
        "Software Licenses": 8_000,
    },
}

# Planned seasonality multipliers applied to the budget (month -> factor).
# Unlisted months default to 1.0.
BUDGET_SEASONALITY: dict[str, dict[int, float]] = {
    # Campaign peaks: spring launch, back-to-business, Q4 holiday season
    "Advertising": {3: 1.20, 9: 1.15, 11: 1.40, 12: 1.30},
    # Low travel over summer vacation, high around autumn conferences
    "Travel": {7: 0.60, 8: 0.60, 10: 1.30},
    # Holiday gifts: Passover (April) and Rosh Hashanah (September)
    "Employee Welfare": {4: 1.80, 9: 1.80},
}

# Deliberate overspend scenarios: (cost center, category, month) ->
# (overspend ratio above budget, vendor, description of the anomaly entry).
# All scenarios fall within the closed YTD period.
OVERSPEND_SCENARIOS: dict[tuple[str, str, int], tuple[float, str, str]] = {
    ("HR", "Consulting", 2): (
        1.20, "Nisha Recruitment", "Executive search fee - VP Engineering placement"),
    ("IT", "Software Licenses", 3): (
        0.45, "Microsoft", "Unplanned M365 E5 upgrade - true-up for all users"),
    ("Operations", "Travel", 4): (
        0.90, "El Al Israel Airlines", "Emergency supplier site visits - Far East"),
    ("Marketing", "Advertising", 5): (
        0.60, "Meta Platforms", "Unbudgeted product-launch campaign - Israel & EU"),
    ("R&D", "Consulting", 6): (
        0.85, "Deloitte Israel", "Cyber security penetration test - urgent"),
    ("HR", "Payroll", 6): (
        0.12, "Hilan", "Mid-year retention bonus - not in budget"),
    ("IT", "Cloud Infrastructure", 7): (
        0.30, "Amazon Web Services", "EC2 usage spike - untagged dev instances"),
    ("IT", "Cloud Infrastructure", 8): (
        0.35, "Amazon Web Services", "EC2 usage spike - untagged dev instances"),
    ("R&D", "Travel", 9): (
        0.95, "El Al Israel Airlines", "Team flights to AWS re:Invent - business class"),
}

# Probability that a non-scenario cell ends up with meaningful savings.
SAVINGS_PROBABILITY = 0.20

# Vendor catalog per expense category: each vendor maps to the descriptions
# that realistically match the goods or services it provides.
VENDOR_CATALOG: dict[str, dict[str, list[str]]] = {
    "Software Licenses": {
        "Microsoft": ["Microsoft 365 subscription", "Additional M365 user seats"],
        "Salesforce": ["Sales Cloud subscription", "Additional CRM user seats"],
        "Atlassian": ["Jira and Confluence subscription"],
        "Adobe": ["Adobe Creative Cloud licenses", "Adobe Acrobat Pro licenses"],
        "Monday.com": ["Work management platform subscription"],
        "Zoom Video Communications": ["Zoom business plan subscription"],
        "JetBrains": ["IDE developer licenses renewal"],
        "Slack Technologies": ["Slack Business+ subscription"],
    },
    "Cloud Infrastructure": {
        "Amazon Web Services": ["EC2 compute usage", "S3 storage and backup",
                                "Data transfer charges"],
        "Microsoft Azure": ["Azure virtual machines usage", "Azure SQL database"],
        "Google Cloud": ["BigQuery analytics usage", "Cloud storage"],
        "Cloudflare": ["CDN and DDoS protection plan"],
        "Datadog": ["Infrastructure monitoring and logging"],
    },
    "Travel": {
        "El Al Israel Airlines": ["Flight tickets - business trip"],
        "Booking.com": ["Hotel accommodation"],
        "Dan Hotels": ["Hotel accommodation - Tel Aviv offsite"],
        "Issta Travel": ["Travel package - conference trip"],
        "Hertz Israel": ["Car rental"],
        "Gett": ["Local taxi rides"],
    },
    "Consulting": {
        "Deloitte Israel": ["Advisory services - process improvement"],
        "KPMG Somekh Chaikin": ["Internal audit support services"],
        "PwC Kesselman": ["Tax advisory services"],
        "EY Kost Forer": ["Financial due diligence support"],
        "Herzog Fox & Neeman": ["Legal counsel - commercial contracts"],
        "Nisha Recruitment": ["Recruitment fees - placement"],
    },
    "Office Supplies": {
        "Office Depot Israel": ["Office stationery", "Printer toner and paper"],
        "Kravitz": ["Office stationery"],
        "IKEA Israel": ["Office furniture"],
        "Shufersal": ["Kitchen and refreshments"],
    },
    "Advertising": {
        "Google Ads": ["Paid search campaign"],
        "Meta Platforms": ["Social media ads - Facebook and Instagram"],
        "LinkedIn": ["Sponsored content - B2B campaign"],
        "Taboola": ["Native advertising campaign"],
        "Outbrain": ["Content recommendation campaign"],
    },
    "Employee Welfare": {
        "Cibus": ["Employee meal vouchers"],
        "BuyMe": ["Holiday gift cards"],
        "Holmes Place": ["Employee gym memberships"],
        "Dan Hotels": ["Team building event"],
    },
}

# Payroll is split into fixed components rather than random vendors.
PAYROLL_COMPONENTS: list[tuple[str, str, float]] = [
    ("Hilan", "Monthly salary run", 0.78),
    ("Migdal Pension Fund", "Pension and severance contributions", 0.14),
    ("National Insurance Institute", "Employer NII contributions", 0.08),
]

# Number of journal entries per non-payroll cell (min, max inclusive).
ENTRY_COUNT_RANGE: dict[str, tuple[int, int]] = {
    "Software Licenses": (3, 7),
    "Cloud Infrastructure": (3, 6),
    "Travel": (4, 10),
    "Consulting": (2, 5),
    "Office Supplies": (3, 8),
    "Advertising": (4, 9),
    "Employee Welfare": (2, 5),
}


# ---------------------------------------------------------------------------
# Budget generation
# ---------------------------------------------------------------------------

def build_budget() -> pd.DataFrame:
    """Build the monthly budget table for all cost centers and categories."""
    rows = []
    for month in range(1, 13):
        for cost_center, categories in BASE_MONTHLY_BUDGET.items():
            for category, base_amount in categories.items():
                factor = BUDGET_SEASONALITY.get(category, {}).get(month, 1.0)
                # Round to the nearest 500 ILS, as budgets usually are
                amount = round(base_amount * factor / 500) * 500
                rows.append({
                    "Month": f"{YEAR}-{month:02d}",
                    "Cost_Center": cost_center,
                    "Expense_Category": category,
                    "Budget_Amount": float(amount),
                })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Actuals (GL) generation
# ---------------------------------------------------------------------------

def draw_spend_ratio(rng: np.random.Generator, category: str) -> float:
    """Return actual-to-budget ratio for a regular (non-scenario) cell."""
    if category == "Payroll":
        # Payroll is highly predictable
        return rng.normal(1.0, 0.015)
    if rng.random() < SAVINGS_PROBABILITY:
        # Meaningful savings: delayed purchases, cancelled trips, etc.
        return rng.uniform(0.70, 0.90)
    # Normal fluctuation around budget
    return float(np.clip(rng.normal(0.98, 0.05), 0.85, 1.10))


def split_amount(rng: np.random.Generator, total: float, n_parts: int) -> list[float]:
    """Split a total into n random positive parts that sum exactly to total."""
    weights = rng.dirichlet(np.full(n_parts, 2.0))
    parts = np.round(weights * total, 2)
    # Push the rounding residual into the largest entry
    parts[np.argmax(parts)] += round(total - parts.sum(), 2)
    return [round(float(p), 2) for p in parts]


def business_days(month: int) -> pd.DatetimeIndex:
    """Return all business days (Sun-Thu, Israeli work week) in a month."""
    start = pd.Timestamp(year=YEAR, month=month, day=1)
    end = start + pd.offsets.MonthEnd(0)
    return pd.bdate_range(start, end, freq="C", weekmask="Sun Mon Tue Wed Thu")


def build_cell_entries(
    rng: np.random.Generator,
    month: int,
    cost_center: str,
    category: str,
    budget_amount: float,
) -> list[dict]:
    """Generate the journal entries for one (month, cost center, category) cell."""
    days = business_days(month)
    month_label = pd.Timestamp(year=YEAR, month=month, day=1).strftime("%b %Y")
    entries: list[dict] = []
    scenario = OVERSPEND_SCENARIOS.get((cost_center, category, month))

    # Regular spend: near budget for scenario cells, random ratio otherwise
    ratio = rng.normal(1.0, 0.02) if scenario else draw_spend_ratio(rng, category)
    regular_total = round(budget_amount * ratio, 2)

    if category == "Payroll":
        # Salary, pension and NII posted on the last business day
        for vendor, description, share in PAYROLL_COMPONENTS:
            entries.append({
                "Date": days[-1],
                "Vendor_Name": vendor,
                "Description": f"{description} - {month_label}",
                "Actual_Amount": round(regular_total * share, 2),
            })
    else:
        low, high = ENTRY_COUNT_RANGE[category]
        n_entries = int(rng.integers(low, high + 1))
        catalog = VENDOR_CATALOG[category]
        vendors = list(catalog)
        for amount in split_amount(rng, regular_total, n_entries):
            vendor = str(rng.choice(vendors))
            description = str(rng.choice(catalog[vendor]))
            entries.append({
                "Date": rng.choice(days),
                "Vendor_Name": vendor,
                "Description": f"{description} - {month_label}",
                "Actual_Amount": amount,
            })

    # Overspend scenario: one distinct, large entry that explains the variance
    if scenario:
        extra_ratio, vendor, description = scenario
        entries.append({
            "Date": rng.choice(days),
            "Vendor_Name": vendor,
            "Description": description,
            "Actual_Amount": round(budget_amount * extra_ratio, 2),
        })

    for entry in entries:
        entry["Cost_Center"] = cost_center
        entry["Expense_Category"] = category
    return entries


def build_actuals(rng: np.random.Generator, budget: pd.DataFrame) -> pd.DataFrame:
    """Build the YTD GL actuals table from the budget and spend scenarios."""
    entries: list[dict] = []
    for row in budget.itertuples(index=False):
        month = int(row.Month.split("-")[1])
        if month > LAST_CLOSED_MONTH:
            # Open periods have no postings yet
            continue
        entries.extend(build_cell_entries(
            rng, month, row.Cost_Center, row.Expense_Category, row.Budget_Amount))

    actuals = pd.DataFrame(entries)
    actuals = actuals.sort_values(["Date", "Cost_Center", "Expense_Category"])
    actuals = actuals.reset_index(drop=True)
    actuals["Date"] = pd.to_datetime(actuals["Date"]).dt.strftime("%Y-%m-%d")
    actuals.insert(0, "Transaction_ID",
                   [f"JE-{YEAR}-{i:06d}" for i in range(1, len(actuals) + 1)])
    column_order = [
        "Transaction_ID", "Date", "Cost_Center", "Expense_Category",
        "Vendor_Name", "Description", "Actual_Amount",
    ]
    return actuals[column_order]


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Generate both datasets and save them as CSV files."""
    rng = np.random.default_rng(SEED)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    budget = build_budget()
    actuals = build_actuals(rng, budget)

    budget.to_csv(BUDGET_FILE, index=False, encoding="utf-8")
    actuals.to_csv(ACTUALS_FILE, index=False, encoding="utf-8")

    ytd_months = [f"{YEAR}-{m:02d}" for m in range(1, LAST_CLOSED_MONTH + 1)]
    annual_budget = budget["Budget_Amount"].sum()
    ytd_budget = budget.loc[budget["Month"].isin(ytd_months), "Budget_Amount"].sum()
    ytd_actual = actuals["Actual_Amount"].sum()
    print(f"Budget rows      : {len(budget):>6,}  ->  {BUDGET_FILE.name}")
    print(f"GL entries (YTD) : {len(actuals):>6,}  ->  {ACTUALS_FILE.name}")
    print(f"Annual budget    : {annual_budget:>15,.2f} ILS")
    print(f"YTD budget       : {ytd_budget:>15,.2f} ILS (through {ytd_months[-1]})")
    print(f"YTD actual       : {ytd_actual:>15,.2f} ILS "
          f"({ytd_actual / ytd_budget - 1:+.1%} vs YTD budget)")


if __name__ == "__main__":
    main()
