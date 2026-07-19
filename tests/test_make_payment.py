"""
Tests for make_payment.py

Run with:  pytest test_make_payment.py -v
"""

import pandas as pd
import pytest

import services.make_payment as mp


@pytest.fixture
def work_dir(tmp_path, monkeypatch):
    """
    Create a ./tables/ directory with seed credits.csv and payments.csv,
    then chdir into it so the module's relative paths resolve here.
    """
    tables = tmp_path / "tables"
    tables.mkdir()

    credits_df = pd.DataFrame({
        "customer": ["Alice", "Bob", "Carol"],
        "amount": [500, 100, 250],
        "status": ["open", "open", "open"],
    })
    credits_df.to_csv(tables / "credits.csv", index=False)

    # payments.csv needs to pre-exist with a header row since make_payment
    # appends with header=False.
    pd.DataFrame(columns=["date", "customer", "amount"]).to_csv(
        tables / "payments.csv", index=False
    )

    monkeypatch.chdir(tmp_path)
    return tmp_path


def read_credits(work_dir):
    return pd.read_csv(work_dir / "tables" / "credits.csv")


def read_payments(work_dir):
    return pd.read_csv(work_dir / "tables" / "payments.csv")


# ---------------------------------------------------------------------
# decreament_credit
# ---------------------------------------------------------------------

def test_partial_payment_reduces_amount_and_keeps_open(work_dir):
    mp.decreament_credit("Alice", 200)
    credits = read_credits(work_dir)
    row = credits[credits["customer"] == "Alice"].iloc[0]
    assert row["amount"] == 300
    assert row["status"] == "open"


def test_exact_payment_settles_account(work_dir):
    mp.decreament_credit("Bob", 100)
    credits = read_credits(work_dir)
    row = credits[credits["customer"] == "Bob"].iloc[0]
    assert row["amount"] == 0
    assert row["status"] == "settled"


def test_overpayment_clamps_to_zero_and_settles(work_dir):
    # Paying more than what's owed should not go negative.
    mp.decreament_credit("Carol", 999)
    credits = read_credits(work_dir)
    row = credits[credits["customer"] == "Carol"].iloc[0]
    assert row["amount"] == 0
    assert row["status"] == "settled"


def test_unknown_customer_raises(work_dir):
    # Current implementation does credit_account["amount"].iloc[0] with no
    # existence check, so an unknown customer should raise an IndexError.
    with pytest.raises(IndexError):
        mp.decreament_credit("Nobody", 50)


def test_only_targeted_customer_row_changes(work_dir):
    mp.decreament_credit("Alice", 200)
    credits = read_credits(work_dir)
    bob = credits[credits["customer"] == "Bob"].iloc[0]
    carol = credits[credits["customer"] == "Carol"].iloc[0]
    assert bob["amount"] == 100
    assert carol["amount"] == 250


def test_zero_amount_payment_leaves_balance_unchanged(work_dir):
    mp.decreament_credit("Alice", 0)
    credits = read_credits(work_dir)
    row = credits[credits["customer"] == "Alice"].iloc[0]
    assert row["amount"] == 500
    assert row["status"] == "open"


# ---------------------------------------------------------------------
# make_payment
# ---------------------------------------------------------------------

def test_make_payment_appends_a_row_to_payments_csv(work_dir):
    mp.make_payment("2026-07-19", "Alice", 200)
    payments = read_payments(work_dir)
    assert len(payments) == 1
    row = payments.iloc[0]
    assert row["date"] == "2026-07-19"
    assert row["customer"] == "Alice"
    assert row["amount"] == 200


def test_make_payment_appends_without_clobbering_existing_rows(work_dir):
    mp.make_payment("2026-07-19", "Alice", 100)
    mp.make_payment("2026-07-20", "Bob", 50)
    payments = read_payments(work_dir)
    assert len(payments) == 2
    assert list(payments["customer"]) == ["Alice", "Bob"]


def test_make_payment_also_updates_credits(work_dir):
    mp.make_payment("2026-07-19", "Alice", 200)
    credits = read_credits(work_dir)
    row = credits[credits["customer"] == "Alice"].iloc[0]
    assert row["amount"] == 300
    assert row["status"] == "open"


def test_make_payment_settles_when_amount_covers_full_credit(work_dir):
    mp.make_payment("2026-07-19", "Bob", 100)
    credits = read_credits(work_dir)
    row = credits[credits["customer"] == "Bob"].iloc[0]
    assert row["amount"] == 0
    assert row["status"] == "settled"


def test_make_payment_unknown_customer_still_raises(work_dir):
    # payments.csv row gets written before decreament_credit is called,
    # so this also verifies that a bad customer doesn't silently succeed.
    with pytest.raises(IndexError):
        mp.make_payment("2026-07-19", "Nobody", 50)
    payments = read_payments(work_dir)
    # The payment row was still appended even though the credit update failed.
    assert len(payments) == 1