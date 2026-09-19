import json
from typing import Any, Protocol

import httpx

from ..config import get_settings


class FinancialMemory(Protocol):
    provider_name: str

    def remember_goal(self, goal: dict[str, Any]) -> dict[str, Any]:
        ...

    def recall_goals(self) -> dict[str, Any]:
        ...


class InMemoryFinancialMemory:
    provider_name = "local-in-memory"

    def __init__(self) -> None:
        self._goals: list[dict[str, Any]] = []

    def remember_goal(self, goal: dict[str, Any]) -> dict[str, Any]:
        self._goals.append(goal)
        return {
            "remembered": True,
            "provider": self.provider_name,
            "goal": goal,
        }

    def recall_goals(self) -> dict[str, Any]:
        return {
            "provider": self.provider_name,
            "goals": list(self._goals),
        }


class CogneeHttpFinancialMemory:
    provider_name = "cognee-http"

    def __init__(
        self,
        api_key: str,
        base_url: str,
        dataset: str,
        dataset_id: str | None = None,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.dataset = dataset
        self.dataset_id = dataset_id

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "X-Api-Key": self.api_key,
        }

    def _add_dataset_selector(self) -> dict[str, str]:
        if self.dataset_id:
            return {"datasetId": self.dataset_id}
        return {"datasetName": self.dataset}

    def _query_dataset_selector(self) -> dict[str, list[str]]:
        if self.dataset_id:
            return {"datasetIds": [self.dataset_id]}
        return {"datasets": [self.dataset]}

    def remember_goal(self, goal: dict[str, Any]) -> dict[str, Any]:
        memory_text = f"Paytm Sense financial goal: {json.dumps(goal, sort_keys=True)}"
        add_response = httpx.post(
            f"{self.base_url}/api/v1/add",
            headers=self._headers,
            data=self._add_dataset_selector(),
            files=[
                (
                    "data",
                    (
                        "financial_goal.txt",
                        memory_text.encode("utf-8"),
                        "text/plain",
                    ),
                )
            ],
            timeout=20,
        )
        add_response.raise_for_status()

        cognify_response = httpx.post(
            f"{self.base_url}/api/v1/cognify",
            headers=self._headers,
            json={
                "run_in_background": False,
                **self._query_dataset_selector(),
            },
            timeout=60,
        )
        cognify_response.raise_for_status()

        return {
            "remembered": True,
            "provider": self.provider_name,
            "dataset": self.dataset,
            "dataset_id": self.dataset_id,
            "goal": goal,
        }

    def recall_goals(self) -> dict[str, Any]:
        response = httpx.post(
            f"{self.base_url}/api/v1/search",
            headers=self._headers,
            json={
                "query": "Recall the user's Paytm Sense financial goals and intentions.",
                "search_type": "GRAPH_COMPLETION",
                "top_k": 15,
                **self._query_dataset_selector(),
            },
            timeout=20,
        )
        response.raise_for_status()
        return {
            "provider": self.provider_name,
            "dataset": self.dataset,
            "dataset_id": self.dataset_id,
            "goals": response.json(),
        }


class SafeFallbackFinancialMemory:
    provider_name = "cognee-with-local-fallback"

    def __init__(
        self,
        primary: FinancialMemory,
        fallback: InMemoryFinancialMemory,
    ) -> None:
        self.primary = primary
        self.fallback = fallback

    def remember_goal(self, goal: dict[str, Any]) -> dict[str, Any]:
        try:
            return self.primary.remember_goal(goal)
        except (httpx.HTTPError, OSError, ValueError, TypeError) as exc:
            fallback_result = self.fallback.remember_goal(goal)
            return {
                **fallback_result,
                "provider": self.fallback.provider_name,
                "fallback": True,
                "primary_provider": self.primary.provider_name,
                "fallback_reason": str(exc),
            }

    def recall_goals(self) -> dict[str, Any]:
        try:
            return self.primary.recall_goals()
        except (httpx.HTTPError, OSError, ValueError, TypeError) as exc:
            fallback_result = self.fallback.recall_goals()
            return {
                **fallback_result,
                "provider": self.fallback.provider_name,
                "fallback": True,
                "primary_provider": self.primary.provider_name,
                "fallback_reason": str(exc),
            }


_LOCAL_MEMORY = InMemoryFinancialMemory()


def get_memory() -> FinancialMemory:
    settings = get_settings()
    if settings.cognee_api_key:
        return SafeFallbackFinancialMemory(
            primary=CogneeHttpFinancialMemory(
                api_key=settings.cognee_api_key,
                base_url=settings.cognee_base_url,
                dataset=settings.cognee_dataset,
                dataset_id=settings.cognee_dataset_id,
            ),
            fallback=_LOCAL_MEMORY,
        )
    return _LOCAL_MEMORY
