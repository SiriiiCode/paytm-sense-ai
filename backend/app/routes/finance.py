from fastapi import APIRouter

from ..services.transactions import load_transactions
from ..services.financial import get_safe_to_spend


router = APIRouter()


@router.get("/safe-to-spend")
def safe_to_spend():
    transactions = load_transactions()

    return get_safe_to_spend(transactions)