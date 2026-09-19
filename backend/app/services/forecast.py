from statistics import mean

from ..schemas import Transaction
from .financial import get_balance


def _round(value: float) -> float:
    return round(value, 2)


def _monthly_totals(transactions: list[Transaction], transaction_type: str) -> list[float]:
    totals: dict[str, float] = {}
    for transaction in transactions:
        if transaction.type != transaction_type:
            continue
        month = transaction.date.strftime("%Y-%m")
        totals[month] = totals.get(month, 0.0) + transaction.amount
    return [totals[key] for key in sorted(totals)]


def get_cashflow_forecast(
    transactions: list[Transaction],
    horizon_days: int = 30,
) -> dict:
    if horizon_days <= 0:
        horizon_days = 30

    if not transactions:
        return {
            "horizon_days": horizon_days,
            "as_of_date": None,
            "forecast_income": 0.0,
            "forecast_expenses": 0.0,
            "forecast_net_cashflow": 0.0,
            "projected_balance": get_balance(),
            "method": "moving_average",
            "assumptions": ["No transaction history available."],
        }

    income_months = _monthly_totals(transactions, "Credit")
    expense_months = _monthly_totals(transactions, "Debit")
    window = 3
    income_average = mean(income_months[-window:]) if income_months else 0.0
    expense_average = mean(expense_months[-window:]) if expense_months else 0.0
    scale = horizon_days / 30
    forecast_income = income_average * scale
    forecast_expenses = expense_average * scale
    forecast_net = forecast_income - forecast_expenses

    return {
        "horizon_days": horizon_days,
        "as_of_date": max(transaction.date for transaction in transactions),
        "forecast_income": _round(forecast_income),
        "forecast_expenses": _round(forecast_expenses),
        "forecast_net_cashflow": _round(forecast_net),
        "projected_balance": _round(get_balance() + forecast_net),
        "method": "3-month moving average scaled to horizon",
        "assumptions": [
            "Uses only historical transaction averages.",
            "Does not use an LLM to calculate forecast values.",
            "Synthetic prototype data may not reflect a real user's seasonality.",
        ],
    }
