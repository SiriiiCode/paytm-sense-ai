import csv
from pathlib import Path

from ..schemas import Transaction


DATA_FILE = (
    Path(__file__).resolve().parents[2]
    / "data"
    / "transactions.csv"
)


def load_transactions() -> list[Transaction]:
    transactions = []

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