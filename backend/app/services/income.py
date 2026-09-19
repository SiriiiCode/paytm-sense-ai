from statistics import mean

from ..schemas import Transaction
from .recurring import get_recurring_commitment_total

ESSENTIAL_CATEGORIES = {"Housing", "EMI", "Utilities", "Groceries", "Healthcare"}


def _round(value: float) -> float:
    return round(value, 2)


def _monthly_amounts(
    transactions: list[Transaction],
    transaction_type: str,
    categories: set[str] | None = None,
) -> list[float]:
    totals: dict[str, float] = {}
    for transaction in transactions:
        if transaction.type != transaction_type:
            continue
        if categories is not None and transaction.category not in categories:
            continue
        month = transaction.date.strftime("%Y-%m")
        totals[month] = totals.get(month, 0.0) + transaction.amount
    return [totals[key] for key in sorted(totals)]


def get_income_analysis(transactions: list[Transaction]) -> dict:
    income_months = _monthly_amounts(transactions, "Credit")
    essential_months = _monthly_amounts(
        transactions,
        "Debit",
        ESSENTIAL_CATEGORIES,
    )
    expense_months = _monthly_amounts(transactions, "Debit")

    current_income = mean(income_months[-3:]) if income_months else 0.0
    essential_average = mean(essential_months[-3:]) if essential_months else 0.0
    expense_average = mean(expense_months[-3:]) if expense_months else 0.0
    recurring_total = get_recurring_commitment_total(transactions)

    survival_target = max(essential_average, recurring_total)
    comfortable_target = max(expense_average * 1.1, survival_target * 1.25)
    aspirational_target = comfortable_target * 1.25

    return {
        "prototype_estimate": True,
        "current_income": _round(current_income),
        "survival_target": _round(survival_target),
        "comfortable_target": _round(comfortable_target),
        "aspirational_target": _round(aspirational_target),
        "income_gap": _round(max(comfortable_target - current_income, 0.0)),
        "heuristics": [
            "Current income is the average monthly credit over the latest 3 months.",
            "Survival target is the higher of essential spend average and active recurring commitments.",
            "Comfortable target is the higher of 110% of average spend and 125% of survival target.",
            "Aspirational target is 125% of comfortable target.",
        ],
    }
