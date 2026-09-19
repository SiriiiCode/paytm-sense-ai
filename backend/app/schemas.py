from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class Transaction(BaseModel):
    transaction_id: str
    date: date
    description: str
    amount: float = Field(gt=0)
    type: Literal["Credit", "Debit"]
    category: str
    recurring: bool

    @field_validator("transaction_id", "description", "category")
    @classmethod
    def must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value


class TransactionCreate(BaseModel):
    date: date
    description: str
    amount: float = Field(gt=0)
    type: Literal["Credit", "Debit"]
    category: str
    recurring: bool = False

    @field_validator("description", "category")
    @classmethod
    def must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value


class RecurringCommitment(BaseModel):
    description: str
    category: str
    amount: float
    frequency: str
    last_seen: date
    days_since_last: int
    status: Literal["active", "inactive"]
    next_expected_date: date | None = None
    overdue_days: int = 0


class SafeToSpendResponse(BaseModel):
    balance: float
    recurring_commitments: float
    savings_goal: float
    emergency_buffer: float
    protected_money: float
    safe_to_spend: float


class CashflowResponse(BaseModel):
    period_start: date | None
    period_end: date | None
    total_income: float
    total_expenses: float
    net_cashflow: float
    average_daily_income: float
    average_daily_expense: float
    monthly: list[dict[str, Any]]
    by_category: list[dict[str, Any]]


class ForecastResponse(BaseModel):
    horizon_days: int
    as_of_date: date | None
    forecast_income: float
    forecast_expenses: float
    forecast_net_cashflow: float
    projected_balance: float
    method: str
    assumptions: list[str]


class IncomeAnalysisResponse(BaseModel):
    prototype_estimate: bool
    current_income: float
    survival_target: float
    comfortable_target: float
    aspirational_target: float
    income_gap: float
    heuristics: list[str]


class FinancialSummaryResponse(BaseModel):
    balance: float
    protected_money: float
    safe_to_spend: float
    recurring_commitments: list[RecurringCommitment]
    savings_goal: float
    emergency_buffer: float
    cashflow: CashflowResponse
    forecast: ForecastResponse
    income_analysis: IncomeAnalysisResponse


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1000)

    @field_validator("message")
    @classmethod
    def message_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("message must not be blank")
        return value


class ChatResponse(BaseModel):
    answer: str
    tool_used: str | None = None
    tool_result: dict[str, Any] | list[dict[str, Any]] | None = None
    ai_provider: str
    memory_context: dict[str, Any] | None = None


class IncomePathway(BaseModel):
    id: Literal["survival", "comfortable", "aspirational"]
    name: str
    target_monthly_income: float
    target_additional_income: float
    description: str


class CareerSkill(BaseModel):
    skill: str
    proficiency: Literal["Beginner", "Intermediate", "Advanced"] = "Beginner"

    @field_validator("skill")
    @classmethod
    def skill_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value


class CareerProfile(BaseModel):
    education_status: str
    highest_qualification: str | None = None
    field_of_study: str | None = None
    graduation_year: int | None = Field(default=None, ge=1950, le=2100)
    employment_status: str
    current_designation: str | None = None
    years_of_experience: float = Field(default=0, ge=0, le=60)
    industry: str | None = None
    previous_experience: str | None = None
    skills: list[CareerSkill] = Field(default_factory=list, min_length=1)
    preferred_job_types: list[str] = Field(default_factory=list)
    preferred_work_mode: str | None = None
    preferred_location: str | None = None
    hours_available_per_week: int | None = Field(default=None, ge=1, le=100)
    minimum_additional_income: float | None = Field(default=None, ge=0)
    industries_of_interest: list[str] = Field(default_factory=list)
    roles_of_interest: list[str] = Field(default_factory=list)
    work_to_avoid: str | None = None
    willingness_to_learn: Literal["Low", "Medium", "High"] = "Medium"
    career_context: str | None = None

    @field_validator("education_status", "employment_status")
    @classmethod
    def required_text_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value


class IncomeGuidanceRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=120)
    pathway_id: Literal["survival", "comfortable", "aspirational"]
    career_profile: CareerProfile
    remember_profile: bool = False

    @field_validator("user_id")
    @classmethod
    def user_id_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value


class RecommendedRole(BaseModel):
    role: str
    why_it_fits: str
    required_skills: list[str] = Field(default_factory=list)
    skills_user_already_has: list[str] = Field(default_factory=list)
    skill_gaps: list[str] = Field(default_factory=list)
    search_queries: list[str] = Field(default_factory=list)


class ActionPlanItem(BaseModel):
    period: str
    actions: list[str]


class MemoryContext(BaseModel):
    enabled: bool
    provider: str
    recalled: bool = False
    remembered: bool = False
    summary: str | None = None
    fallback: bool = False


class IncomeGuidanceResponse(BaseModel):
    selected_pathway: IncomePathway
    profile_summary: str
    recommended_roles: list[RecommendedRole]
    skill_gaps: list[str]
    action_plan: list[ActionPlanItem]
    application_strategy: list[str]
    profile_notes: list[str] = Field(default_factory=list)
    memory_context: MemoryContext
