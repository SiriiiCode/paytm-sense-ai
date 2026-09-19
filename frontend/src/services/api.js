const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
    ...options,
  });

  if (!response.ok) {
    let detail = "Unable to complete request.";
    try {
      const body = await response.json();
      detail = Array.isArray(body.detail)
        ? body.detail.map((item) => item.msg).join(" ")
        : body.detail || detail;
    } catch {
      detail = response.statusText || detail;
    }
    throw new Error(detail);
  }

  return response.json();
}

export const api = {
  baseUrl: API_BASE_URL,
  health: () => request("/"),
  getFinancialSummary: () => request("/financial-summary"),
  getSafeToSpend: () => request("/safe-to-spend"),
  getTransactions: () => request("/transactions"),
  addTransaction: (payload) =>
    request("/transactions", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  getCashflow: () => request("/cashflow"),
  getCommitmentForecast: () => request("/cash-flow-forecast"),
  getUpcomingCommitments: () => request("/upcoming-commitments"),
  getForecast: () => request("/forecast"),
  getIncomeAnalysis: () => request("/income-analysis"),
  getIncomePathways: () => request("/income-pathways"),
  getIncomeGuidance: (payload) =>
    request("/income-guidance", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  chat: (message) =>
    request("/chat", {
      method: "POST",
      body: JSON.stringify({ message }),
    }),
};
