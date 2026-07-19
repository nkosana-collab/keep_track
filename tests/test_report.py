"""
Tests for services/report.py

Run with (from the project root, keep_track/):
    pytest tests/test_report.py -v

Each test runs inside a temporary directory (see the `work_dir` fixture)
with its own ./tables/daily_sales.csv, ./tables/credits.csv, and
./tables/expenses.csv, so the real project data is never touched.

Note: generate_report() needs the `reportlab` package installed
(pip install reportlab) since report.py imports it lazily inside the
method.
"""
import os
import pandas as pd
import pytest

from services.report import Report


@pytest.fixture
def work_dir(tmp_path, monkeypatch):
    tables = tmp_path / "tables"
    tables.mkdir()
    monkeypatch.chdir(tmp_path)
    return tmp_path


def write_daily_sales(work_dir, rows):
    """rows: list of dicts with keys date, customer, method, amount, quantity"""
    pd.DataFrame(rows).to_csv(work_dir / "tables" / "daily_sales.csv", index=False)


def write_credits(work_dir, rows):
    """rows: list of dicts with keys customer, amount, status"""
    pd.DataFrame(rows, columns=["customer", "amount", "status"]).to_csv(
        work_dir / "tables" / "credits.csv", index=False
    )


def write_expenses(work_dir, rows):
    """rows: list of dicts with keys date, amount (and any other columns)"""
    pd.DataFrame(rows, columns=["date", "amount"]).to_csv(
        work_dir / "tables" / "expenses.csv", index=False
    )


# ---------------------------------------------------------------------
# get_sales
# ---------------------------------------------------------------------

def test_get_sales_splits_totals_by_method(work_dir):
    write_daily_sales(work_dir, [
        {"date": "2026-07-10", "customer": "Alice", "method": "cash",
         "amount": 10, "quantity": 2},   # 20
        {"date": "2026-07-11", "customer": "Bob", "method": "credit",
         "amount": 15, "quantity": 3},   # 45
        {"date": "2026-07-12", "customer": "Carol", "method": "eft",
         "amount": 100, "quantity": 1},  # 100
    ])
    report = Report("2026-07-01", "2026-07-31")

    sales = report.get_sales()

    assert sales == {"cash_sales": 20, "credit_sales": 45, "eft_sales": 100}


def test_get_sales_missing_method_defaults_to_zero(work_dir):
    write_daily_sales(work_dir, [
        {"date": "2026-07-10", "customer": "Alice", "method": "cash",
         "amount": 10, "quantity": 1},
    ])
    report = Report("2026-07-01", "2026-07-31")

    sales = report.get_sales()

    assert sales["cash_sales"] == 10
    assert sales["credit_sales"] == 0
    assert sales["eft_sales"] == 0


def test_get_sales_excludes_rows_outside_date_range(work_dir):
    write_daily_sales(work_dir, [
        {"date": "2026-06-30", "customer": "Alice", "method": "cash",
         "amount": 100, "quantity": 1},   # before range
        {"date": "2026-08-01", "customer": "Bob", "method": "cash",
         "amount": 100, "quantity": 1},   # after range
        {"date": "2026-07-15", "customer": "Carol", "method": "cash",
         "amount": 10, "quantity": 1},    # inside range
    ])
    report = Report("2026-07-01", "2026-07-31")

    sales = report.get_sales()

    assert sales["cash_sales"] == 10


def test_get_sales_includes_boundary_dates(work_dir):
    write_daily_sales(work_dir, [
        {"date": "2026-07-01", "customer": "Alice", "method": "cash",
         "amount": 5, "quantity": 1},     # start boundary
        {"date": "2026-07-31", "customer": "Bob", "method": "cash",
         "amount": 7, "quantity": 1},     # end boundary
    ])
    report = Report("2026-07-01", "2026-07-31")

    sales = report.get_sales()

    assert sales["cash_sales"] == 12


def test_get_sales_no_rows_in_range_returns_all_zero(work_dir):
    write_daily_sales(work_dir, [
        {"date": "2026-01-01", "customer": "Alice", "method": "cash",
         "amount": 10, "quantity": 1},
    ])
    report = Report("2026-07-01", "2026-07-31")

    sales = report.get_sales()

    assert sales == {"cash_sales": 0, "credit_sales": 0, "eft_sales": 0}


# ---------------------------------------------------------------------
# get_credits
# ---------------------------------------------------------------------

def test_get_credits_only_includes_active_status(work_dir):
    write_credits(work_dir, [
        {"customer": "Alice", "amount": 100, "status": "active"},
        {"customer": "Bob", "amount": 50, "status": "settled"},
        {"customer": "Carol", "amount": 75, "status": "active"},
    ])
    report = Report("2026-07-01", "2026-07-31")

    balances, total = report.get_credits()

    assert balances == {"Alice": 100, "Carol": 75}
    assert total == 175
    assert "Bob" not in balances


def test_get_credits_no_active_accounts_returns_empty(work_dir):
    write_credits(work_dir, [
        {"customer": "Bob", "amount": 50, "status": "settled"},
    ])
    report = Report("2026-07-01", "2026-07-31")

    balances, total = report.get_credits()

    assert balances == {}
    assert total == 0


def test_get_credits_empty_file_returns_empty(work_dir):
    write_credits(work_dir, [])
    report = Report("2026-07-01", "2026-07-31")

    balances, total = report.get_credits()

    assert balances == {}
    assert total == 0


# ---------------------------------------------------------------------
# get_expenses
# ---------------------------------------------------------------------

def test_get_expenses_sums_within_range(work_dir):
    write_expenses(work_dir, [
        {"date": "2026-07-05", "amount": 200},
        {"date": "2026-07-20", "amount": 300},
    ])
    report = Report("2026-07-01", "2026-07-31")

    assert report.get_expenses() == 500


def test_get_expenses_excludes_rows_outside_range(work_dir):
    write_expenses(work_dir, [
        {"date": "2026-06-01", "amount": 999},   # before range
        {"date": "2026-07-05", "amount": 200},   # inside range
    ])
    report = Report("2026-07-01", "2026-07-31")

    assert report.get_expenses() == 200


def test_get_expenses_no_rows_in_range_returns_zero(work_dir):
    write_expenses(work_dir, [
        {"date": "2026-01-01", "amount": 999},
    ])
    report = Report("2026-07-01", "2026-07-31")

    assert report.get_expenses() == 0


# ---------------------------------------------------------------------
# generate_report (PDF generation)
# ---------------------------------------------------------------------

def test_generate_report_writes_a_pdf_file(work_dir):
    write_daily_sales(work_dir, [
        {"date": "2026-07-10", "customer": "Alice", "method": "cash",
         "amount": 10, "quantity": 2},
        {"date": "2026-07-11", "customer": "Bob", "method": "credit",
         "amount": 15, "quantity": 3},
    ])
    write_credits(work_dir, [
        {"customer": "Bob", "amount": 45, "status": "active"},
    ])
    write_expenses(work_dir, [
        {"date": "2026-07-12", "amount": 30},
    ])

    report = Report("2026-07-01", "2026-07-31")
    report.generate_report()

    pdf_path = work_dir / "report.pdf"
    assert pdf_path.exists()
    assert pdf_path.stat().st_size > 0


def test_generate_report_handles_no_active_credits(work_dir):
    # Regression guard: an empty balances dict still needs to render
    # a valid credits table (header + Total row only).
    write_daily_sales(work_dir, [
        {"date": "2026-07-10", "customer": "Alice", "method": "cash",
         "amount": 10, "quantity": 1},
    ])
    write_credits(work_dir, [])
    write_expenses(work_dir, [])

    report = Report("2026-07-01", "2026-07-31")
    report.generate_report()   # should not raise

    assert (work_dir / "report.pdf").exists()


def test_generate_report_net_total_is_gross_minus_expenses(work_dir, monkeypatch):
    # Verify the arithmetic feeding the summary table, by intercepting
    # the Table() calls reportlab makes rather than parsing the PDF.
    write_daily_sales(work_dir, [
        {"date": "2026-07-10", "customer": "Alice", "method": "cash",
         "amount": 100, "quantity": 1},   # cash 100
        {"date": "2026-07-11", "customer": "Bob", "method": "credit",
         "amount": 50, "quantity": 1},    # credit 50
    ])
    write_credits(work_dir, [
        {"customer": "Bob", "amount": 50, "status": "active"},
    ])
    write_expenses(work_dir, [
        {"date": "2026-07-12", "amount": 40},
    ])

    captured_tables = []
    import reportlab.platypus as platypus
    real_table = platypus.Table

    def spy_table(data, *args, **kwargs):
        captured_tables.append(data)
        return real_table(data, *args, **kwargs)

    monkeypatch.setattr(platypus, "Table", spy_table)

    report = Report("2026-07-01", "2026-07-31")
    report.generate_report()

    summary_rows = captured_tables[-1]
    summary = {row[0]: row[1] for row in summary_rows[1:]}
    assert summary["Credit_sales"] == 50
    assert summary["Cash_sales"] == 100
    assert summary["EFT_sales"] == 0
    assert summary["Gross_total"] == 150
    assert summary["Expenses"] == 40
    assert summary["Net_total"] == 110