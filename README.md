# Paytm Sense AI

Paytm Sense is an AI-powered financial intelligence layer built for the Paytm AI Hackathon. The backend combines a deterministic financial firewall with lightweight statistical intelligence and an optional AI explanation layer.

The LLM never calculates authoritative money values. Balance, protected money, safe-to-spend, recurring commitments, cashflow, forecasts, and income targets are computed in Python services.

## Architecture

- Data / ingestion: CSV transaction loading and transaction creation.
- Deterministic financial engine: balance, recurring commitments, protected money, safe-to-spend.
- Statistical intelligence: cashflow metrics, moving-average forecast, prototype income targets.
- AI agent: uses Groq/OpenAI-style tool calling when configured, receives computed backend results, and explains them.
- API layer: FastAPI routes with Pydantic response models.
- Optional adapters: Groq, Cognee HTTP memory, n8n webhook.

## Backend Structure

```text
backend/
  app/
    ai/
    routes/
    services/
    config.py
    main.py
    schemas.py
  data/
    account.json
    transactions.csv
  tests/
  requirements.txt
workflows/n8n/
```

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend\requirements.txt
```

## Run API

```powershell
cd backend
..\.venv\Scripts\uvicorn.exe app.main:app --reload
```

Or run uvicorn through Python:

```powershell
cd backend
..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000/docs`.

## Run Tests

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests
```

## Frontend Integration

Run the backend locally and use `http://127.0.0.1:8000` as the API base URL.
FastAPI also exposes the generated OpenAPI UI at `http://127.0.0.1:8000/docs`.

Dates are serialized as `YYYY-MM-DD`. Money values are JSON numbers. Transaction
`type` must be either `Credit` or `Debit`.

## API Endpoints

### `GET /`

Health check for local development.

Example response:

```json
{
  "message": "Paytm Sense backend is running"
}
```

### `GET /transactions`

Returns all transactions loaded from `backend/data/transactions.csv`.

Response structure: an array of transaction objects.

Important fields:

- `transaction_id`: generated transaction id such as `TXN0001`.
- `date`: transaction date.
- `description`: merchant/source text.
- `amount`: positive amount.
- `type`: `Credit` or `Debit`.
- `category`: category label.
- `recurring`: boolean recurring marker.

Example request:

```http
GET /transactions
```

Example response:

```json
[
  {
    "transaction_id": "TXN0001",
    "date": "2026-09-01",
    "description": "Salary",
    "amount": 60000.0,
    "type": "Credit",
    "category": "Income",
    "recurring": false
  }
]
```

### `POST /transactions`

Adds a transaction, persists it to the CSV store, updates local account balance,
and publishes optional n8n financial-state events. Returns `201 Created`.

Request body:

```json
{
  "date": "2026-09-18",
  "description": "Groceries",
  "amount": 1200.0,
  "type": "Debit",
  "category": "Groceries",
  "recurring": false
}
```

Request fields:

- `date`: required date.
- `description`: required non-blank string.
- `amount`: required number greater than `0`.
- `type`: required `Credit` or `Debit`.
- `category`: required non-blank string.
- `recurring`: optional boolean, defaults to `false`.

Response structure: the created transaction, including generated
`transaction_id`.

Example request:

```http
POST /transactions
Content-Type: application/json
```

```json
{
  "date": "2026-09-18",
  "description": "Groceries",
  "amount": 1200.0,
  "type": "Debit",
  "category": "Groceries",
  "recurring": false
}
```

Example response:

```json
{
  "transaction_id": "TXN0002",
  "date": "2026-09-18",
  "description": "Groceries",
  "amount": 1200.0,
  "type": "Debit",
  "category": "Groceries",
  "recurring": false
}
```

Invalid input returns FastAPI/Pydantic validation errors with status `422`.

### `GET /safe-to-spend`

Returns the deterministic financial firewall calculation.

Response structure:

```json
{
  "balance": 50000.0,
  "recurring_commitments": 19000.0,
  "savings_goal": 5000.0,
  "emergency_buffer": 10000.0,
  "protected_money": 34000.0,
  "safe_to_spend": 16000.0
}
```

Important fields:

- `balance`: current balance from local account state.
- `recurring_commitments`: total amount of active recurring debits.
- `savings_goal`: fixed protected savings amount.
- `emergency_buffer`: fixed protected emergency buffer.
- `protected_money`: recurring commitments plus savings goal plus emergency buffer.
- `safe_to_spend`: `balance - protected_money`, never below `0`.

### `GET /financial-summary`

Returns the main frontend dashboard payload: safe-to-spend numbers, recurring
commitments, cashflow metrics, forecast, and income analysis. This route also
publishes optional n8n financial-state events.

Response structure:

```json
{
  "balance": 50000.0,
  "protected_money": 34000.0,
  "safe_to_spend": 16000.0,
  "recurring_commitments": [
    {
      "description": "House Rent",
      "category": "Housing",
      "amount": 18000.0,
      "frequency": "monthly",
      "last_seen": "2026-09-02",
      "days_since_last": 16,
      "status": "active",
      "next_expected_date": "2026-10-02",
      "overdue_days": 0
    }
  ],
  "savings_goal": 5000.0,
  "emergency_buffer": 10000.0,
  "cashflow": {
    "period_start": "2026-09-01",
    "period_end": "2026-09-18",
    "total_income": 60000.0,
    "total_expenses": 19000.0,
    "net_cashflow": 41000.0,
    "average_daily_income": 3333.33,
    "average_daily_expense": 1055.56,
    "monthly": [
      {
        "month": "2026-09",
        "income": 60000.0,
        "expenses": 19000.0,
        "net": 41000.0
      }
    ],
    "by_category": [
      {
        "category": "Housing",
        "amount": 18000.0
      }
    ]
  },
  "forecast": {
    "horizon_days": 30,
    "as_of_date": "2026-09-18",
    "forecast_income": 60000.0,
    "forecast_expenses": 19000.0,
    "forecast_net_cashflow": 41000.0,
    "projected_balance": 91000.0,
    "method": "3-month moving average scaled to horizon",
    "assumptions": [
      "Uses only historical transaction averages.",
      "Does not use an LLM to calculate forecast values.",
      "Synthetic prototype data may not reflect a real user's seasonality."
    ]
  },
  "income_analysis": {
    "prototype_estimate": true,
    "current_income": 60000.0,
    "survival_target": 18000.0,
    "comfortable_target": 23750.0,
    "aspirational_target": 29687.5,
    "income_gap": 0.0,
    "heuristics": [
      "Current income is the average monthly credit over the latest 3 months.",
      "Survival target is the higher of essential spend average and active recurring commitments.",
      "Comfortable target is the higher of 110% of average spend and 125% of survival target.",
      "Aspirational target is 125% of comfortable target."
    ]
  }
}
```

Important top-level fields:

- `balance`, `protected_money`, `safe_to_spend`, `savings_goal`,
  `emergency_buffer`: same meanings as `/safe-to-spend`.
- `recurring_commitments`: array of recurring debit commitments sorted by amount.
- `cashflow`: historical income/expense metrics.
- `forecast`: moving-average cashflow forecast.
- `income_analysis`: prototype income target heuristics.

Recurring commitment fields:

- `frequency`: one of the inferred labels used by the backend, such as
  `weekly`, `monthly`, `quarterly`, or `unknown`.
- `status`: `active` or `inactive`.
- `next_expected_date`: date or `null`.
- `overdue_days`: `0` when not overdue.

Example request:

```http
GET /financial-summary
```

### `GET /cashflow`

Returns the `cashflow` object used inside `/financial-summary`.

### `GET /cash-flow-forecast`

Returns a commitment-based balance projection using active recurring commitments
from the financial summary. This is separate from `GET /forecast`, which returns
the moving-average cashflow forecast.

Response structure:

```json
{
  "current_balance": 50000.0,
  "forecast": [
    {
      "description": "House Rent",
      "amount": 18000.0,
      "next_expected_date": "2026-10-02",
      "projected_balance": 32000.0
    }
  ],
  "final_projected_balance": 32000.0
}
```

Important fields:

- `current_balance`: current balance from `/financial-summary`.
- `forecast`: array of active recurring commitments in projection order.
- `forecast[].projected_balance`: running balance after subtracting that
  commitment amount.
- `final_projected_balance`: balance after all active recurring commitments are
  subtracted.

Example request:

```http
GET /cash-flow-forecast
```

If there are no active recurring commitments, `forecast` is an empty array and
`final_projected_balance` equals `current_balance`.

### `GET /upcoming-commitments`

Returns only active recurring commitments. The object fields are the same as
`recurring_commitments` in `/financial-summary`.

### `GET /forecast`

Returns the moving-average forecast object used inside `/financial-summary`.

### `GET /income-analysis`

Returns the income analysis object used inside `/financial-summary`.

### `POST /chat`

Optional AI explanation layer. Request body:

```json
{
  "message": "Can I spend Rs 8000 on shoes?"
}
```

Response structure:

```json
{
  "answer": "Backend-computed answer text.",
  "tool_used": "get_safe_to_spend",
  "tool_result": {
    "safe_to_spend": 16000.0
  },
  "ai_provider": "local-rule-based",
  "memory_context": null
}
```

## Environment Variables

Copy `.env.example` to `.env` for local secrets. Do not commit `.env`.

- `GROQ_API_KEY`: optional Groq key for tool-calling chat.
- `GROQ_MODEL`: optional model name, defaults to `openai/gpt-oss-120b`.
- `COGNEE_API_KEY`: optional Cognee API key for persistent financial memory.
- `COGNEE_BASE_URL`: optional tenant-specific Cognee base URL, defaults to `https://api.cognee.ai`.
- `COGNEE_DATASET`: optional Cognee dataset name for Paytm Sense memory.
- `COGNEE_DATASET_ID`: optional Cognee dataset id; when set, it is used instead of `COGNEE_DATASET`.
- `N8N_WEBHOOK_URL`: optional webhook for automation events.
- `DATABASE_URL`: reserved for a future database-backed store.

## Groq Chat

When `GROQ_API_KEY` is set, `POST /chat` sends the user message to Groq with structured tool definitions. Groq chooses a tool, the backend executes it, and Groq receives the actual deterministic tool result before writing the final answer. The configured model is read from `GROQ_MODEL`; the backend does not silently swap it.

Without `GROQ_API_KEY`, chat uses a deterministic local fallback for demo reliability.

## Cognee Memory

When `COGNEE_API_KEY` is set, Paytm Sense uses Cognee's HTTP API with `/api/v1/add`, `/api/v1/cognify`, and `/api/v1/search` for financial goals and intentions. `/api/v1/add` sends multipart/form-data with a `data` text file part plus either `datasetName` or `datasetId`; `/api/v1/cognify` and `/api/v1/search` use JSON and target either `datasets` or `datasetIds`. Without Cognee credentials, it uses an in-process fallback memory. The fallback is useful for local demo flow but is not persistent across process restarts.

## n8n Automation

When `N8N_WEBHOOK_URL` is set, the backend emits financial-state events while serving financial summary/safe-to-spend requests and after new transactions:

- `financial_state_updated`
- `safe_to_spend_changed`
- `active_recurring_commitment_changed`
- `recurring_commitment_became_inactive`

Without a webhook URL, event publishing returns a skipped delivery result and core calculations continue normally.

## Fallback Behavior

The backend remains runnable with the included synthetic dataset even when Groq, Cognee, n8n, and PostgreSQL are unavailable. External services never calculate authoritative financial values.

## Prototype Limitations

- Recurring detection uses the dataset recurring flag as a candidate signal.
- Forecasting uses simple moving averages, not a complex ML model.
- Income analysis is a transparent heuristic estimate, not financial advice.
- The CSV store is suitable for demo data, not concurrent production writes.
