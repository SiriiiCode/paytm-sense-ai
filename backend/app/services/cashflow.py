from collections import defaultdict
from datetime import date

from ..schemas import Transaction
from .financial import get_net_cashflow


def _round(value: float) -> float:
    return round(value, 2)


def get_cashflow_metrics(transactions: list[Transaction]) -> dict:
    if not transactions:
        return {
            "period_start": None,
            "period_end": None,
            "total_income": 0.0,
            "total_expenses": 0.0,
            "net_cashflow": 0.0,
            "average_daily_income": 0.0,
            "average_daily_expense": 0.0,
            "monthly": [],
            "by_category": [],
        }

    period_start = min(transaction.date for transaction in transactions)
    period_end = max(transaction.date for transaction in transactions)
    days = max((period_end - period_start).days + 1, 1)

    income = sum(
        transaction.amount for transaction in transactions if transaction.type == "Credit"
    )
    expenses = sum(
        transaction.amount for transaction in transactions if transaction.type == "Debit"
    )

    monthly: dict[str, dict[str, float | str]] = defaultdict(
        lambda: {"month": "", "income": 0.0, "expenses": 0.0, "net": 0.0}
    )
    by_category: dict[str, float] = defaultdict(float)

    for transaction in transactions:
        month = transaction.date.strftime("%Y-%m")
        monthly[month]["month"] = month
        if transaction.type == "Credit":
            monthly[month]["income"] += transaction.amount
        else:
            monthly[month]["expenses"] += transaction.amount
            by_category[transaction.category] += transaction.amount
        monthly[month]["net"] = (
            float(monthly[month]["income"]) - float(monthly[month]["expenses"])
        )

    monthly_rows = [
        {
            "month": item["month"],
            "income": _round(float(item["income"])),
            "expenses": _round(float(item["expenses"])),
            "net": _round(float(item["net"])),
        }
        for item in sorted(monthly.values(), key=lambda row: str(row["month"]))
    ]

    category_rows = [
        {"category": category, "amount": _round(amount)}
        for category, amount in sorted(
            by_category.items(),
            key=lambda item: item[1],
            reverse=True,
        )
    ]

    return {
        "period_start": period_start,
        "period_end": period_end,
        "total_income": _round(income),
        "total_expenses": _round(expenses),
        "net_cashflow": get_net_cashflow(transactions),
        "average_daily_income": _round(income / days),
        "average_daily_expense": _round(expenses / days),
        "monthly": monthly_rows,
        "by_category": category_rows,
    }


def get_spending_analysis(transactions: list[Transaction]) -> dict:
    cashflow = get_cashflow_metrics(transactions)
    return {
        "top_categories": cashflow["by_category"][:5],
        "total_expenses": cashflow["total_expenses"],
        "period_start": cashflow["period_start"],
        "period_end": cashflow["period_end"],
    }
