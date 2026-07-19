import pandas as pd
import pytest

import services.update_credits as uc


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


def read_credits(work_dir):
    return pd.read_csv(work_dir / "tables" / "credits.csv")


# ---------------------------------------------------------------------

def test_new_customer_credit_sale_is_added(work_dir):
    write_daily_sales(work_dir, [
        {"date": "2026-07-19", "customer": "Dan", "method": "credit",
         "amount": 50, "quantity": 2},
    ])
    write_credits(work_dir, [])

    uc.update_credit("2026-07-19")

    credits = read_credits(work_dir)
    row = credits[credits["customer"] == "Dan"].iloc[0]
    assert row["amount"] == 100          # 50 * 2
    assert row["status"] == "active"


def test_existing_customer_credit_sale_increments_amount(work_dir):
    write_daily_sales(work_dir, [
        {"date": "2026-07-19", "customer": "Alice", "method": "credit",
         "amount": 20, "quantity": 3},
    ])
    write_credits(work_dir, [
        {"customer": "Alice", "amount": 100, "status": "open"},
    ])

    uc.update_credit("2026-07-19")

    credits = read_credits(work_dir)
    row = credits[credits["customer"] == "Alice"].iloc[0]
    assert row["amount"] == 160          # 100 + (20 * 3)
    assert row["status"] == "open"       # status untouched for existing customers


def test_multiple_credit_sales_same_customer_same_date_accumulate(work_dir):
    write_daily_sales(work_dir, [
        {"date": "2026-07-19", "customer": "Alice", "method": "credit",
         "amount": 20, "quantity": 1},
        {"date": "2026-07-19", "customer": "Alice", "method": "credit",
         "amount": 30, "quantity": 1},
    ])
    write_credits(work_dir, [
        {"customer": "Alice", "amount": 0, "status": "open"},
    ])

    uc.update_credit("2026-07-19")

    credits = read_credits(work_dir)
    row = credits[credits["customer"] == "Alice"].iloc[0]
    assert row["amount"] == 50            # 20 + 30


def test_cash_sales_are_ignored(work_dir):
    write_daily_sales(work_dir, [
        {"date": "2026-07-19", "customer": "Alice", "method": "cash",
         "amount": 500, "quantity": 1},
    ])
    write_credits(work_dir, [])

    uc.update_credit("2026-07-19")

    credits = read_credits(work_dir)
    assert "Alice" not in credits["customer"].values


def test_sales_on_other_dates_are_ignored(work_dir):
    write_daily_sales(work_dir, [
        {"date": "2026-07-18", "customer": "Alice", "method": "credit",
         "amount": 500, "quantity": 1},
    ])
    write_credits(work_dir, [])

    uc.update_credit("2026-07-19")

    credits = read_credits(work_dir)
    assert "Alice" not in credits["customer"].values


def test_no_matching_credit_sales_leaves_credits_unchanged(work_dir):
    write_daily_sales(work_dir, [
        {"date": "2026-07-19", "customer": "Alice", "method": "cash",
         "amount": 500, "quantity": 1},
    ])
    write_credits(work_dir, [
        {"customer": "Bob", "amount": 40, "status": "open"},
    ])

    uc.update_credit("2026-07-19")

    credits = read_credits(work_dir)
    assert len(credits) == 1
    row = credits.iloc[0]
    assert row["customer"] == "Bob"
    assert row["amount"] == 40


def test_new_and_existing_customer_in_same_run(work_dir):
    write_daily_sales(work_dir, [
        {"date": "2026-07-19", "customer": "Alice", "method": "credit",
         "amount": 20, "quantity": 2},   # existing -> +40
        {"date": "2026-07-19", "customer": "Eve", "method": "credit",
         "amount": 10, "quantity": 5},   # new -> 50
    ])
    write_credits(work_dir, [
        {"customer": "Alice", "amount": 100, "status": "open"},
    ])

    uc.update_credit("2026-07-19")

    credits = read_credits(work_dir)
    alice = credits[credits["customer"] == "Alice"].iloc[0]
    eve = credits[credits["customer"] == "Eve"].iloc[0]
    assert alice["amount"] == 140
    assert eve["amount"] == 50
    assert eve["status"] == "active"


def test_amount_is_price_times_quantity_not_price_alone(work_dir):
    write_daily_sales(work_dir, [
        {"date": "2026-07-19", "customer": "Frank", "method": "credit",
         "amount": 15, "quantity": 4},
    ])
    write_credits(work_dir, [])

    uc.update_credit("2026-07-19")

    credits = read_credits(work_dir)
    row = credits[credits["customer"] == "Frank"].iloc[0]
    assert row["amount"] == 60           # 15 * 4, not 15