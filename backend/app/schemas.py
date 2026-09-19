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
