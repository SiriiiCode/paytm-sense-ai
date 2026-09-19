import re
from typing import Any

from .client import AIClient, RuleBasedAIClient, get_ai_client
from .tools import execute_tool, get_tool_schemas


def select_local_tool(message: str) -> tuple[str, dict[str, Any]]:
    text = message.lower()
    remembered_goal = _extract_goal(message)
    if remembered_goal:
        return "remember_financial_goal", remembered_goal
    if any(word in text for word in ["goal", "remember", "saving for"]):
        return "recall_financial_goals", {}
    if any(word in text for word in ["recurring", "commitment", "subscription", "emi"]):
        return "get_upcoming_commitments", {}
    if any(word in text for word in ["income", "salary", "earn", "target"]):
        return "get_ideal_income", {}
    if any(word in text for word in ["spending most", "where am i spending", "category"]):
        return "get_spending_analysis", {}
    if any(word in text for word in ["forecast", "future", "next month"]):
        return "get_cashflow_forecast", {}
    if any(word in text for word in ["cashflow", "cash flow"]):
        return "get_cashflow", {}
    if any(word in text for word in ["safe", "spend", "buy", "afford"]):
        return "get_safe_to_spend", {}
    return "get_financial_summary", {}


def _extract_goal(message: str) -> dict[str, Any] | None:
    text = message.lower()
    if not any(word in text for word in ["saving", "save", "goal", "remember"]):
        return None
    if not any(word in text for word in ["for", "towards", "toward"]):
        return None

    amount_match = re.search(r"(?:rs\.?|inr|₹)?\s*([0-9][0-9,]*(?:\.\d+)?)", text)
    target_amount = None
    if amount_match:
        target_amount = float(amount_match.group(1).replace(",", ""))

    description = message.strip()
    return {
        "description": description,
        "target_amount": target_amount,
        "currency": "INR",
    }


def _requested_spend(message: str) -> float | None:
    match = re.search(r"(?:rs\.?|inr|₹)?\s*([0-9][0-9,]*(?:\.\d+)?)", message.lower())
    if not match:
        return None
    return float(match.group(1).replace(",", ""))


def _answer_spend_decision(message: str, tool_result: dict[str, Any]) -> str | None:
    requested = _requested_spend(message)
    if requested is None:
        return None

    safe_to_spend = float(tool_result["safe_to_spend"])
    if requested <= safe_to_spend:
        remaining = safe_to_spend - requested
        return (
            "### AFFORDABILITY\n"
            f"- Purchase: Rs {requested:.2f}\n"
            f"- Safe to spend: Rs {safe_to_spend:.2f}\n"
            f"- Remaining after purchase: Rs {remaining:.2f}\n"
            f"- Protected money remains: Rs {float(tool_result['protected_money']):.2f}\n\n"
            "### RECOMMENDATION\n"
            "- Yes, this purchase is within your safe-to-spend limit."
        )
    gap = requested - safe_to_spend
    return (
        "### AFFORDABILITY\n"
        f"- Purchase: Rs {requested:.2f}\n"
        f"- Safe to spend: Rs {safe_to_spend:.2f}\n"
        f"- Gap: Rs {gap:.2f}\n\n"
        "### RECOMMENDATION\n"
        "- Not safely. This purchase is above your safe-to-spend limit."
    )


def _append_memory_context(answer: str) -> tuple[str, dict[str, Any]]:
    memory_context = execute_tool("recall_financial_goals", {})
    goals = memory_context.get("goals") if isinstance(memory_context, dict) else None
    if goals:
        answer = f"{answer} I also found saved financial context: {goals}."
    return answer, memory_context


def answer_chat(
    message: str,
    ai_client: AIClient | None = None,
) -> dict[str, Any]:
    client = ai_client or get_ai_client()

    try:
        result = client.answer_with_tools(
            message=message,
            tool_schemas=get_tool_schemas(),
            execute_tool=execute_tool,
        )
    except Exception:
        fallback = RuleBasedAIClient()
        result = fallback.answer_with_tools(
            message=message,
            tool_schemas=get_tool_schemas(),
            execute_tool=execute_tool,
        )
        client = fallback

    memory_context = None
    if result["tool_used"] == "get_safe_to_spend":
        deterministic_answer = _answer_spend_decision(
            message,
            result["tool_result"],
        )
        if deterministic_answer:
            result["answer"] = deterministic_answer
        result["answer"], memory_context = _append_memory_context(result["answer"])

    return {
        "answer": result["answer"],
        "tool_used": result["tool_used"],
        "tool_result": result["tool_result"],
        "ai_provider": client.provider_name,
        "memory_context": memory_context,
    }
