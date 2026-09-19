from ..schemas import Transaction
from .cashflow import get_cashflow_metrics
from .financial import get_safe_to_spend
from .forecast import get_cashflow_forecast
from .income import get_income_analysis
from .recurring import get_recurring_commitments


def get_financial_summary(transactions: list[Transaction]) -> dict:
    safe_to_spend = get_safe_to_spend(transactions)
    return {
        "balance": safe_to_spend["balance"],
        "protected_money": safe_to_spend["protected_money"],
        "safe_to_spend": safe_to_spend["safe_to_spend"],
        "recurring_commitments": get_recurring_commitments(transactions),
        "savings_goal": safe_to_spend["savings_goal"],
        "emergency_buffer": safe_to_spend["emergency_buffer"],
        "cashflow": get_cashflow_metrics(transactions),
        "forecast": get_cashflow_forecast(transactions),
        "income_analysis": get_income_analysis(transactions),
    }
