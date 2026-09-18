import json
from pathlib import Path

from ..schemas import Transaction
from .recurring import get_recurring_commitment_total


ACCOUNT_FILE = (
    Path(__file__).resolve().parents[2]
    / "data"
    / "account.json"
)

SAVINGS_GOAL = 5_000.0
EMERGENCY_BUFFER = 10_000.0


def get_balance() -> float:
    with ACCOUNT_FILE.open("r", encoding="utf-8") as file:
        account = json.load(file)

    return round(float(account["current_balance"]), 2)


def get_net_cashflow(transactions: list[Transaction]) -> float:
    total_credit = sum(
        transaction.amount
        for transaction in transactions
        if transaction.type == "Credit"
    )

    total_debit = sum(
        transaction.amount
        for transaction in transactions
        if transaction.type == "Debit"
    )

    return round(total_credit - total_debit, 2)


def get_safe_to_spend(
    transactions: list[Transaction],
) -> dict:

    balance = get_balance()

    recurring_commitments = get_recurring_commitment_total(
        transactions
    )

    protected_money = (
        recurring_commitments
        + SAVINGS_GOAL
        + EMERGENCY_BUFFER
    )

    safe_to_spend = max(
        balance - protected_money,
        0,
    )

    return {
        "balance": round(balance, 2),
        "recurring_commitments": round(
            recurring_commitments, 2
        ),
        "savings_goal": SAVINGS_GOAL,
        "emergency_buffer": EMERGENCY_BUFFER,
        "protected_money": round(
            protected_money, 2
        ),
        "safe_to_spend": round(
            safe_to_spend, 2
        ),
    }