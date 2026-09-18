from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


class Transaction(BaseModel):
    transaction_id: str
    date: date
    description: str
    amount: float = Field(gt=0)
    type: Literal["Credit", "Debit"]
    category: str
    recurring: bool