import json
from typing import Any, Protocol

import httpx

from ..config import get_settings
from ..schemas import CareerProfile, IncomePathway


class CareerMemory(Protocol):
    provider_name: str

    def remember_guidance(
        self,
        user_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        ...

    def recall_career_context(self, user_id: str) -> dict[str, Any]:
        ...


class DisabledCareerMemory:
    provider_name = "disabled"

    def remember_guidance(
        self,
        user_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        del user_id, payload
        return {"remembered": False, "provider": self.provider_name}

    def recall_career_context(self, user_id: str) -> dict[str, Any]:
        del user_id
        return {"recalled": False, "provider": self.provider_name, "context": None}


class InMemoryCareerMemory:
    provider_name = "local-in-memory"

    def __init__(self) -> None:
        self._items: dict[str, list[dict[str, Any]]] = {}

    def remember_guidance(
        self,
        user_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        self._items.setdefault(user_id, []).append(payload)
        return {"remembered": True, "provider": self.provider_name}

    def recall_career_context(self, user_id: str) -> dict[str, Any]:
        items = self._items.get(user_id, [])
        return {
            "recalled": bool(items),
            "provider": self.provider_name,
            "context": items[-3:],
        }


class CogneeHttpCareerMemory:
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
        return {"X-Api-Key": self.api_key}

    def _add_dataset_selector(self) -> dict[str, str]:
        if self.dataset_id:
            return {"datasetId": self.dataset_id}
        return {"datasetName": self.dataset}

    def _query_dataset_selector(self) -> dict[str, list[str]]:
        if self.dataset_id:
            return {"datasetIds": [self.dataset_id]}
        return {"datasets": [self.dataset]}

    def remember_guidance(
        self,
        user_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        memory_text = (
            f"Paytm Sense career memory for user:{user_id}: "
            f"{json.dumps(payload, sort_keys=True)}"
        )
        add_response = httpx.post(
            f"{self.base_url}/api/v1/add",
            headers=self._headers,
            data=self._add_dataset_selector(),
            files=[
                (
                    "data",
                    (
                        "career_guidance.txt",
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
            json={"run_in_background": False, **self._query_dataset_selector()},
            timeout=60,
        )
        cognify_response.raise_for_status()
        return {
            "remembered": True,
            "provider": self.provider_name,
            "dataset": self.dataset,
        }

    def recall_career_context(self, user_id: str) -> dict[str, Any]:
        response = httpx.post(
            f"{self.base_url}/api/v1/search",
            headers=self._headers,
            json={
                "query": (
                    f"Recall career profile, skills, goals, income pathway, "
                    f"skill gaps, and preferred roles for user:{user_id}."
                ),
                "search_type": "GRAPH_COMPLETION",
                "top_k": 10,
                **self._query_dataset_selector(),
            },
            timeout=20,
        )
        response.raise_for_status()
        return {
            "recalled": True,
            "provider": self.provider_name,
            "context": response.json(),
        }


class SafeFallbackCareerMemory:
    provider_name = "cognee-with-local-fallback"

    def __init__(
        self,
        primary: CareerMemory,
        fallback: CareerMemory,
    ) -> None:
        self.primary = primary
        self.fallback = fallback

    def remember_guidance(
        self,
        user_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        try:
            return self.primary.remember_guidance(user_id, payload)
        except (httpx.HTTPError, OSError, TypeError, ValueError) as exc:
            result = self.fallback.remember_guidance(user_id, payload)
            return {
                **result,
                "fallback": True,
                "primary_provider": self.primary.provider_name,
                "fallback_reason": str(exc),
            }

    def recall_career_context(self, user_id: str) -> dict[str, Any]:
        try:
            return self.primary.recall_career_context(user_id)
        except (httpx.HTTPError, OSError, TypeError, ValueError) as exc:
            result = self.fallback.recall_career_context(user_id)
            return {
                **result,
                "fallback": True,
                "primary_provider": self.primary.provider_name,
                "fallback_reason": str(exc),
            }


def build_career_memory_payload(
    profile: CareerProfile,
    pathway: IncomePathway,
    guidance: dict[str, Any],
) -> dict[str, Any]:
    return {
        "career_profile": profile.model_dump(),
        "selected_pathway": pathway.model_dump(),
        "recommended_roles": guidance.get("recommended_roles", []),
        "skill_gaps": guidance.get("skill_gaps", []),
        "action_plan": guidance.get("action_plan", []),
    }


def get_career_memory() -> CareerMemory:
    settings = get_settings()
    if settings.cognee_api_key:
        return SafeFallbackCareerMemory(
            primary=CogneeHttpCareerMemory(
                api_key=settings.cognee_api_key,
                base_url=settings.cognee_base_url,
                dataset=settings.career_memory_dataset,
                dataset_id=settings.career_memory_dataset_id,
            ),
            fallback=DisabledCareerMemory(),
        )
    return DisabledCareerMemory()
