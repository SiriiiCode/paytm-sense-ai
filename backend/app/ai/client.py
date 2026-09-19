import json
from datetime import date, datetime
from typing import Any, Protocol

import httpx

from ..config import get_settings


class ToolCallingResult(dict):
    answer: str
    tool_used: str | None
    tool_result: Any


class AIClient(Protocol):
    provider_name: str

    def answer_with_tools(
        self,
        message: str,
        tool_schemas: list[dict[str, Any]],
        execute_tool,
    ) -> dict[str, Any]:
        ...


def _json_default(value: Any) -> str:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return str(value)


class RuleBasedAIClient:
    provider_name = "local-rule-based"

    def complete_from_tool(
        self,
        message: str,
        tool_name: str,
        tool_result: Any,
    ) -> str:
        del message

        if tool_name == "get_safe_to_spend":
            return (
                f"You can safely spend Rs {tool_result['safe_to_spend']:.2f}. "
                f"That keeps Rs {tool_result['protected_money']:.2f} protected for "
                "active commitments, savings, and emergency buffer."
            )

        if tool_name == "get_upcoming_commitments":
            active = [
                item
                for item in tool_result
                if item["status"] == "active"
            ]

            if not active:
                return (
                    "I do not see active recurring commitments "
                    "in the current data."
                )

            names = ", ".join(
                f"{item['description']} (Rs {item['amount']:.2f})"
                for item in active[:5]
            )

            return (
                f"Your active recurring commitments are: {names}."
            )

        if tool_name == "get_ideal_income":
            return (
                "Prototype income targets: "
                f"survival Rs {tool_result['survival_target']:.2f}, "
                f"comfortable Rs {tool_result['comfortable_target']:.2f}, "
                f"aspirational Rs {tool_result['aspirational_target']:.2f}. "
                f"Your current income gap to comfortable is "
                f"Rs {tool_result['income_gap']:.2f}."
            )

        if tool_name == "get_spending_analysis":
            top = (
                tool_result["top_categories"][0]
                if tool_result["top_categories"]
                else None
            )

            if top:
                return (
                    f"You are spending the most on {top['category']} "
                    f"at Rs {top['amount']:.2f} in the available history."
                )

            return (
                "I do not see debit transactions to analyze yet."
            )

        if tool_name == "get_cashflow_forecast":
            return (
                f"Using {tool_result['method']}, the next "
                f"{tool_result['horizon_days']} days forecast net cashflow "
                f"is Rs {tool_result['forecast_net_cashflow']:.2f}."
            )

        if tool_name == "get_cashflow":
            return (
                "Your historical cash flow for the available data is: "
                f"income Rs {tool_result['total_income']:.2f}, "
                f"expenses Rs {tool_result['total_expenses']:.2f}, "
                f"net cashflow Rs {tool_result['net_cashflow']:.2f}."
            )

        if tool_name == "remember_financial_goal":
            return (
                "I remembered that financial goal for future "
                "Paytm Sense answers."
            )

        if tool_name == "recall_financial_goals":
            goals = tool_result.get("goals") or []

            if not goals:
                return (
                    "I do not have any saved financial goals yet."
                )

            return (
                f"I found saved financial context: {goals}."
            )

        return (
            f"Your balance is Rs {tool_result['balance']:.2f}, "
            f"protected money is Rs {tool_result['protected_money']:.2f}, "
            f"and safe-to-spend is "
            f"Rs {tool_result['safe_to_spend']:.2f}."
        )

    def answer_with_tools(
        self,
        message: str,
        tool_schemas: list[dict[str, Any]],
        execute_tool,
    ) -> dict[str, Any]:
        del tool_schemas

        from .agent import select_local_tool

        tool_name, arguments = select_local_tool(message)

        tool_result = execute_tool(
            tool_name,
            arguments,
        )

        return {
            "answer": self.complete_from_tool(
                message,
                tool_name,
                tool_result,
            ),
            "tool_used": tool_name,
            "tool_result": tool_result,
        }


class GroqAIClient:
    provider_name = "groq"

    def __init__(
        self,
        api_key: str,
        model: str,
    ) -> None:
        self.api_key = api_key
        self.model = model

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _chat(
        self,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        response = httpx.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers=self._headers,
            json=payload,
            timeout=30,
        )

        response.raise_for_status()

        return response.json()

    def answer_with_tools(
        self,
        message: str,
        tool_schemas: list[dict[str, Any]],
        execute_tool,
    ) -> dict[str, Any]:
        system = (
            "You are Paytm Sense. Use the provided tools whenever "
            "financial data, memory, goals, or spending decisions "
            "are needed. Never invent financial numbers. "
            "Backend tool results are authoritative."
        )

        messages: list[dict[str, Any]] = [
            {
                "role": "system",
                "content": system,
            },
            {
                "role": "user",
                "content": message,
            },
        ]

        used_tools: list[str] = []
        tool_results: list[Any] = []

        max_iterations = 5

        for _ in range(max_iterations):
            response = self._chat(
                {
                    "model": self.model,
                    "messages": messages,
                    "tools": tool_schemas,
                    "tool_choice": "auto",
                    "temperature": 0.1,
                }
            )

            assistant_message = (
                response["choices"][0]["message"]
            )

            tool_calls = (
                assistant_message.get("tool_calls")
                or []
            )

            # No tool call means the model is ready
            # to return its final answer.
            if not tool_calls:
                return {
                    "answer": (
                        assistant_message.get("content")
                        or (
                            "I need a backend tool result "
                            "to answer that safely."
                        )
                    ),
                    "tool_used": (
                        used_tools[0]
                        if len(used_tools) == 1
                        else ",".join(used_tools)
                        if used_tools
                        else None
                    ),
                    "tool_result": (
                        tool_results[0]
                        if len(tool_results) == 1
                        else tool_results
                        if tool_results
                        else None
                    ),
                }

            # Preserve the assistant message that
            # contains the tool-call request(s).
            messages.append(assistant_message)

            # Execute every tool requested in this turn.
            for tool_call in tool_calls:
                function = tool_call["function"]

                tool_name = function["name"]

                raw_arguments = (
                    function.get("arguments")
                    or "{}"
                )

                arguments = json.loads(
                    raw_arguments
                )

                tool_result = execute_tool(
                    tool_name,
                    arguments,
                )

                used_tools.append(tool_name)
                tool_results.append(tool_result)

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call["id"],
                        "name": tool_name,
                        "content": json.dumps(
                            tool_result,
                            default=_json_default,
                        ),
                    }
                )

        raise RuntimeError(
            "Groq tool-calling loop exceeded the "
            "maximum number of iterations."
        )


def get_ai_client() -> AIClient:
    settings = get_settings()

    if settings.groq_api_key:
        return GroqAIClient(
            settings.groq_api_key,
            settings.groq_model,
        )

    return RuleBasedAIClient()
