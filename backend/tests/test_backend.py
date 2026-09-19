import json
from datetime import date

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app import config
from app.main import app
from app.schemas import Transaction
from app.ai.agent import answer_chat
from app.ai.client import GroqAIClient, RuleBasedAIClient
from app.ai.tools import get_tool_schemas
from app.services import financial, recurring, transactions
from app.services import automation
from app.services.cashflow import get_cashflow_metrics
from app.services.income import get_income_analysis
from app.services.memory import (
    CogneeHttpFinancialMemory,
    InMemoryFinancialMemory,
    SafeFallbackFinancialMemory,
)
from app.services.summary import get_financial_summary


def make_transaction(
    transaction_id: str,
    transaction_date: date,
    description: str,
    amount: float,
    transaction_type: str = "Debit",
    category: str = "Bills",
    is_recurring: bool = False,
) -> Transaction:
    return Transaction(
        transaction_id=transaction_id,
        date=transaction_date,
        description=description,
        amount=amount,
        type=transaction_type,
        category=category,
        recurring=is_recurring,
    )


def test_load_transactions_parses_csv_rows(tmp_path, monkeypatch):
    csv_file = tmp_path / "transactions.csv"
    csv_file.write_text(
        "\n".join(
            [
                "transaction_id,date,description,amount,type,category,recurring",
                "TXN1,2026-09-01,Salary,60000.0,Credit,Income,No",
                "TXN2,2026-09-02,House Rent,18000.0,Debit,Housing,Yes",
                "TXN3,2026-09-03,Netflix,649.0,Debit,Entertainment,1",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(transactions, "DATA_FILE", csv_file)

    loaded = transactions.load_transactions()

    assert loaded == [
        Transaction(
            transaction_id="TXN1",
            date=date(2026, 9, 1),
            description="Salary",
            amount=60000.0,
            type="Credit",
            category="Income",
            recurring=False,
        ),
        Transaction(
            transaction_id="TXN2",
            date=date(2026, 9, 2),
            description="House Rent",
            amount=18000.0,
            type="Debit",
            category="Housing",
            recurring=True,
        ),
        Transaction(
            transaction_id="TXN3",
            date=date(2026, 9, 3),
            description="Netflix",
            amount=649.0,
            type="Debit",
            category="Entertainment",
            recurring=True,
        ),
    ]


def test_create_transaction_updates_balance_for_credit_and_debit(tmp_path, monkeypatch):
    csv_file = tmp_path / "transactions.csv"
    account_file = tmp_path / "account.json"
    csv_file.write_text(
        "transaction_id,date,description,amount,type,category,recurring\n",
        encoding="utf-8",
    )
    account_file.write_text(
        '{"current_balance": 1000.0, "currency": "INR"}',
        encoding="utf-8",
    )
    monkeypatch.setattr(transactions, "DATA_FILE", csv_file)
    monkeypatch.setattr(transactions, "ACCOUNT_FILE", account_file)

    credit = transactions.create_transaction(
        transactions.TransactionCreate(
            date=date(2026, 9, 18),
            description="Refund",
            amount=250.0,
            type="Credit",
            category="Income",
            recurring=False,
        )
    )
    debit = transactions.create_transaction(
        transactions.TransactionCreate(
            date=date(2026, 9, 18),
            description="Snacks",
            amount=100.0,
            type="Debit",
            category="Food",
            recurring=False,
        )
    )

    assert credit.transaction_id == "TXN0001"
    assert debit.transaction_id == "TXN0002"
    assert json.loads(account_file.read_text(encoding="utf-8"))["current_balance"] == 1150.0
    assert len(transactions.load_transactions()) == 2


def test_create_transaction_rolls_back_when_account_write_fails(tmp_path, monkeypatch):
    csv_file = tmp_path / "transactions.csv"
    account_file = tmp_path / "account.json"
    original_csv = "\n".join(
        [
            "transaction_id,date,description,amount,type,category,recurring",
            "TXN0001,2026-09-01,Salary,1000.0,Credit,Income,No",
        ]
    )
    original_account = '{"current_balance": 1000.0, "currency": "INR"}'
    csv_file.write_text(original_csv, encoding="utf-8")
    account_file.write_text(original_account, encoding="utf-8")
    monkeypatch.setattr(transactions, "DATA_FILE", csv_file)
    monkeypatch.setattr(transactions, "ACCOUNT_FILE", account_file)

    def fail_account_write(account):
        del account
        raise OSError("disk full")

    monkeypatch.setattr(transactions, "_write_account_file", fail_account_write)

    with pytest.raises(HTTPException):
        transactions.create_transaction(
            transactions.TransactionCreate(
                date=date(2026, 9, 18),
                description="Snacks",
                amount=100.0,
                type="Debit",
                category="Food",
                recurring=False,
            )
        )

    assert csv_file.read_text(encoding="utf-8") == original_csv
    assert account_file.read_text(encoding="utf-8") == original_account


def test_transaction_schema_accepts_valid_transaction():
    transaction = Transaction(
        transaction_id="TXN1",
        date="2026-09-01",
        description="Salary",
        amount=60000.0,
        type="Credit",
        category="Income",
        recurring=False,
    )

    assert transaction.date == date(2026, 9, 1)
    assert transaction.amount == 60000.0


@pytest.mark.parametrize(
    "field,value",
    [
        ("amount", 0),
        ("amount", -1),
        ("type", "Refund"),
    ],
)
def test_transaction_schema_rejects_invalid_values(field, value):
    data = {
        "transaction_id": "TXN1",
        "date": "2026-09-01",
        "description": "Salary",
        "amount": 60000.0,
        "type": "Credit",
        "category": "Income",
        "recurring": False,
    }
    data[field] = value

    with pytest.raises(ValidationError):
        Transaction(**data)


def test_get_recurring_commitments_detects_active_recurring_debits():
    sample = [
        make_transaction(
            "R1", date(2026, 1, 2), "House Rent", 18000.0, is_recurring=True
        ),
        make_transaction(
            "R2", date(2026, 2, 2), "house rent", 18000.0, is_recurring=True
        ),
        make_transaction(
            "R3", date(2026, 3, 2), "House Rent", 18000.0, is_recurring=True
        ),
        make_transaction(
            "O1", date(2026, 1, 1), "Old Subscription", 500.0, is_recurring=True
        ),
        make_transaction(
            "C1",
            date(2026, 3, 15),
            "Salary",
            60000.0,
            transaction_type="Credit",
            category="Income",
            is_recurring=True,
        ),
        make_transaction("N1", date(2026, 3, 15), "Groceries", 1200.0),
    ]

    commitments = recurring.get_recurring_commitments(sample)

    assert commitments[0]["description"] == "House Rent"
    assert commitments[0]["amount"] == 18000.0
    assert commitments[0]["frequency"] == "monthly"
    assert commitments[0]["status"] == "active"
    assert commitments[0]["next_expected_date"] == date(2026, 4, 1)
    assert commitments[1]["description"] == "Old Subscription"
    assert commitments[1]["status"] == "inactive"


def test_get_balance_reads_account_file(tmp_path, monkeypatch):
    account_file = tmp_path / "account.json"
    account_file.write_text('{"current_balance": 12345.678}', encoding="utf-8")
    monkeypatch.setattr(financial, "ACCOUNT_FILE", account_file)

    assert financial.get_balance() == 12345.68


def test_get_net_cashflow_returns_credits_minus_debits():
    sample = [
        make_transaction(
            "C1",
            date(2026, 9, 1),
            "Salary",
            60000.0,
            transaction_type="Credit",
            category="Income",
        ),
        make_transaction("D1", date(2026, 9, 2), "Rent", 18000.0),
        make_transaction("D2", date(2026, 9, 3), "Netflix", 649.0),
    ]

    assert financial.get_net_cashflow(sample) == 41351.0


def test_get_safe_to_spend_protects_active_commitments(monkeypatch):
    monkeypatch.setattr(financial, "get_balance", lambda: 50000.0)
    sample = [
        make_transaction("R1", date(2026, 1, 2), "Rent", 18000.0, is_recurring=True),
        make_transaction("R2", date(2026, 2, 2), "Rent", 18000.0, is_recurring=True),
        make_transaction("R3", date(2026, 3, 2), "Rent", 18000.0, is_recurring=True),
        make_transaction(
            "I1", date(2026, 3, 10), "Internet", 1000.0, is_recurring=True
        ),
        make_transaction(
            "C1",
            date(2026, 3, 15),
            "Salary",
            60000.0,
            transaction_type="Credit",
            category="Income",
        ),
    ]

    assert financial.get_safe_to_spend(sample) == {
        "balance": 50000.0,
        "recurring_commitments": 19000.0,
        "savings_goal": 5000.0,
        "emergency_buffer": 10000.0,
        "protected_money": 34000.0,
        "safe_to_spend": 16000.0,
    }


def test_recurring_commitments_use_latest_changed_amount():
    sample = [
        make_transaction("R1", date(2026, 1, 2), "Gym", 1000.0, is_recurring=True),
        make_transaction("R2", date(2026, 2, 2), "Gym", 1200.0, is_recurring=True),
        make_transaction("R3", date(2026, 3, 2), "Gym", 1200.0, is_recurring=True),
        make_transaction(
            "C1",
            date(2026, 3, 15),
            "Salary",
            60000.0,
            transaction_type="Credit",
            category="Income",
        ),
    ]

    [commitment] = recurring.get_recurring_commitments(sample)

    assert commitment["amount"] == 1200.0
    assert recurring.get_recurring_commitment_total(sample) == 1200.0


def test_new_recurring_debit_reduces_safe_to_spend_once(tmp_path, monkeypatch):
    csv_file = tmp_path / "transactions.csv"
    account_file = tmp_path / "account.json"
    csv_file.write_text(
        "transaction_id,date,description,amount,type,category,recurring\n",
        encoding="utf-8",
    )
    account_file.write_text(
        '{"current_balance": 1000.0, "currency": "INR"}',
        encoding="utf-8",
    )
    monkeypatch.setattr(transactions, "DATA_FILE", csv_file)
    monkeypatch.setattr(transactions, "ACCOUNT_FILE", account_file)
    monkeypatch.setattr(financial, "ACCOUNT_FILE", account_file)
    monkeypatch.setattr(financial, "SAVINGS_GOAL", 0.0)
    monkeypatch.setattr(financial, "EMERGENCY_BUFFER", 0.0)

    created = transactions.create_transaction(
        transactions.TransactionCreate(
            date=date(2026, 9, 18),
            description="Gym",
            amount=100.0,
            type="Debit",
            category="Fitness",
            recurring=True,
        )
    )

    loaded = transactions.load_transactions()

    assert created.recurring is True
    assert json.loads(account_file.read_text(encoding="utf-8"))["current_balance"] == 900.0
    assert recurring.get_recurring_commitment_total(loaded) == 0.0
    assert financial.get_safe_to_spend(loaded)["safe_to_spend"] == 900.0


def test_existing_recurring_debit_still_reduces_safe_to_spend(tmp_path, monkeypatch):
    csv_file = tmp_path / "transactions.csv"
    account_file = tmp_path / "account.json"
    csv_file.write_text(
        "\n".join(
            [
                "transaction_id,date,description,amount,type,category,recurring",
                "TXN0001,2026-08-18,Gym,100.0,Debit,Fitness,Yes",
                "TXN0002,2026-09-01,Salary,1000.0,Credit,Income,No",
            ]
        ),
        encoding="utf-8",
    )
    account_file.write_text(
        '{"current_balance": 1000.0, "currency": "INR"}',
        encoding="utf-8",
    )
    monkeypatch.setattr(transactions, "DATA_FILE", csv_file)
    monkeypatch.setattr(transactions, "ACCOUNT_FILE", account_file)
    monkeypatch.setattr(financial, "ACCOUNT_FILE", account_file)
    monkeypatch.setattr(financial, "SAVINGS_GOAL", 0.0)
    monkeypatch.setattr(financial, "EMERGENCY_BUFFER", 0.0)

    before = financial.get_safe_to_spend(transactions.load_transactions())

    transactions.create_transaction(
        transactions.TransactionCreate(
            date=date(2026, 9, 18),
            description="Gym",
            amount=100.0,
            type="Debit",
            category="Fitness",
            recurring=True,
        )
    )
    after = financial.get_safe_to_spend(transactions.load_transactions())

    assert before["safe_to_spend"] == 900.0
    assert after["safe_to_spend"] == 800.0


def test_changed_recurring_debit_amount_does_not_increase_safe_to_spend(tmp_path, monkeypatch):
    csv_file = tmp_path / "transactions.csv"
    account_file = tmp_path / "account.json"
    csv_file.write_text(
        "\n".join(
            [
                "transaction_id,date,description,amount,type,category,recurring",
                "TXN0001,2026-08-18,Netflix,649.0,Debit,Entertainment,Yes",
                "TXN0002,2026-09-01,Salary,1000.0,Credit,Income,No",
            ]
        ),
        encoding="utf-8",
    )
    account_file.write_text(
        '{"current_balance": 1000.0, "currency": "INR"}',
        encoding="utf-8",
    )
    monkeypatch.setattr(transactions, "DATA_FILE", csv_file)
    monkeypatch.setattr(transactions, "ACCOUNT_FILE", account_file)
    monkeypatch.setattr(financial, "ACCOUNT_FILE", account_file)
    monkeypatch.setattr(financial, "SAVINGS_GOAL", 0.0)
    monkeypatch.setattr(financial, "EMERGENCY_BUFFER", 0.0)

    before = financial.get_safe_to_spend(transactions.load_transactions())

    transactions.create_transaction(
        transactions.TransactionCreate(
            date=date(2026, 9, 18),
            description="Netflix",
            amount=100.0,
            type="Debit",
            category="Entertainment",
            recurring=True,
        )
    )
    after = financial.get_safe_to_spend(transactions.load_transactions())

    assert before["safe_to_spend"] == 351.0
    assert after["safe_to_spend"] == 251.0


def test_recurring_commitments_become_inactive_when_overdue():
    sample = [
        make_transaction("R1", date(2026, 1, 1), "Gym", 1000.0, is_recurring=True),
        make_transaction("R2", date(2026, 2, 1), "Gym", 1000.0, is_recurring=True),
        make_transaction("D1", date(2026, 5, 1), "Groceries", 500.0),
    ]

    [commitment] = recurring.get_recurring_commitments(sample)

    assert commitment["status"] == "inactive"
    assert recurring.get_recurring_commitment_total(sample) == 0.0


def test_recurring_commitments_detect_new_active_candidate_without_double_counting():
    sample = [
        make_transaction("R1", date(2026, 3, 1), "Rent", 18000.0, is_recurring=True),
        make_transaction("R2", date(2026, 4, 1), "Rent", 18000.0, is_recurring=True),
        make_transaction("R3", date(2026, 4, 2), "Internet", 999.0, is_recurring=True),
    ]

    commitments = recurring.get_recurring_commitments(sample)

    assert {item["description"] for item in commitments} == {"Rent", "Internet"}
    assert recurring.get_recurring_commitment_total(sample) == 18000.0


def test_cashflow_metrics_separate_history_from_balance():
    sample = [
        make_transaction(
            "C1",
            date(2026, 9, 1),
            "Salary",
            60000.0,
            transaction_type="Credit",
            category="Income",
        ),
        make_transaction("D1", date(2026, 9, 2), "Rent", 18000.0, category="Housing"),
        make_transaction("D2", date(2026, 9, 3), "Food", 1000.0, category="Food"),
    ]

    metrics = get_cashflow_metrics(sample)

    assert metrics["total_income"] == 60000.0
    assert metrics["total_expenses"] == 19000.0
    assert metrics["net_cashflow"] == 41000.0
    assert metrics["by_category"][0] == {"category": "Housing", "amount": 18000.0}


def test_income_analysis_returns_documented_targets():
    sample = [
        make_transaction(
            "C1",
            date(2026, 7, 1),
            "Salary",
            50000.0,
            transaction_type="Credit",
            category="Income",
        ),
        make_transaction(
            "C2",
            date(2026, 8, 1),
            "Salary",
            60000.0,
            transaction_type="Credit",
            category="Income",
        ),
        make_transaction(
            "C3",
            date(2026, 9, 1),
            "Salary",
            70000.0,
            transaction_type="Credit",
            category="Income",
        ),
        make_transaction("D1", date(2026, 9, 2), "Rent", 18000.0, category="Housing", is_recurring=True),
        make_transaction("D2", date(2026, 9, 3), "Food", 12000.0, category="Groceries"),
    ]

    analysis = get_income_analysis(sample)

    assert analysis["prototype_estimate"] is True
    assert analysis["current_income"] == 60000.0
    assert analysis["comfortable_target"] >= analysis["survival_target"]
    assert analysis["heuristics"]


def test_financial_summary_includes_firewall_cashflow_and_income(monkeypatch):
    monkeypatch.setattr(financial, "get_balance", lambda: 50000.0)
    sample = [
        make_transaction("R1", date(2026, 9, 2), "Rent", 18000.0, category="Housing", is_recurring=True),
        make_transaction(
            "C1",
            date(2026, 9, 15),
            "Salary",
            60000.0,
            transaction_type="Credit",
            category="Income",
        ),
    ]

    summary = get_financial_summary(sample)

    assert summary["safe_to_spend"] == 17000.0
    assert summary["cashflow"]["net_cashflow"] == 42000.0
    assert summary["income_analysis"]["prototype_estimate"] is True


def test_safe_to_spend_endpoint_returns_service_result(monkeypatch):
    expected = {
        "balance": 50000.0,
        "recurring_commitments": 19000.0,
        "savings_goal": 5000.0,
        "emergency_buffer": 10000.0,
        "protected_money": 34000.0,
        "safe_to_spend": 16000.0,
    }

    from app.routes import finance

    monkeypatch.setattr(finance, "load_transactions", lambda: ["transaction"])
    monkeypatch.setattr(finance, "get_safe_to_spend", lambda loaded: expected)
    monkeypatch.setattr(finance, "publish_financial_state_events", lambda loaded: [])

    response = TestClient(app).get("/safe-to-spend")

    assert response.status_code == 200
    assert response.json() == expected


def test_cashflow_endpoint_returns_metrics(monkeypatch):
    from app.routes import finance

    monkeypatch.setattr(finance, "load_transactions", lambda: [])

    response = TestClient(app).get("/cashflow")

    assert response.status_code == 200
    assert response.json()["net_cashflow"] == 0.0


def test_transactions_endpoint_rejects_invalid_input():
    response = TestClient(app).post(
        "/transactions",
        json={
            "date": "2026-09-01",
            "description": "",
            "amount": -1,
            "type": "Debit",
            "category": "Food",
            "recurring": False,
        },
    )

    assert response.status_code == 422


def test_chat_uses_tool_result_for_spend_decision(monkeypatch):
    from app.ai import tools

    monkeypatch.setattr(
        tools,
        "load_transactions",
        lambda: [
            make_transaction(
                "C1",
                date(2026, 9, 1),
                "Salary",
                60000.0,
                transaction_type="Credit",
                category="Income",
            )
        ],
    )
    monkeypatch.setattr(financial, "get_balance", lambda: 50000.0)

    result = answer_chat("Can I spend Rs 8000 on shoes?", RuleBasedAIClient())

    assert result["tool_used"] == "get_safe_to_spend"
    assert "Yes" in result["answer"]


def test_local_chat_remembers_and_recalls_financial_goal(monkeypatch):
    memory = InMemoryFinancialMemory()

    from app.ai import tools

    monkeypatch.setattr(tools, "get_memory", lambda: memory)

    remembered = answer_chat(
        "I'm saving Rs 50000 for a laptop.",
        RuleBasedAIClient(),
    )
    recalled = answer_chat(
        "What goal did I tell you about?",
        RuleBasedAIClient(),
    )

    assert remembered["tool_used"] == "remember_financial_goal"
    assert remembered["tool_result"]["remembered"] is True
    assert recalled["tool_used"] == "recall_financial_goals"
    assert "laptop" in recalled["answer"]


def test_local_chat_formats_cashflow_response(monkeypatch):
    from app.ai import tools

    monkeypatch.setattr(
        tools,
        "load_transactions",
        lambda: [
            make_transaction(
                "C1",
                date(2026, 9, 1),
                "Salary",
                60000.0,
                transaction_type="Credit",
                category="Income",
            ),
            make_transaction("D1", date(2026, 9, 2), "Rent", 18000.0),
        ],
    )

    result = answer_chat("Show me my cash flow.", RuleBasedAIClient())

    assert result["tool_used"] == "get_cashflow"
    assert "### CASH FLOW" in result["answer"]
    assert "- Net cashflow: Rs 42000.00" in result["answer"]


def test_groq_tool_calling_path_uses_backend_tool(monkeypatch):
    calls = []

    class FakeResponse:
        def __init__(self, payload):
            self.payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self.payload

    def fake_post(url, headers, json, timeout):
        del url, headers, timeout
        calls.append(json)
        if len(calls) == 1:
            return FakeResponse(
                {
                    "choices": [
                        {
                            "message": {
                                "role": "assistant",
                                "tool_calls": [
                                    {
                                        "id": "call_1",
                                        "type": "function",
                                        "function": {
                                            "name": "get_safe_to_spend",
                                            "arguments": "{}",
                                        },
                                    }
                                ],
                            }
                        }
                    ]
                }
            )
        return FakeResponse(
            {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "Backend says safe-to-spend is Rs 123.00.",
                        }
                    }
                ]
            }
        )

    from app.ai import client

    monkeypatch.setattr(client.httpx, "post", fake_post)

    groq = GroqAIClient("test-key", "configured-model")
    result = groq.answer_with_tools(
        "How much can I safely spend?",
        get_tool_schemas(),
        lambda name, args: {
            "balance": 1000.0,
            "recurring_commitments": 100.0,
            "savings_goal": 500.0,
            "emergency_buffer": 277.0,
            "protected_money": 877.0,
            "safe_to_spend": 123.0,
        },
    )

    assert calls[0]["model"] == "configured-model"
    assert calls[0]["tools"]
    assert calls[1]["messages"][-1]["role"] == "tool"
    assert result["tool_used"] == "get_safe_to_spend"
    assert result["tool_result"]["safe_to_spend"] == 123.0


def test_groq_tool_calling_executes_multiple_requested_tools(monkeypatch):
    calls = []
    executed = []

    class FakeResponse:
        def __init__(self, payload):
            self.payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self.payload

    def fake_post(url, headers, json, timeout):
        del url, headers, timeout
        calls.append(json)
        if len(calls) == 1:
            return FakeResponse(
                {
                    "choices": [
                        {
                            "message": {
                                "role": "assistant",
                                "tool_calls": [
                                    {
                                        "id": "call_1",
                                        "type": "function",
                                        "function": {
                                            "name": "get_safe_to_spend",
                                            "arguments": "{}",
                                        },
                                    },
                                    {
                                        "id": "call_2",
                                        "type": "function",
                                        "function": {
                                            "name": "recall_financial_goals",
                                            "arguments": "{}",
                                        },
                                    },
                                ],
                            }
                        }
                    ]
                }
            )
        return FakeResponse(
            {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "Combined backend result.",
                        }
                    }
                ]
            }
        )

    from app.ai import client

    monkeypatch.setattr(client.httpx, "post", fake_post)

    def fake_execute(name, args):
        del args
        executed.append(name)
        if name == "get_safe_to_spend":
            return {"safe_to_spend": 123.0}
        return {"goals": ["Laptop"]}

    result = GroqAIClient("test-key", "configured-model").answer_with_tools(
        "Can I spend and what goal do I have?",
        get_tool_schemas(),
        fake_execute,
    )

    assert executed == ["get_safe_to_spend", "recall_financial_goals"]
    assert calls[1]["messages"][-2]["name"] == "get_safe_to_spend"
    assert calls[1]["messages"][-1]["name"] == "recall_financial_goals"
    assert result["tool_used"] == "get_safe_to_spend,recall_financial_goals"
    assert result["tool_result"] == [
        {
            "tool_name": "get_safe_to_spend",
            "result": {"safe_to_spend": 123.0},
        },
        {
            "tool_name": "recall_financial_goals",
            "result": {"goals": ["Laptop"]},
        },
    ]


def test_chat_endpoint_accepts_multi_tool_result_with_list_payload(monkeypatch):
    calls = []

    class FakeResponse:
        def __init__(self, payload):
            self.payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self.payload

    def fake_post(url, headers, json, timeout):
        del url, headers, timeout
        calls.append(json)
        if len(calls) == 1:
            return FakeResponse(
                {
                    "choices": [
                        {
                            "message": {
                                "role": "assistant",
                                "tool_calls": [
                                    {
                                        "id": "call_safe",
                                        "type": "function",
                                        "function": {
                                            "name": "get_safe_to_spend",
                                            "arguments": "{}",
                                        },
                                    },
                                    {
                                        "id": "call_commitments",
                                        "type": "function",
                                        "function": {
                                            "name": "get_upcoming_commitments",
                                            "arguments": "{}",
                                        },
                                    },
                                ],
                            }
                        }
                    ]
                }
            )
        return FakeResponse(
            {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "Safe-to-spend and commitments reviewed.",
                        }
                    }
                ]
            }
        )

    sample = [
        make_transaction(
            "R1",
            date(2026, 1, 2),
            "House Rent",
            18000.0,
            category="Housing",
            is_recurring=True,
        ),
        make_transaction(
            "R2",
            date(2026, 2, 2),
            "House Rent",
            18000.0,
            category="Housing",
            is_recurring=True,
        ),
        make_transaction(
            "R3",
            date(2026, 3, 2),
            "House Rent",
            18000.0,
            category="Housing",
            is_recurring=True,
        ),
        make_transaction(
            "C1",
            date(2026, 3, 15),
            "Salary",
            60000.0,
            transaction_type="Credit",
            category="Income",
        ),
    ]

    from app.ai import agent, client, tools

    monkeypatch.setattr(
        agent,
        "get_ai_client",
        lambda: GroqAIClient("test-key", "configured-model"),
    )
    monkeypatch.setattr(client.httpx, "post", fake_post)
    monkeypatch.setattr(tools, "load_transactions", lambda: sample)
    monkeypatch.setattr(financial, "get_balance", lambda: 59800.0)

    response = TestClient(app).post(
        "/chat",
        json={"message": "Can I spend safely and what commitments are next?"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["tool_used"] == "get_safe_to_spend,get_upcoming_commitments"
    assert body["tool_result"][0]["tool_name"] == "get_safe_to_spend"
    assert body["tool_result"][0]["result"]["safe_to_spend"] == 26800.0
    assert body["tool_result"][1]["tool_name"] == "get_upcoming_commitments"
    assert body["tool_result"][1]["result"][0]["description"] == "House Rent"


def test_cognee_memory_uses_http_api_with_mock(monkeypatch):
    requests = []

    class FakeResponse:
        def __init__(self, payload=None):
            self.payload = payload or {"result": "saved laptop goal"}

        def raise_for_status(self):
            return None

        def json(self):
            return self.payload

    def fake_post(url, headers, timeout, json=None, data=None, files=None):
        del timeout
        requests.append(
            {
                "url": url,
                "headers": headers,
                "json": json,
                "data": data,
                "files": files,
            }
        )
        return FakeResponse()

    from app.services import memory

    monkeypatch.setattr(memory.httpx, "post", fake_post)

    cognee = CogneeHttpFinancialMemory(
        api_key="test-key",
        base_url="https://api.cognee.ai",
        dataset="paytm-test",
    )
    stored = cognee.remember_goal({"description": "Laptop", "target_amount": 50000})
    recalled = cognee.recall_goals()

    assert stored["remembered"] is True
    assert requests[0]["url"].endswith("/api/v1/add")
    assert requests[1]["url"].endswith("/api/v1/cognify")
    assert requests[2]["url"].endswith("/api/v1/search")
    assert requests[0]["json"] is None
    assert requests[0]["data"] == {"datasetName": "paytm-test"}
    assert requests[0]["files"][0][0] == "data"
    assert requests[0]["files"][0][1][0] == "financial_goal.txt"
    assert requests[0]["files"][0][1][2] == "text/plain"
    assert requests[1]["json"] == {
        "run_in_background": False,
        "datasets": ["paytm-test"],
    }
    assert requests[2]["json"]["datasets"] == ["paytm-test"]
    assert requests[2]["json"]["top_k"] == 15
    assert requests[0]["headers"]["X-Api-Key"] == "test-key"
    assert "Content-Type" not in requests[0]["headers"]
    assert recalled["provider"] == "cognee-http"


def test_cognee_memory_can_target_dataset_id(monkeypatch):
    requests = []

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"result": "ok"}

    def fake_post(url, headers, timeout, json=None, data=None, files=None):
        del url, headers, timeout, files
        requests.append({"json": json, "data": data})
        return FakeResponse()

    from app.services import memory

    monkeypatch.setattr(memory.httpx, "post", fake_post)

    cognee = CogneeHttpFinancialMemory(
        api_key="test-key",
        base_url="https://tenant.cognee.example",
        dataset="ignored-when-id-is-set",
        dataset_id="dataset-123",
    )

    cognee.remember_goal({"description": "Emergency fund"})
    cognee.recall_goals()

    assert requests[0]["data"]["datasetId"] == "dataset-123"
    assert requests[1]["json"] == {
        "run_in_background": False,
        "datasetIds": ["dataset-123"],
    }
    assert requests[2]["json"]["datasetIds"] == ["dataset-123"]


def test_memory_without_cognee_credentials_uses_local_fallback(monkeypatch):
    from app.services import memory

    config.get_settings.cache_clear()
    monkeypatch.setenv("COGNEE_API_KEY", "")
    memory._LOCAL_MEMORY = InMemoryFinancialMemory()

    selected = memory.get_memory()
    result = selected.remember_goal({"description": "Laptop"})

    assert isinstance(selected, InMemoryFinancialMemory)
    assert result["provider"] == "local-in-memory"
    assert result["remembered"] is True
    config.get_settings.cache_clear()


def test_memory_with_cognee_credentials_uses_cognee_on_success(monkeypatch):
    from app.services import memory

    calls = []

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"result": "from cognee"}

    def fake_post(url, headers, timeout, json=None, data=None, files=None):
        del headers, timeout, json, data, files
        calls.append(url)
        return FakeResponse()

    config.get_settings.cache_clear()
    monkeypatch.setenv("COGNEE_API_KEY", "test-key")
    monkeypatch.setattr(memory.httpx, "post", fake_post)
    memory._LOCAL_MEMORY = InMemoryFinancialMemory()

    selected = memory.get_memory()
    remembered = selected.remember_goal({"description": "Laptop"})
    recalled = selected.recall_goals()

    assert isinstance(selected, SafeFallbackFinancialMemory)
    assert remembered["provider"] == "cognee-http"
    assert "fallback" not in remembered
    assert recalled["provider"] == "cognee-http"
    assert len(calls) == 3
    config.get_settings.cache_clear()


def test_memory_with_cognee_failure_falls_back_to_local(monkeypatch):
    from app.services import memory

    def failing_post(*args, **kwargs):
        del args, kwargs
        raise memory.httpx.ConnectError("Cognee unavailable")

    config.get_settings.cache_clear()
    monkeypatch.setenv("COGNEE_API_KEY", "test-key")
    monkeypatch.setattr(memory.httpx, "post", failing_post)
    memory._LOCAL_MEMORY = InMemoryFinancialMemory()

    selected = memory.get_memory()
    remembered = selected.remember_goal({"description": "Laptop"})
    recalled = selected.recall_goals()

    assert remembered["provider"] == "local-in-memory"
    assert remembered["fallback"] is True
    assert remembered["primary_provider"] == "cognee-http"
    assert recalled["provider"] == "local-in-memory"
    assert recalled["fallback"] is True
    assert recalled["goals"][0]["description"] == "Laptop"
    config.get_settings.cache_clear()


def test_chat_still_works_when_cognee_is_unavailable(monkeypatch):
    from app.services import memory

    def failing_post(*args, **kwargs):
        del args, kwargs
        raise memory.httpx.ConnectError("Cognee unavailable")

    config.get_settings.cache_clear()
    monkeypatch.setenv("COGNEE_API_KEY", "test-key")
    monkeypatch.setattr(memory.httpx, "post", failing_post)
    memory._LOCAL_MEMORY = InMemoryFinancialMemory()

    result = answer_chat(
        "I'm saving Rs 50000 for a laptop.",
        RuleBasedAIClient(),
    )

    assert result["tool_used"] == "remember_financial_goal"
    assert result["tool_result"]["provider"] == "local-in-memory"
    assert result["tool_result"]["fallback"] is True
    config.get_settings.cache_clear()


def test_n8n_event_delivery_with_mock(monkeypatch):
    delivered = []

    class FakeResponse:
        status_code = 200

        def raise_for_status(self):
            return None

    def fake_post(url, json, timeout):
        del timeout
        delivered.append({"url": url, "json": json})
        return FakeResponse()

    config.get_settings.cache_clear()
    monkeypatch.setenv("N8N_WEBHOOK_URL", "https://n8n.example/webhook")
    monkeypatch.setattr(automation.httpx, "post", fake_post)

    result = automation.emit_event("safe_to_spend_changed", {"current": 1000})

    assert result == {"delivered": True, "status_code": 200}
    assert delivered[0]["json"]["event_type"] == "safe_to_spend_changed"
    config.get_settings.cache_clear()


def test_n8n_detects_safe_to_spend_and_commitment_changes():
    previous = {
        "safe_to_spend": 1000.0,
        "protected_money": 2000.0,
        "active_commitments": {"gym": 1000.0, "rent": 18000.0},
        "inactive_commitments": [],
    }
    current = {
        "safe_to_spend": 800.0,
        "protected_money": 2200.0,
        "active_commitments": {"gym": 1200.0, "internet": 999.0},
        "inactive_commitments": [],
    }

    event_types = [
        event["event_type"]
        for event in automation.detect_financial_events(current, previous)
    ]

    assert "safe_to_spend_changed" in event_types
    assert event_types.count("active_recurring_commitment_changed") == 2
    assert "recurring_commitment_became_inactive" in event_types


def test_dotenv_loading_reads_local_env_file(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("GROQ_MODEL=test-model\nGROQ_API_KEY=abc\n", encoding="utf-8")
    monkeypatch.setattr(config, "ENV_FILE", env_file)
    monkeypatch.delenv("GROQ_MODEL", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    config.get_settings.cache_clear()

    settings = config.get_settings()

    assert settings.groq_model == "test-model"
    assert settings.groq_api_key == "abc"
    config.get_settings.cache_clear()


def test_default_groq_model_is_current_configured_default(monkeypatch):
    monkeypatch.delenv("GROQ_MODEL", raising=False)
    config.get_settings.cache_clear()

    assert config.get_settings().groq_model == "openai/gpt-oss-120b"
    config.get_settings.cache_clear()


def test_chat_endpoint_validates_blank_message():
    response = TestClient(app).post("/chat", json={"message": "   "})

    assert response.status_code == 422


def _career_profile_payload():
    return {
        "education_status": "Student",
        "highest_qualification": "BTech",
        "field_of_study": "Computer Science",
        "graduation_year": 2027,
        "employment_status": "Student",
        "current_designation": "",
        "years_of_experience": 0,
        "industry": "Technology",
        "previous_experience": "Built small web projects.",
        "skills": [
            {"skill": "HTML", "proficiency": "Intermediate"},
            {"skill": "CSS", "proficiency": "Intermediate"},
            {"skill": "JavaScript", "proficiency": "Beginner"},
        ],
        "preferred_job_types": ["Internship", "Freelance"],
        "preferred_work_mode": "Remote",
        "preferred_location": "India",
        "hours_available_per_week": 12,
        "minimum_additional_income": 10000,
        "industries_of_interest": ["Technology"],
        "roles_of_interest": ["Frontend Developer"],
        "work_to_avoid": "Night shift support",
        "willingness_to_learn": "High",
        "career_context": "I want frontend work.",
    }


def test_income_pathways_endpoint_uses_existing_income_analysis():
    response = TestClient(app).get("/income-pathways")

    assert response.status_code == 200
    body = response.json()
    assert [item["id"] for item in body] == [
        "survival",
        "comfortable",
        "aspirational",
    ]
    assert all("target_additional_income" in item for item in body)


def test_income_guidance_request_validation_rejects_missing_skills():
    payload = {
        "user_id": "demo-user",
        "pathway_id": "comfortable",
        "remember_profile": False,
        "career_profile": {
            **_career_profile_payload(),
            "skills": [],
        },
    }

    response = TestClient(app).post("/income-guidance", json=payload)

    assert response.status_code == 422


def test_income_guidance_full_flow_with_memory_disabled(monkeypatch):
    from app.services import career_guidance

    def fake_generate(pathway, profile, memory_context=None):
        del pathway, memory_context
        return {
            "profile_summary": f"{profile.education_status} profile reviewed.",
            "recommended_roles": [
                {
                    "role": "Frontend Developer",
                    "why_it_fits": "Matches current skills.",
                    "required_skills": ["HTML", "CSS", "JavaScript"],
                    "skills_user_already_has": ["HTML", "CSS"],
                    "skill_gaps": ["React"],
                    "search_queries": ["frontend developer"],
                }
            ],
            "skill_gaps": ["React"],
            "action_plan": [{"period": "Week 1", "actions": ["Build a UI project."]}],
            "application_strategy": ["Apply with proof of work."],
            "profile_notes": ["No memory used."],
        }

    monkeypatch.setattr(career_guidance, "generate_career_guidance", fake_generate)

    response = TestClient(app).post(
        "/income-guidance",
        json={
            "user_id": "demo-user",
            "pathway_id": "comfortable",
            "remember_profile": False,
            "career_profile": _career_profile_payload(),
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["selected_pathway"]["id"] == "comfortable"
    assert body["recommended_roles"][0]["role"] == "Frontend Developer"
    assert body["skill_gaps"] == ["React"]
    assert body["action_plan"][0]["period"] == "Week 1"
    assert body["memory_context"]["enabled"] is False


def test_income_guidance_memory_enabled(monkeypatch):
    from app.services import career_guidance

    remembered = []

    class FakeMemory:
        provider_name = "fake-memory"

        def recall_career_context(self, user_id):
            return {
                "recalled": True,
                "provider": self.provider_name,
                "context": {"previous_focus": "Frontend"},
            }

        def remember_guidance(self, user_id, payload):
            remembered.append({"user_id": user_id, "payload": payload})
            return {"remembered": True, "provider": self.provider_name}

    def fake_generate(pathway, profile, memory_context=None):
        assert memory_context == {"previous_focus": "Frontend"}
        return {
            "profile_summary": "Memory-aware profile reviewed.",
            "recommended_roles": [
                {
                    "role": "Frontend Developer",
                    "why_it_fits": "Matches recalled context.",
                    "required_skills": ["React"],
                    "skills_user_already_has": ["JavaScript"],
                    "skill_gaps": ["React"],
                    "search_queries": ["frontend developer"],
                }
            ],
            "skill_gaps": ["React"],
            "action_plan": [{"period": "Week 1", "actions": ["Learn React basics."]}],
            "application_strategy": ["Apply selectively."],
            "profile_notes": [],
        }

    monkeypatch.setattr(career_guidance, "get_career_memory", lambda: FakeMemory())
    monkeypatch.setattr(career_guidance, "generate_career_guidance", fake_generate)

    response = TestClient(app).post(
        "/income-guidance",
        json={
            "user_id": "demo-user",
            "pathway_id": "comfortable",
            "remember_profile": True,
            "career_profile": _career_profile_payload(),
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["recommended_roles"][0]["skill_gaps"] == ["React"]
    assert body["action_plan"][0]["actions"] == ["Learn React basics."]
    assert body["memory_context"]["recalled"] is True
    assert body["memory_context"]["remembered"] is True
    assert remembered[0]["user_id"] == "demo-user"


def test_career_memory_without_cognee_key_is_disabled(monkeypatch):
    from app.services import career_memory

    config.get_settings.cache_clear()
    monkeypatch.setenv("COGNEE_API_KEY", "")

    selected = career_memory.get_career_memory()
    remembered = selected.remember_guidance("demo-user", {"role": "Frontend"})
    recalled = selected.recall_career_context("demo-user")

    assert selected.provider_name == "disabled"
    assert remembered == {"remembered": False, "provider": "disabled"}
    assert recalled == {
        "recalled": False,
        "provider": "disabled",
        "context": None,
    }
    config.get_settings.cache_clear()


def test_cognee_career_memory_writes_and_recalls_with_career_dataset(monkeypatch):
    from app.services import career_memory

    requests = []

    class FakeResponse:
        def __init__(self, payload=None):
            self.payload = payload or {"result": "frontend career memory"}

        def raise_for_status(self):
            return None

        def json(self):
            return self.payload

    def fake_post(url, headers, timeout, json=None, data=None, files=None):
        del timeout
        requests.append(
            {
                "url": url,
                "headers": headers,
                "json": json,
                "data": data,
                "files": files,
            }
        )
        return FakeResponse()

    monkeypatch.setattr(career_memory.httpx, "post", fake_post)
    memory = career_memory.CogneeHttpCareerMemory(
        api_key="test-key",
        base_url="https://api.cognee.ai",
        dataset="paytm_sense_career_memory",
    )

    remembered = memory.remember_guidance(
        "demo-user",
        {"selected_pathway": {"id": "comfortable"}, "skill_gaps": ["React"]},
    )
    recalled = memory.recall_career_context("demo-user")

    assert remembered["remembered"] is True
    assert requests[0]["url"].endswith("/api/v1/add")
    assert requests[0]["headers"]["X-Api-Key"] == "test-key"
    assert requests[0]["data"] == {"datasetName": "paytm_sense_career_memory"}
    assert requests[0]["files"][0][1][0] == "career_guidance.txt"
    assert b"user:demo-user" in requests[0]["files"][0][1][1]
    assert requests[1]["url"].endswith("/api/v1/cognify")
    assert requests[1]["json"]["datasets"] == ["paytm_sense_career_memory"]
    assert requests[2]["url"].endswith("/api/v1/search")
    assert requests[2]["json"]["datasets"] == ["paytm_sense_career_memory"]
    assert "user:demo-user" in requests[2]["json"]["query"]
    assert recalled["provider"] == "cognee-http"
