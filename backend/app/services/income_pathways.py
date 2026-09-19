from ..schemas import IncomePathway
from .income import get_income_analysis
from .transactions import load_transactions


def _round(value: float) -> float:
    return round(max(value, 0.0), 2)


def get_income_pathways() -> list[IncomePathway]:
    analysis = get_income_analysis(load_transactions())
    current_income = float(analysis["current_income"])
    targets = [
        (
            "survival",
            "Survival Target",
            float(analysis["survival_target"]),
            "Cover essential expenses and active commitments.",
        ),
        (
            "comfortable",
            "Comfortable Target",
            float(analysis["comfortable_target"]),
            "Create breathing room beyond monthly expenses.",
        ),
        (
            "aspirational",
            "Aspirational Target",
            float(analysis["aspirational_target"]),
            "Build a stronger path toward financial growth.",
        ),
    ]

    return [
        IncomePathway(
            id=pathway_id,
            name=name,
            target_monthly_income=_round(target),
            target_additional_income=_round(target - current_income),
            description=description,
        )
        for pathway_id, name, target, description in targets
    ]


def get_income_pathway(pathway_id: str) -> IncomePathway | None:
    for pathway in get_income_pathways():
        if pathway.id == pathway_id:
            return pathway
    return None
