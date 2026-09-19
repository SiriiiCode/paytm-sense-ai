import json
from typing import Any

import httpx
from ..config import get_settings
from ..schemas import (
    ActionPlanItem,
    CareerProfile,
    IncomePathway,
    RecommendedRole,
)


def generate_career_guidance(
    pathway: IncomePathway,
    profile: CareerProfile,
    memory_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    settings = get_settings()
    if not settings.groq_api_key:
        return _local_guidance(pathway, profile, memory_context)

    system = (
        "You are Paytm Sense Income Pathways. Return only valid JSON. "
        "Do not calculate financial targets; use the provided pathway values. "
        "Recommend realistic career/job pathways based on the profile, skills, "
        "preferences, and recalled memory. Do not invent companies, salaries, "
        "application links, or claim access to current vacancies. Produce 3 to 5 "
        "recommended roles."
    )
    payload = {
        "selected_pathway": pathway.model_dump(),
        "career_profile": profile.model_dump(),
        "recalled_memory": memory_context,
        "required_schema": {
            "profile_summary": "short string",
            "recommended_roles": [
                {
                    "role": "string",
                    "why_it_fits": "string",
                    "required_skills": ["string"],
                    "skills_user_already_has": ["string"],
                    "skill_gaps": ["string"],
                    "search_queries": ["string"],
                }
            ],
            "skill_gaps": ["string"],
            "action_plan": [{"period": "string", "actions": ["string"]}],
            "application_strategy": ["string"],
            "profile_notes": ["string"],
        },
    }

    response = httpx.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {settings.groq_api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": settings.groq_model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": json.dumps(payload, sort_keys=True)},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.2,
        },
        timeout=40,
    )
    response.raise_for_status()
    content = response.json()["choices"][0]["message"].get("content") or "{}"
    return _validate_guidance(json.loads(content))


def _validate_guidance(payload: dict[str, Any]) -> dict[str, Any]:
    roles = [
        RecommendedRole(**role).model_dump()
        for role in payload.get("recommended_roles", [])
    ][:5]
    action_plan = [
        ActionPlanItem(**item).model_dump()
        for item in payload.get("action_plan", [])
    ][:5]
    if not roles:
        raise ValueError("At least one recommended role is required")
    return {
        "profile_summary": str(payload.get("profile_summary") or ""),
        "recommended_roles": roles,
        "skill_gaps": _unique_strings(payload.get("skill_gaps", []))[:12],
        "action_plan": action_plan,
        "application_strategy": _unique_strings(
            payload.get("application_strategy", [])
        )[:8],
        "profile_notes": _unique_strings(payload.get("profile_notes", []))[:8],
    }


def _local_guidance(
    pathway: IncomePathway,
    profile: CareerProfile,
    memory_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    del memory_context
    user_skills = [item.skill for item in profile.skills]
    normalized = {skill.lower() for skill in user_skills}
    interests = profile.roles_of_interest or profile.industries_of_interest
    base_role = interests[0] if interests else _infer_role(normalized)
    roles = [
        _role(
            base_role,
            "Matches your stated interests and available profile context.",
            ["Communication", "Portfolio", "Client coordination"],
            user_skills,
            ["Portfolio proof", "Role-specific projects"],
        ),
        _role(
            "Freelance " + base_role,
            "Can fit around your available hours while pursuing additional income.",
            ["Proposal writing", "Pricing", "Delivery planning"],
            user_skills,
            ["Client acquisition", "Work samples"],
        ),
        _role(
            "Junior " + base_role,
            "A realistic entry pathway if you build proof of work and fill core gaps.",
            ["Foundational tools", "Interview basics", "Applied projects"],
            user_skills,
            ["Interview preparation", "Applied project depth"],
        ),
    ]
    skill_gaps = _unique_strings(
        gap for role in roles for gap in role["skill_gaps"]
    )
    return {
        "profile_summary": (
            f"Your profile can target {pathway.name.lower()} by focusing on "
            f"roles aligned with {', '.join(user_skills[:4]) or 'your current skills'}."
        ),
        "recommended_roles": roles,
        "skill_gaps": skill_gaps,
        "action_plan": [
            {
                "period": "Week 1",
                "actions": [
                    "Pick one target role and collect 3 relevant job descriptions.",
                    "Map your current skills against the repeated requirements.",
                ],
            },
            {
                "period": "Weeks 2-3",
                "actions": [
                    "Build one small proof-of-work project.",
                    "Close the top two skill gaps from the role cards.",
                ],
            },
            {
                "period": "Week 4",
                "actions": [
                    "Apply to focused roles with a tailored profile.",
                    "Track responses and refine the search queries.",
                ],
            },
        ],
        "application_strategy": [
            "Use the role search queries as keywords for your own applications.",
            "Prioritize roles that match your preferred work mode and hours.",
            "Show proof of skills instead of listing skills only.",
        ],
        "profile_notes": [
            "Guidance used backend income targets and your submitted career profile.",
        ],
    }


def _infer_role(skills: set[str]) -> str:
    if {"react", "javascript", "html", "css"} & skills:
        return "Frontend Developer"
    if {"python", "sql", "excel"} & skills:
        return "Data Analyst"
    if {"figma", "canva", "design"} & skills:
        return "Designer"
    if {"sales", "communication"} & skills:
        return "Sales Associate"
    return "Operations Associate"


def _role(
    role: str,
    why: str,
    required: list[str],
    user_skills: list[str],
    gaps: list[str],
) -> dict[str, Any]:
    return RecommendedRole(
        role=role,
        why_it_fits=why,
        required_skills=required,
        skills_user_already_has=user_skills[:6],
        skill_gaps=gaps,
        search_queries=[
            role,
            f"entry level {role}",
            f"remote {role}",
        ],
    ).model_dump()


def _unique_strings(items) -> list[str]:
    seen = set()
    result = []
    for item in items:
        text = str(item).strip()
        key = text.lower()
        if text and key not in seen:
            seen.add(key)
            result.append(text)
    return result
