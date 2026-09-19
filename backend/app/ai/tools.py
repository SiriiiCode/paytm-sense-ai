from typing import Any, Callable

from ..services.cashflow import get_cashflow_metrics, get_spending_analysis
from ..services.financial import get_safe_to_spend
from ..services.forecast import get_cashflow_forecast
from ..services.income import get_income_analysis
from ..services.memory import get_memory
from ..services.recurring import get_recurring_commitments
from ..services.summary import get_financial_summary
from ..services.transactions import load_transactions


ToolFn = Callable[[dict[str, Any]], dict[str, Any] | list[dict[str, Any]]]


def _transactions():
    return load_transactions()


def _remember_financial_goal(arguments: dict[str, Any]) -> dict[str, Any]:
    goal = {
        "description": arguments["description"],
        "target_amount": arguments.get("target_amount"),
        "currency": arguments.get("currency", "INR"),
    }
    return get_memory().remember_goal(goal)


def _recall_financial_goals(arguments: dict[str, Any]) -> dict[str, Any]:
    del arguments
    return get_memory().recall_goals()


def get_tools() -> dict[str, ToolFn]:
    return {
        "get_financial_summary": lambda args: get_financial_summary(_transactions()),
        "get_safe_to_spend": lambda args: get_safe_to_spend(_transactions()),
        "get_upcoming_commitments": lambda args: get_recurring_commitments(_transactions()),
        "get_spending_analysis": lambda args: get_spending_analysis(_transactions()),
        "get_cashflow_forecast": lambda args: get_cashflow_forecast(_transactions()),
        "get_ideal_income": lambda args: get_income_analysis(_transactions()),
        "get_cashflow": lambda args: get_cashflow_metrics(_transactions()),
        "remember_financial_goal": _remember_financial_goal,
        "recall_financial_goals": _recall_financial_goals,
    }


def get_tool_schemas() -> list[dict[str, Any]]:
    no_args = {"type": "object", "properties": {}, "additionalProperties": False}
    return [
        {
            "type": "function",
            "function": {
                "name": "get_financial_summary",
                "description": "Get deterministic dashboard-level financial summary.",
                "parameters": no_args,
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_safe_to_spend",
                "description": "Get deterministic safe-to-spend values and protected money.",
                "parameters": no_args,
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_upcoming_commitments",
                "description": "Get recurring commitments detected by backend logic.",
                "parameters": no_args,
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_spending_analysis",
                "description": "Get deterministic spending totals by category.",
                "parameters": no_args,
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_cashflow_forecast",
                "description": "Get deterministic moving-average cashflow forecast.",
                "parameters": no_args,
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_ideal_income",
                "description": "Get prototype income targets from backend heuristics.",
                "parameters": no_args,
            },
        },
        {
            "type": "function",
            "function": {
                "name": "remember_financial_goal",
                "description": "Store a user financial goal or intention in memory.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "description": {"type": "string"},
                        "target_amount": {"type": ["number", "null"]},
                        "currency": {"type": "string", "default": "INR"},
                    },
                    "required": ["description"],
                    "additionalProperties": False,
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "recall_financial_goals",
                "description": "Recall saved user financial goals and preferences.",
                "parameters": no_args,
            },
        },
    ]


def execute_tool(
    tool_name: str,
    arguments: dict[str, Any] | None = None,
) -> dict[str, Any] | list[dict[str, Any]]:
    tools = get_tools()
    if tool_name not in tools:
        raise ValueError(f"Unknown tool: {tool_name}")
    return tools[tool_name](arguments or {})
