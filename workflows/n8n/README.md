# Paytm Sense n8n Webhook

The backend can emit optional automation events to n8n when `N8N_WEBHOOK_URL` is
configured. Core financial calculations do not depend on n8n.

Financial-risk alerts and user notifications should be handled in n8n. For SMS
or WhatsApp delivery, add Twilio nodes or HTTP Request nodes after the webhook
and Switch nodes; Twilio credentials belong in n8n credentials, not in this
repository.

Example event payload:

```json
{
  "event_type": "safe_to_spend_changed",
  "payload": {
    "previous": 12000,
    "current": 9500,
    "delta": -2500
  }
}
```

Supported event types:

- `financial_state_updated`
- `safe_to_spend_changed`
- `active_recurring_commitment_changed`
- `recurring_commitment_became_inactive`

Suggested workflow:

1. Create an n8n Webhook trigger.
2. Set the backend `N8N_WEBHOOK_URL` to the production webhook URL.
3. Add a Switch node on `event_type`.
4. For `safe_to_spend_changed`, notify when `payload.delta` is negative.
5. For recurring commitment events, notify the user or add a review task.
6. Connect Twilio notification actions where financial-risk alerts are needed.

Local API base URL:

```text
http://localhost:8000
```

Backend routes that may trigger or support alert workflows:

- `POST /transactions`: adds a transaction and recalculates financial state.
- `GET /financial-summary`: returns dashboard state and publishes optional
  financial-state events.
- `GET /safe-to-spend`: returns safe-to-spend state and publishes optional
  financial-state events.
- `GET /cash-flow-forecast`: returns active-commitment balance projection.
