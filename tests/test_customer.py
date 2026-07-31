"""
Tests for model/customer.py

Run with (from the project root, keep_track/):
    pytest tests/test_customer.py -v

Each test runs inside a temporary directory (see the `work_dir` fixture)
with its own ./tables/credits.csv and ./tables/daily_sales.csv, so the
real project data is never touched. generate_report() needs `reportlab`
installed (pip install reportlab).
"""
import pandas as pd
import pytest

from model.customer import Customer


@pytest.fixture
def work_dir(tmp_path, monkeypatch):
    tables = tmp_path / "tables"
    tables.mkdir()
    monkeypatch.chdir(tmp_path)
    return tmp_path


def write_credits(work_dir, rows):
    """rows: list of dicts with keys customer, amount, size"""
    pd.DataFrame(rows, columns=["customer", "amount", "size"]).to_csv(
        work_dir / "tables" / "credits.csv", index=False
    )


def write_daily_sales(work_dir, rows):
    """rows: list of dicts with keys date, customer, area, size, quantity, method, amount"""
    pd.DataFrame(
        rows,
        columns=["date", "customer", "area", "size", "quantity", "method", "amount"],
    ).to_csv(work_dir / "tables" / "daily_sales.csv", index=False)


# ---------------------------------------------------------------------
# get_credit_record
# ---------------------------------------------------------------------

def test_get_credit_record_returns_balance_for_existing_customer(work_dir):
    write_credits(work_dir, [
        {"customer": "Alice", "amount": 150, "size": "9kg"},
        {"customer": "Bob", "amount": 0, "size": "19kg"},
    ])
    customer = Customer("Alice")

    assert customer.get_credit_record() == 150


def test_get_credit_record_unknown_customer_raises(work_dir):
    write_credits(work_dir, [
        {"customer": "Alice", "amount": 150, "size": "9kg"},
    ])
    customer = Customer("Nobody")

    with pytest.raises(ValueError):
        customer.get_credit_record()


# ---------------------------------------------------------------------
# get_credit_sales
# ---------------------------------------------------------------------

def test_get_credit_sales_walks_back_to_cover_the_balance(work_dir):
    # Balance owed is 100. Latest sale (07-20) alone covers it, so only
    # that one row should be selected even though older credit sales exist.
    write_credits(work_dir, [
        {"customer": "Alice", "amount": 100, "size": "9kg"},
    ])
    write_daily_sales(work_dir, [
        {"date": "2026-07-01", "customer": "Alice", "area": "North",
         "size": "9kg", "quantity": 2, "method": "credit", "amount": 30},
        {"date": "2026-07-20", "customer": "Alice", "area": "North",
         "size": "9kg", "quantity": 5, "method": "credit", "amount": 20},
    ])
    customer = Customer("Alice")

    sales_df, balance_due = customer.get_credit_sales()

    assert balance_due == 100
    assert len(sales_df) == 1
    assert sales_df.iloc[0]["date"] == pd.Timestamp("2026-07-20")
    assert sales_df.iloc[0]["line_total"] == 100


def test_get_credit_sales_accumulates_multiple_rows_until_balance_covered(work_dir):
    # Balance owed is 65. Latest sale alone (07-25, 30) isn't enough, so it
    # should keep walking back to 07-15 (40) -> running total 70, which
    # covers the balance, and stop before 07-01 (999).
    write_credits(work_dir, [
        {"customer": "Alice", "amount": 65, "size": "9kg"},
    ])
    write_daily_sales(work_dir, [
        {"date": "2026-07-01", "customer": "Alice", "area": "North",
         "size": "9kg", "quantity": 1, "method": "credit", "amount": 999},
        {"date": "2026-07-15", "customer": "Alice", "area": "North",
         "size": "9kg", "quantity": 4, "method": "credit", "amount": 10},   # 40
        {"date": "2026-07-25", "customer": "Alice", "area": "North",
         "size": "9kg", "quantity": 3, "method": "credit", "amount": 10},   # 30
    ])
    customer = Customer("Alice")

    sales_df, balance_due = customer.get_credit_sales()

    dates = list(sales_df["date"])
    assert pd.Timestamp("2026-07-01") not in dates
    assert pd.Timestamp("2026-07-15") in dates
    assert pd.Timestamp("2026-07-25") in dates
    # Result comes back oldest -> newest.
    assert dates == sorted(dates)


def test_get_credit_sales_ignores_non_credit_methods(work_dir):
    write_credits(work_dir, [
        {"customer": "Alice", "amount": 20, "size": "9kg"},
    ])
    write_daily_sales(work_dir, [
        {"date": "2026-07-20", "customer": "Alice", "area": "North",
         "size": "9kg", "quantity": 5, "method": "cash", "amount": 100},
        {"date": "2026-07-19", "customer": "Alice", "area": "North",
         "size": "9kg", "quantity": 2, "method": "credit", "amount": 10},
    ])
    customer = Customer("Alice")

    sales_df, _ = customer.get_credit_sales()

    assert len(sales_df) == 1
    assert sales_df.iloc[0]["method"] == "credit"


def test_get_credit_sales_ignores_other_customers(work_dir):
    write_credits(work_dir, [
        {"customer": "Alice", "amount": 20, "size": "9kg"},
    ])
    write_daily_sales(work_dir, [
        {"date": "2026-07-19", "customer": "Bob", "area": "North",
         "size": "9kg", "quantity": 2, "method": "credit", "amount": 500},
        {"date": "2026-07-18", "customer": "Alice", "area": "North",
         "size": "9kg", "quantity": 2, "method": "credit", "amount": 10},
    ])
    customer = Customer("Alice")

    sales_df, _ = customer.get_credit_sales()

    assert len(sales_df) == 1
    assert (sales_df["customer"] == "Alice").all()


def test_get_credit_sales_zero_balance_selects_no_rows(work_dir):
    write_credits(work_dir, [
        {"customer": "Alice", "amount": 0, "size": "9kg"},
    ])
    write_daily_sales(work_dir, [
        {"date": "2026-07-19", "customer": "Alice", "area": "North",
         "size": "9kg", "quantity": 2, "method": "credit", "amount": 10},
    ])
    customer = Customer("Alice")

    sales_df, balance_due = customer.get_credit_sales()

    assert balance_due == 0
    assert sales_df.empty


def test_get_credit_sales_insufficient_history_returns_everything_available(work_dir):
    # Balance owed (500) exceeds the sum of all recorded credit sales (40).
    # Should just return everything it has rather than erroring.
    write_credits(work_dir, [
        {"customer": "Alice", "amount": 500, "size": "9kg"},
    ])
    write_daily_sales(work_dir, [
        {"date": "2026-07-01", "customer": "Alice", "area": "North",
         "size": "9kg", "quantity": 2, "method": "credit", "amount": 10},   # 20
        {"date": "2026-07-02", "customer": "Alice", "area": "North",
         "size": "9kg", "quantity": 2, "method": "credit", "amount": 10},   # 20
    ])
    customer = Customer("Alice")

    sales_df, balance_due = customer.get_credit_sales()

    assert len(sales_df) == 2
    assert sales_df["line_total"].sum() == 40


# ---------------------------------------------------------------------
# generate_report (PDF generation)
# ---------------------------------------------------------------------

def test_generate_report_writes_a_named_pdf(work_dir):
    write_credits(work_dir, [
        {"customer": "Alice", "amount": 100, "size": "9kg"},
    ])
    write_daily_sales(work_dir, [
        {"date": "2026-07-20", "customer": "Alice", "area": "North",
         "size": "9kg", "quantity": 5, "method": "credit", "amount": 20},
    ])
    customer = Customer("Alice")

    customer.generate_report()

    pdf_path = work_dir / "Alice_credit_report.pdf"
    assert pdf_path.exists()
    assert pdf_path.stat().st_size > 0


def test_generate_report_table_has_expected_rows_and_columns(work_dir, monkeypatch):
    write_credits(work_dir, [
        {"customer": "Alice", "amount": 50, "size": "9kg"},
    ])
    write_daily_sales(work_dir, [
        {"date": "2026-07-18", "customer": "Alice", "area": "North",
         "size": "9kg", "quantity": 5, "method": "credit", "amount": 10},
    ])

    captured_tables = []
    import reportlab.platypus as platypus
    real_table = platypus.Table

    def spy_table(data, *args, **kwargs):
        captured_tables.append(data)
        return real_table(data, *args, **kwargs)

    monkeypatch.setattr(platypus, "Table", spy_table)

    Customer("Alice").generate_report()

    table_rows = captured_tables[-1]
    assert table_rows[0] == ["Date", "Size", "Quantity", "Amount"]
    assert table_rows[1][0] == "2026-07-18"
    assert table_rows[1][1] == "9kg"
    assert table_rows[1][2] == 5
    assert table_rows[1][3] == 10
    assert table_rows[-1][2] == "Balance due"
    assert table_rows[-1][3] == 50


def test_customer_class_never_writes_to_the_source_tables(work_dir):
    write_credits(work_dir, [
        {"customer": "Alice", "amount": 65, "size": "9kg"},
    ])
    write_daily_sales(work_dir, [
        {"date": "2026-07-15", "customer": "Alice", "area": "North",
         "size": "9kg", "quantity": 4, "method": "credit", "amount": 10},
        {"date": "2026-07-25", "customer": "Alice", "area": "North",
         "size": "9kg", "quantity": 3, "method": "credit", "amount": 10},
    ])

    credits_before = (work_dir / "tables" / "credits.csv").read_bytes()
    sales_before = (work_dir / "tables" / "daily_sales.csv").read_bytes()

    customer = Customer("Alice")
    customer.get_credit_record()
    customer.get_credit_sales()
    customer.generate_report()

    credits_after = (work_dir / "tables" / "credits.csv").read_bytes()
    sales_after = (work_dir / "tables" / "daily_sales.csv").read_bytes()

    assert credits_before == credits_after
    assert sales_before == sales_after


def test_generate_report_handles_customer_with_no_credit_sales(work_dir):
    # Balance on file but no matching credit-sale history — should not
    # crash, just produce a table with no line-item rows.
    write_credits(work_dir, [
        {"customer": "Alice", "amount": 50, "size": "9kg"},
    ])
    write_daily_sales(work_dir, [])

    Customer("Alice").generate_report()

    assert (work_dir / "Alice_credit_report.pdf").exists()
