from fastapi import HTTPException

from ..ai.career_guidance import generate_career_guidance
from ..schemas import (
    IncomeGuidanceRequest,
    IncomeGuidanceResponse,
    MemoryContext,
)
from .career_memory import build_career_memory_payload, get_career_memory
from .income_pathways import get_income_pathway


def create_income_guidance(
    payload: IncomeGuidanceRequest,
) -> IncomeGuidanceResponse:
    pathway = get_income_pathway(payload.pathway_id)
    if pathway is None:
        raise HTTPException(status_code=404, detail="Selected pathway not found")

    memory = get_career_memory()
    recalled = {"recalled": False, "context": None, "provider": memory.provider_name}
    if payload.remember_profile:
        recalled = memory.recall_career_context(payload.user_id)

    try:
        guidance = generate_career_guidance(
            pathway=pathway,
            profile=payload.career_profile,
            memory_context=recalled.get("context"),
        )
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail="We couldn't analyze your pathway right now.",
        ) from exc

    remembered = {"remembered": False}
    if payload.remember_profile:
        remembered = memory.remember_guidance(
            payload.user_id,
            build_career_memory_payload(
                payload.career_profile,
                pathway,
                guidance,
            ),
        )

    return IncomeGuidanceResponse(
        selected_pathway=pathway,
        profile_summary=guidance["profile_summary"],
        recommended_roles=guidance["recommended_roles"],
        skill_gaps=guidance["skill_gaps"],
        action_plan=guidance["action_plan"],
        application_strategy=guidance["application_strategy"],
        profile_notes=guidance.get("profile_notes", []),
        memory_context=MemoryContext(
            enabled=payload.remember_profile,
            provider=memory.provider_name,
            recalled=bool(recalled.get("recalled")),
            remembered=bool(remembered.get("remembered")),
            summary=_memory_summary(recalled),
            fallback=bool(recalled.get("fallback") or remembered.get("fallback")),
        ),
    )


def _memory_summary(recalled: dict) -> str | None:
    context = recalled.get("context")
    if not context:
        return None
    text = str(context)
    return text[:320]
