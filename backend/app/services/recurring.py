from datetime import timedelta
from statistics import median

from ..schemas import Transaction


def _infer_frequency(dates: list) -> tuple[str, float]:
    """
    Infer a simple payment frequency from the gaps between transactions.

    Returns:
        (frequency_name, expected_days)
    """

    if len(dates) < 2:
        return "unknown", 30.0

    dates = sorted(dates)

    gaps = [
        (dates[i] - dates[i - 1]).days
        for i in range(1, len(dates))
    ]

    typical_gap = median(gaps)

    if 5 <= typical_gap <= 9:
        return "weekly", 7.0

    if 20 <= typical_gap <= 40:
        return "monthly", 30.0

    if 75 <= typical_gap <= 100:
        return "quarterly", 90.0

    return "unknown", float(typical_gap)


def _commitment_key(transaction: Transaction) -> str:
    return "|".join(
        [
            transaction.description.strip().lower(),
            transaction.category.strip().lower(),
        ]
    )


def get_recurring_commitments(
    transactions: list[Transaction],
) -> list[dict]:

    recurring_transactions = [
        transaction
        for transaction in transactions
        if transaction.type == "Debit"
        and transaction.recurring
    ]

    if not recurring_transactions:
        return []

    # The latest transaction in the dataset represents
    # the latest financial information available to us.
    as_of_date = max(
        transaction.date
        for transaction in transactions
    )

    groups: dict[str, list[Transaction]] = {}

    for transaction in recurring_transactions:
        key = _commitment_key(transaction)

        groups.setdefault(key, []).append(transaction)

    commitments = []

    for group in groups.values():
        group.sort(key=lambda transaction: transaction.date)

        latest = group[-1]

        frequency, expected_days = _infer_frequency(
            [transaction.date for transaction in group]
        )

        days_since_last = (
            as_of_date - latest.date
        ).days

        # Allow some tolerance for late/missed transactions.
        active_threshold = expected_days * 1.5

        is_active = days_since_last <= active_threshold
        next_expected_date = latest.date + timedelta(days=int(expected_days))
        overdue_days = max((as_of_date - next_expected_date).days, 0)

        commitments.append(
            {
                "description": latest.description,
                "category": latest.category,
                "amount": latest.amount,
                "frequency": frequency,
                "last_seen": latest.date,
                "days_since_last": days_since_last,
                "status": "active" if is_active else "inactive",
                "next_expected_date": next_expected_date,
                "overdue_days": overdue_days,
            }
        )

    return sorted(
        commitments,
        key=lambda item: item["amount"],
        reverse=True,
    )


def get_recurring_commitment_total(
    transactions: list[Transaction],
) -> float:

    commitments = get_recurring_commitments(transactions)

    return round(
        sum(
            item["amount"]
            for item in commitments
            if item["status"] == "active"
        ),
        2,
    )
