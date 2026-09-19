from typing import Any

import httpx

from ..config import get_settings
from ..schemas import Transaction
from .financial import get_safe_to_spend
from .recurring import get_recurring_commitments


_LAST_FINANCIAL_STATE: dict[str, Any] | None = None
SAFE_TO_SPEND_CHANGE_THRESHOLD = 1.0


def emit_event(event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    settings = get_settings()
    if not settings.n8n_webhook_url:
        return {"delivered": False, "reason": "N8N_WEBHOOK_URL is not configured"}

    try:
        response = httpx.post(
            settings.n8n_webhook_url,
            json={"event_type": event_type, "payload": payload},
            timeout=5,
        )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        return {"delivered": False, "reason": str(exc)}

    return {"delivered": True, "status_code": response.status_code}


def _active_commitment_signature(commitments: list[dict[str, Any]]) -> dict[str, float]:
    return {
        item["description"].strip().lower(): float(item["amount"])
        for item in commitments
        if item["status"] == "active"
    }


def build_financial_state(transactions: list[Transaction]) -> dict[str, Any]:
    safe_to_spend = get_safe_to_spend(transactions)
    commitments = get_recurring_commitments(transactions)
    active_commitments = _active_commitment_signature(commitments)
    inactive_commitments = [
        item for item in commitments if item["status"] == "inactive"
    ]
    return {
        "safe_to_spend": safe_to_spend["safe_to_spend"],
        "protected_money": safe_to_spend["protected_money"],
        "active_commitments": active_commitments,
        "inactive_commitments": inactive_commitments,
    }


def detect_financial_events(
    current_state: dict[str, Any],
    previous_state: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    if previous_state is None:
        return [
            {
                "event_type": "financial_state_updated",
                "payload": current_state,
            }
        ]

    events: list[dict[str, Any]] = []
    safe_delta = float(current_state["safe_to_spend"]) - float(
        previous_state["safe_to_spend"]
    )
    if abs(safe_delta) >= SAFE_TO_SPEND_CHANGE_THRESHOLD:
        events.append(
            {
                "event_type": "safe_to_spend_changed",
                "payload": {
                    "previous": previous_state["safe_to_spend"],
                    "current": current_state["safe_to_spend"],
                    "delta": round(safe_delta, 2),
                },
            }
        )

    previous_active = previous_state["active_commitments"]
    current_active = current_state["active_commitments"]

    for name, amount in current_active.items():
        if name not in previous_active:
            events.append(
                {
                    "event_type": "active_recurring_commitment_changed",
                    "payload": {"description": name, "amount": amount, "change": "new"},
                }
            )
        elif float(previous_active[name]) != float(amount):
            events.append(
                {
                    "event_type": "active_recurring_commitment_changed",
                    "payload": {
                        "description": name,
                        "previous_amount": previous_active[name],
                        "current_amount": amount,
                        "change": "amount_changed",
                    },
                }
            )

    for name, amount in previous_active.items():
        if name not in current_active:
            events.append(
                {
                    "event_type": "recurring_commitment_became_inactive",
                    "payload": {"description": name, "previous_amount": amount},
                }
            )

    return events


def publish_financial_state_events(
    transactions: list[Transaction],
) -> list[dict[str, Any]]:
    global _LAST_FINANCIAL_STATE

    current_state = build_financial_state(transactions)
    events = detect_financial_events(current_state, _LAST_FINANCIAL_STATE)
    deliveries = [
        {
            "event_type": event["event_type"],
            "delivery": emit_event(event["event_type"], event["payload"]),
        }
        for event in events
    ]
    _LAST_FINANCIAL_STATE = current_state
    return deliveries


def reset_financial_state_cache() -> None:
    global _LAST_FINANCIAL_STATE
    _LAST_FINANCIAL_STATE = None
