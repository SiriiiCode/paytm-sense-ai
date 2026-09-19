from fastapi import APIRouter, status

from ..ai.agent import answer_chat
from ..schemas import (
    CashflowResponse,
    ChatRequest,
    ChatResponse,
    FinancialSummaryResponse,
    ForecastResponse,
    IncomeGuidanceRequest,
    IncomeGuidanceResponse,
    IncomePathway,
    IncomeAnalysisResponse,
    RecurringCommitment,
    SafeToSpendResponse,
    Transaction,
    TransactionCreate,
)
from ..services.cashflow import get_cashflow_metrics
from ..services.automation import publish_financial_state_events
from ..services.financial import get_safe_to_spend
from ..services.forecast import get_cashflow_forecast
from ..services.income import get_income_analysis
from ..services.career_guidance import create_income_guidance
from ..services.income_pathways import get_income_pathways
from ..services.recurring import get_recurring_commitments
from ..services.summary import get_financial_summary
from ..services.transactions import create_transaction, load_transactions


router = APIRouter()


@router.get("/transactions", response_model=list[Transaction])
def list_transactions():
    return load_transactions()


@router.post(
    "/transactions",
    response_model=Transaction,
    status_code=status.HTTP_201_CREATED,
)
def add_transaction(payload: TransactionCreate):
    transaction = create_transaction(payload)
    publish_financial_state_events(load_transactions())
    return transaction


@router.get("/safe-to-spend", response_model=SafeToSpendResponse)
def safe_to_spend():
    transactions = load_transactions()
    result = get_safe_to_spend(transactions)
    publish_financial_state_events(transactions)

    return result


@router.get("/financial-summary", response_model=FinancialSummaryResponse)
def financial_summary():
    transactions = load_transactions()
    result = get_financial_summary(transactions)
    publish_financial_state_events(transactions)
    return result


@router.get("/cashflow", response_model=CashflowResponse)
def cashflow():
    transactions = load_transactions()
    return get_cashflow_metrics(transactions)

@router.get("/cash-flow-forecast")
def cash_flow_forecast():
    transactions = load_transactions()

    summary = get_financial_summary(transactions)

    # Convert Pydantic model to dictionary if necessary
    if hasattr(summary, "model_dump"):
        summary_data = summary.model_dump()
    else:
        summary_data = summary

    balance = summary_data.get("balance", 0)
    commitments = summary_data.get("recurring_commitments", [])

    projected_balance = balance
    forecast = []

    for commitment in commitments:
        if commitment.get("status") != "active":
            continue

        amount = commitment.get("amount", 0)
        projected_balance -= amount

        forecast.append({
            "description": commitment.get("description"),
            "amount": amount,
            "next_expected_date": commitment.get("next_expected_date"),
            "projected_balance": projected_balance
        })

    return {
        "current_balance": balance,
        "forecast": forecast,
        "final_projected_balance": projected_balance
    }


@router.get("/upcoming-commitments", response_model=list[RecurringCommitment])
def upcoming_commitments():
    transactions = load_transactions()
    return [
        commitment
        for commitment in get_recurring_commitments(transactions)
        if commitment["status"] == "active"
    ]


@router.get("/forecast", response_model=ForecastResponse)
def forecast():
    transactions = load_transactions()
    return get_cashflow_forecast(transactions)


@router.get("/income-analysis", response_model=IncomeAnalysisResponse)
def income_analysis():
    transactions = load_transactions()
    return get_income_analysis(transactions)


@router.get("/income-pathways", response_model=list[IncomePathway])
def income_pathways():
    return get_income_pathways()


@router.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest):
    return answer_chat(payload.message)


@router.post("/income-guidance", response_model=IncomeGuidanceResponse)
def income_guidance(payload: IncomeGuidanceRequest):
    return create_income_guidance(payload)
