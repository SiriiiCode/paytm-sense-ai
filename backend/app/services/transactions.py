import csv
import json
import os
from pathlib import Path

from fastapi import HTTPException

from ..schemas import Transaction, TransactionCreate


DATA_FILE = (
    Path(__file__).resolve().parents[2]
    / "data"
    / "transactions.csv"
)
ACCOUNT_FILE = (
    Path(__file__).resolve().parents[2]
    / "data"
    / "account.json"
)


FIELDNAMES = [
    "transaction_id",
    "date",
    "description",
    "amount",
    "type",
    "category",
    "recurring",
]


def load_transactions() -> list[Transaction]:
    transactions = []

    if not DATA_FILE.exists():
        return transactions

    with DATA_FILE.open("r", newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)

        for row in reader:
            transaction = Transaction(
                transaction_id=row["transaction_id"],
                date=row["date"],
                description=row["description"],
                amount=float(row["amount"]),
                type=row["type"],
                category=row["category"],
                recurring=row["recurring"].strip().lower()
                in {"true", "yes", "1"},
            )

            transactions.append(transaction)

    return transactions


def _next_transaction_id(transactions: list[Transaction]) -> str:
    highest = 0
    for transaction in transactions:
        suffix = transaction.transaction_id.removeprefix("TXN")
        if suffix.isdigit():
            highest = max(highest, int(suffix))
    return f"TXN{highest + 1:04d}"


def _transaction_to_row(transaction: Transaction) -> dict:
    return {
        "transaction_id": transaction.transaction_id,
        "date": transaction.date.isoformat(),
        "description": transaction.description,
        "amount": transaction.amount,
        "type": transaction.type,
        "category": transaction.category,
        "recurring": "Yes" if transaction.recurring else "No",
    }


def _load_account() -> dict:
    with ACCOUNT_FILE.open("r", encoding="utf-8") as file:
        return json.load(file)


def _balance_after_transaction(balance: float, transaction: Transaction) -> float:
    if transaction.type == "Credit":
        return round(balance + transaction.amount, 2)
    return round(balance - transaction.amount, 2)


def _write_transactions_file(all_transactions: list[Transaction]) -> None:
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    temp_file = DATA_FILE.with_suffix(".csv.tmp")
    with temp_file.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDNAMES)
        writer.writeheader()
        for transaction in all_transactions:
            writer.writerow(_transaction_to_row(transaction))
    os.replace(temp_file, DATA_FILE)


def _write_account_file(account: dict) -> None:
    ACCOUNT_FILE.parent.mkdir(parents=True, exist_ok=True)
    temp_file = ACCOUNT_FILE.with_suffix(".json.tmp")
    with temp_file.open("w", encoding="utf-8") as file:
        json.dump(account, file, indent=2)
        file.write("\n")
    os.replace(temp_file, ACCOUNT_FILE)


def create_transaction(payload: TransactionCreate) -> Transaction:
    transactions = load_transactions()
    transaction = Transaction(
        transaction_id=_next_transaction_id(transactions),
        **payload.model_dump(),
    )
    original_transactions = DATA_FILE.read_bytes() if DATA_FILE.exists() else None
    original_account = ACCOUNT_FILE.read_bytes() if ACCOUNT_FILE.exists() else None

    try:
        account = _load_account()
        account["current_balance"] = _balance_after_transaction(
            float(account["current_balance"]),
            transaction,
        )
        _write_transactions_file([*transactions, transaction])
        _write_account_file(account)
    except OSError as exc:
        _restore_file(DATA_FILE, original_transactions)
        _restore_file(ACCOUNT_FILE, original_account)
        raise HTTPException(
            status_code=500,
            detail="Unable to persist transaction and account state",
        ) from exc
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        _restore_file(DATA_FILE, original_transactions)
        _restore_file(ACCOUNT_FILE, original_account)
        raise HTTPException(
            status_code=500,
            detail="Account state is invalid",
        ) from exc

    return transaction


def _restore_file(path: Path, content: bytes | None) -> None:
    if content is None:
        if path.exists():
            path.unlink()
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
