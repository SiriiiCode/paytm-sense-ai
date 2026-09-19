import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import logo from "./assets/branding/The problem.png";
import { api } from "./services/api.js";

const navItems = [
  { id: "dashboard", label: "Dashboard" },
  { id: "transactions", label: "Transactions" },
  { id: "cashflow", label: "Cash Flow" },
  { id: "firewall", label: "Firewall" },
  { id: "income", label: "Income" },
  { id: "assistant", label: "Assistant" },
];

const pillars = [
  ["PROTECT", "Financial Firewall"],
  ["PREDICT", "Cash flow intelligence"],
  ["OPTIMIZE", "Smarter Financial planning"],
  ["GROW", "Income pathways"],
];

const currency = new Intl.NumberFormat("en-IN", {
  style: "currency",
  currency: "INR",
  maximumFractionDigits: 0,
});

function formatMoney(value) {
  return currency.format(Number(value || 0));
}

function formatDate(value) {
  if (!value) return "Not scheduled";
  return new Intl.DateTimeFormat("en-IN", {
    day: "numeric",
    month: "short",
    year: "numeric",
  }).format(new Date(value));
}

function App() {
  const [entered, setEntered] = useState(false);
  const [active, setActive] = useState("dashboard");
  const [data, setData] = useState({
    summary: null,
    safe: null,
    transactions: [],
    commitmentForecast: null,
    upcoming: [],
    forecast: null,
    income: null,
    pathways: [],
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    let ignore = false;

    async function load() {
      setLoading(true);
      setError("");
      try {
        const [
          summary,
          safe,
          transactions,
          commitmentForecast,
          upcoming,
          forecast,
          income,
          pathways,
        ] = await Promise.all([
          api.getFinancialSummary(),
          api.getSafeToSpend(),
          api.getTransactions(),
          api.getCommitmentForecast(),
          api.getUpcomingCommitments(),
          api.getForecast(),
          api.getIncomeAnalysis(),
          api.getIncomePathways(),
        ]);
        if (!ignore) {
          setData({
            summary,
            safe,
            transactions,
            commitmentForecast,
            upcoming,
            forecast,
            income,
            pathways,
          });
        }
      } catch (err) {
        if (!ignore) setError(err.message || "Unable to load financial data.");
      } finally {
        if (!ignore) setLoading(false);
      }
    }

    load();
    return () => {
      ignore = true;
    };
  }, [refreshKey]);

  const refresh = () => setRefreshKey((key) => key + 1);

  if (!entered) {
    return <Welcome onEnter={() => setEntered(true)} />;
  }

  return (
    <div className="app-shell">
      <Sidebar active={active} setActive={setActive} />
      <main className="main-panel">
        <Topbar active={active} setActive={setActive} />
        {error ? (
          <ConnectionState error={error} onRetry={refresh} />
        ) : (
          <Screen
            active={active}
            setActive={setActive}
            data={data}
            loading={loading}
            refresh={refresh}
          />
        )}
      </main>
    </div>
  );
}

function Welcome({ onEnter }) {
  return (
    <main className="welcome">
      <header className="welcome-header">
        <img className="welcome-logo" src={logo} alt="Paytm Sense" />
      </header>
      <section className="welcome-hero">
        <div className="welcome-copy">
          <p className="tagline">Make every rupee make sense.</p>
          <h1>
            An AI-powered financial
            <span> decision layer </span>
            built into payments.
          </h1>
          <p className="welcome-text">
            Understand your money, anticipate what is coming, protect what
            matters, and build smarter paths toward your goals.
          </p>
          <button className="primary-button hero-cta" onClick={onEnter}>
            Get Started <span aria-hidden="true">-&gt;</span>
          </button>
        </div>
        <HeroIntelligenceVisual />
      </section>
      <section className="landing-feature-strip" aria-label="Paytm Sense pillars">
        {pillars.map(([title, text]) => (
          <article key={title}>
            <span>{title.slice(0, 1)}</span>
            <div>
              <strong>{title}</strong>
              <p>{text}</p>
            </div>
          </article>
        ))}
      </section>
    </main>
  );
}

function HeroIntelligenceVisual() {
  return (
    <section className="hero-visual" aria-label="Financial intelligence visual">
      <div className="sense-orbit" aria-hidden="true">
        <div className="orbit-ring outer" />
        <div className="orbit-ring inner" />
        <div className="sense-core">
          <strong>Rs</strong>
          <span>Sense</span>
        </div>
        <div className="mini-node node-safe">
          <b>Safe</b>
          <span>to Spend</span>
        </div>
        <div className="mini-node node-flow">
          <b>Cash Flow</b>
          <span>Forecast</span>
        </div>
        <div className="mini-node node-protect">
          <b>Protected</b>
          <span>Money</span>
        </div>
        <div className="mini-node node-grow">
          <b>Income</b>
          <span>Pathways</span>
        </div>
      </div>
    </section>
  );
}

function Sidebar({ active, setActive }) {
  return (
    <aside className="sidebar">
      <img className="brand-mark" src={logo} alt="Paytm Sense" />
      <nav aria-label="Primary">
        {navItems.map((item) => (
          <button
            key={item.id}
            className={active === item.id ? "nav-item active" : "nav-item"}
            onClick={() => setActive(item.id)}
          >
            {item.label}
          </button>
        ))}
      </nav>
      <div className="sidebar-note">
        <strong>TRACK</strong>
        <span>AI-powered financial journeys</span>
      </div>
    </aside>
  );
}

function Topbar({ active, setActive }) {
  return (
    <header className="topbar">
      <img src={logo} alt="Paytm Sense" />
      <select
        value={active}
        onChange={(event) => setActive(event.target.value)}
        aria-label="Choose section"
      >
        {navItems.map((item) => (
          <option key={item.id} value={item.id}>
            {item.label}
          </option>
        ))}
      </select>
    </header>
  );
}

function Screen({ active, setActive, data, loading, refresh }) {
  if (loading) return <Skeleton />;

  if (active === "transactions") {
    return (
      <Transactions
        transactions={data.transactions}
        onCreated={refresh}
      />
    );
  }
  if (active === "cashflow") {
    return (
      <CashFlow
        summary={data.summary}
        forecast={data.forecast}
        commitmentForecast={data.commitmentForecast}
      />
    );
  }
  if (active === "firewall") {
    return <Firewall safe={data.safe} commitments={data.upcoming} />;
  }
  if (active === "income") {
    return (
      <Income
        analysis={data.income}
        pathways={data.pathways}
        onGuidance={() => setActive("income-guidance")}
      />
    );
  }
  if (active === "income-guidance") {
    return (
      <IncomeGuidance
        pathways={data.pathways}
        onBackToIncome={() => setActive("income")}
      />
    );
  }
  if (active === "assistant") {
    return <Assistant />;
  }

  return (
    <Dashboard
      data={data}
      setActive={setActive}
    />
  );
}

function Dashboard({ data, setActive }) {
  const { summary, safe, upcoming, commitmentForecast } = data;
  const ratio = summary?.balance
    ? Math.min((summary.safe_to_spend / summary.balance) * 100, 100)
    : 0;

  return (
    <div className="screen">
      <SectionTitle
        kicker="Financial command center"
        title="Your money, protected and readable."
        action={<button onClick={() => setActive("assistant")}>Ask Paytm Sense</button>}
      />
      <section className="hero-metrics">
        <MetricCard label="Current Balance" value={formatMoney(summary?.balance)} />
        <article className="safe-card">
          <span>Safe to Spend</span>
          <strong>{formatMoney(summary?.safe_to_spend)}</strong>
          <div className="progress-track">
            <div style={{ width: `${ratio}%` }} />
          </div>
          <p>
            Protected money stays reserved for commitments, savings goals, and
            emergency buffer.
          </p>
        </article>
        <MetricCard label="Protected Money" value={formatMoney(summary?.protected_money)} />
      </section>
      <section className="dashboard-grid">
        <Panel title="Upcoming commitments" cta="View cash flow" onCta={() => setActive("cashflow")}>
          <CommitmentList items={upcoming} />
        </Panel>
        <Panel title="Cash-flow forecast">
          <ForecastTimeline forecast={commitmentForecast} />
        </Panel>
        <Panel title="Financial firewall">
          <FirewallMini safe={safe} />
        </Panel>
        <Panel title="Income pathways">
          <IncomeMini analysis={summary?.income_analysis} />
        </Panel>
      </section>
    </div>
  );
}

function Transactions({ transactions, onCreated }) {
  const [form, setForm] = useState({
    date: new Date().toISOString().slice(0, 10),
    description: "",
    amount: "",
    type: "Debit",
    category: "",
    recurring: false,
  });
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  async function submit(event) {
    event.preventDefault();
    setSaving(true);
    setError("");
    setMessage("");
    try {
      await api.addTransaction({
        ...form,
        amount: Number(form.amount),
      });
      setForm({
        date: new Date().toISOString().slice(0, 10),
        description: "",
        amount: "",
        type: "Debit",
        category: "",
        recurring: false,
      });
      setMessage("Transaction added. Financial state refreshed.");
      onCreated();
    } catch (err) {
      setError(err.message || "Unable to add transaction.");
    } finally {
      setSaving(false);
    }
  }

  const visible = [...transactions].reverse().slice(0, 80);

  return (
    <div className="screen">
      <SectionTitle kicker="Transactions" title="Add and review financial activity." />
      <section className="transactions-layout">
        <form className="entry-form" onSubmit={submit}>
          <label>
            Date
            <input
              type="date"
              value={form.date}
              onChange={(event) => setForm({ ...form, date: event.target.value })}
              required
            />
          </label>
          <label>
            Description
            <input
              value={form.description}
              onChange={(event) =>
                setForm({ ...form, description: event.target.value })
              }
              placeholder="Merchant or source"
              required
            />
          </label>
          <label>
            Amount
            <input
              type="number"
              min="0.01"
              step="0.01"
              value={form.amount}
              onChange={(event) => setForm({ ...form, amount: event.target.value })}
              required
            />
          </label>
          <label>
            Type
            <select
              value={form.type}
              onChange={(event) => setForm({ ...form, type: event.target.value })}
            >
              <option>Debit</option>
              <option>Credit</option>
            </select>
          </label>
          <label>
            Category
            <input
              value={form.category}
              onChange={(event) => setForm({ ...form, category: event.target.value })}
              placeholder="Food, Income, Housing"
              required
            />
          </label>
          <label className="checkbox-row">
            <input
              type="checkbox"
              checked={form.recurring}
              onChange={(event) => setForm({ ...form, recurring: event.target.checked })}
            />
            Recurring commitment
          </label>
          <button className="primary-button" disabled={saving}>
            {saving ? "Adding..." : "+ Add Transaction"}
          </button>
          {message && <p className="success-text">{message}</p>}
          {error && <p className="error-text">{error}</p>}
        </form>
        <Panel title="Recent transactions">
          {visible.length === 0 ? (
            <EmptyState text="No transactions yet." />
          ) : (
            <div className="transaction-list">
              {visible.map((item) => (
                <article className="transaction-row" key={item.transaction_id}>
                  <div>
                    <strong>{item.description}</strong>
                    <span>
                      {formatDate(item.date)} - {item.category}
                      {item.recurring ? " - Recurring" : ""}
                    </span>
                  </div>
                  <b className={item.type === "Credit" ? "credit" : "debit"}>
                    {item.type === "Credit" ? "+" : "-"}
                    {formatMoney(item.amount)}
                  </b>
                </article>
              ))}
            </div>
          )}
        </Panel>
      </section>
    </div>
  );
}

function CashFlow({ summary, forecast, commitmentForecast }) {
  return (
    <div className="screen">
      <SectionTitle kicker="Predict" title="Cash flow intelligence." />
      <section className="hero-metrics compact">
        <MetricCard label="Forecast Income" value={formatMoney(forecast?.forecast_income)} />
        <MetricCard label="Forecast Expenses" value={formatMoney(forecast?.forecast_expenses)} />
        <MetricCard label="Projected Balance" value={formatMoney(forecast?.projected_balance)} />
      </section>
      <section className="dashboard-grid two">
        <Panel title="Balance progression">
          <ForecastTimeline forecast={commitmentForecast} />
        </Panel>
        <Panel title="Monthly cash flow">
          <MonthlyBars rows={summary?.cashflow?.monthly || []} />
        </Panel>
      </section>
      <Panel title="Forecast assumptions">
        <ul className="clean-list">
          {(forecast?.assumptions || []).map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      </Panel>
    </div>
  );
}

function Firewall({ safe, commitments }) {
  const protectedRatio = safe?.balance
    ? Math.min((safe.protected_money / safe.balance) * 100, 100)
    : 0;

  return (
    <div className="screen">
      <SectionTitle kicker="Protect" title="Financial Firewall." />
      <section className="firewall-hero">
        <div className="shield-orbit" aria-hidden="true">
          <span />
        </div>
        <div>
          <p className="status-pill">Protected</p>
          <h2>You are protected.</h2>
          <p>
            No separate frontend risk engine is running. This view reflects
            backend-computed protected money and leaves a clean boundary for
            future n8n risk alerts.
          </p>
        </div>
      </section>
      <section className="dashboard-grid two">
        <Panel title="Protected allocation">
          <div className="progress-track tall">
            <div style={{ width: `${protectedRatio}%` }} />
          </div>
          <div className="money-split">
            <span>Recurring: {formatMoney(safe?.recurring_commitments)}</span>
            <span>Savings: {formatMoney(safe?.savings_goal)}</span>
            <span>Emergency: {formatMoney(safe?.emergency_buffer)}</span>
          </div>
        </Panel>
        <Panel title="Active commitments">
          <CommitmentList items={commitments} />
        </Panel>
      </section>
    </div>
  );
}

function Income({ analysis, pathways, onGuidance }) {
  return (
    <div className="screen">
      <SectionTitle
        kicker="Grow"
        title="Income pathways."
        action={<button onClick={onGuidance}>Get Guidance</button>}
      />
      <section className="hero-metrics compact">
        <MetricCard label="Current Income" value={formatMoney(analysis?.current_income)} />
        <MetricCard label="Comfortable Target" value={formatMoney(analysis?.comfortable_target)} />
        <MetricCard label="Income Gap" value={formatMoney(analysis?.income_gap)} />
      </section>
      <section className="guidance-cta">
        <div>
          <span>Get Guidance</span>
          <h2>Find realistic ways to build the additional income you need.</h2>
          <p>
            Choose a backend-calculated target, share your career profile, and
            receive recommended roles, skill gaps, and a practical action plan.
          </p>
        </div>
        <button className="primary-button" onClick={onGuidance}>
          Get Guidance
        </button>
      </section>
      <section className="pathway-grid">
        {(pathways || []).map((pathway) => (
          <article className="pathway-card" key={pathway.id}>
            <span>{pathway.name}</span>
            <strong>{formatMoney(pathway.target_additional_income)} / month</strong>
            <p>{pathway.description}</p>
          </article>
        ))}
      </section>
      <Panel title="Target ladder">
        <div className="income-ladder">
          <span>Survival {formatMoney(analysis?.survival_target)}</span>
          <span>Comfortable {formatMoney(analysis?.comfortable_target)}</span>
          <span>Aspirational {formatMoney(analysis?.aspirational_target)}</span>
        </div>
      </Panel>
      <Panel title="Backend analysis notes">
        <ul className="clean-list">
          {(analysis?.heuristics || []).map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      </Panel>
    </div>
  );
}

const defaultCareerProfile = {
  education_status: "Student",
  highest_qualification: "",
  field_of_study: "",
  graduation_year: "",
  employment_status: "Student",
  current_designation: "",
  years_of_experience: 0,
  industry: "",
  previous_experience: "",
  skills: [{ skill: "Communication", proficiency: "Beginner" }],
  preferred_job_types: ["Part-time"],
  preferred_work_mode: "Flexible",
  preferred_location: "India",
  hours_available_per_week: 10,
  minimum_additional_income: "",
  industries_of_interest: [],
  roles_of_interest: [],
  work_to_avoid: "",
  willingness_to_learn: "Medium",
  career_context: "",
};

function IncomeGuidance({ pathways, onBackToIncome }) {
  const [step, setStep] = useState(1);
  const [selectedPathwayId, setSelectedPathwayId] = useState(pathways?.[0]?.id || "comfortable");
  const [profile, setProfile] = useState(defaultCareerProfile);
  const [skillDraft, setSkillDraft] = useState("");
  const [skillLevel, setSkillLevel] = useState("Beginner");
  const [rememberProfile, setRememberProfile] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const selectedPathway = (pathways || []).find((item) => item.id === selectedPathwayId);

  function update(field, value) {
    setProfile((current) => ({ ...current, [field]: value }));
  }

  function addSkill() {
    const skill = skillDraft.trim();
    if (!skill) return;
    setProfile((current) => ({
      ...current,
      skills: [...current.skills, { skill, proficiency: skillLevel }],
    }));
    setSkillDraft("");
  }

  function removeSkill(index) {
    setProfile((current) => ({
      ...current,
      skills: current.skills.filter((_, itemIndex) => itemIndex !== index),
    }));
  }

  async function analyze() {
    setLoading(true);
    setError("");
    setResult(null);
    try {
      const userId = getDemoUserId();
      const payload = {
        user_id: userId,
        pathway_id: selectedPathwayId,
        remember_profile: rememberProfile,
        career_profile: normalizeCareerProfile(profile),
      };
      const response = await api.getIncomeGuidance(payload);
      setResult(response);
      setStep(5);
    } catch (err) {
      setError(err.message || "We couldn't analyze your pathway right now.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="screen">
      <SectionTitle
        kicker="Grow"
        title="Build your path to additional income."
        action={<button onClick={onBackToIncome}>Back to Income</button>}
      />
      <div className="guidance-progress">Step {step} of 5</div>
      {step === 1 && (
        <GuidanceStep title="Choose your pathway">
          <div className="pathway-grid">
            {(pathways || []).map((pathway) => (
              <button
                type="button"
                className={pathway.id === selectedPathwayId ? "pathway-card selected" : "pathway-card"}
                key={pathway.id}
                onClick={() => setSelectedPathwayId(pathway.id)}
              >
                <span>{pathway.name}</span>
                <strong>{formatMoney(pathway.target_additional_income)} / month</strong>
                <p>{pathway.description}</p>
              </button>
            ))}
          </div>
        </GuidanceStep>
      )}
      {step === 2 && (
        <GuidanceStep title="Build your career profile">
          <div className="form-grid">
            <SelectField label="Education status" value={profile.education_status} onChange={(value) => update("education_status", value)} options={["Student", "Graduate", "Postgraduate", "Diploma", "Other"]} />
            <TextField label="Highest qualification" value={profile.highest_qualification} onChange={(value) => update("highest_qualification", value)} />
            <TextField label="Field / specialization" value={profile.field_of_study} onChange={(value) => update("field_of_study", value)} />
            <TextField label="Graduation year" type="number" value={profile.graduation_year} onChange={(value) => update("graduation_year", value)} />
            <SelectField label="Employment status" value={profile.employment_status} onChange={(value) => update("employment_status", value)} options={["Student", "Intern", "Employed", "Freelancer", "Business Owner", "Unemployed", "Other"]} />
            <TextField label="Current designation" value={profile.current_designation} onChange={(value) => update("current_designation", value)} />
            <TextField label="Years of experience" type="number" value={profile.years_of_experience} onChange={(value) => update("years_of_experience", value)} />
            <TextField label="Industry" value={profile.industry} onChange={(value) => update("industry", value)} />
          </div>
        </GuidanceStep>
      )}
      {step === 3 && (
        <GuidanceStep title="Skills and preferences">
          <div className="skill-builder">
            <input value={skillDraft} onChange={(event) => setSkillDraft(event.target.value)} placeholder="Add a skill" />
            <select value={skillLevel} onChange={(event) => setSkillLevel(event.target.value)}>
              <option>Beginner</option>
              <option>Intermediate</option>
              <option>Advanced</option>
            </select>
            <button type="button" onClick={addSkill}>Add</button>
          </div>
          <div className="skill-chips">
            {profile.skills.map((item, index) => (
              <button type="button" key={`${item.skill}-${index}`} onClick={() => removeSkill(index)}>
                {item.skill} - {item.proficiency}
              </button>
            ))}
          </div>
          <div className="form-grid">
            <TextField label="Preferred location" value={profile.preferred_location} onChange={(value) => update("preferred_location", value)} />
            <TextField label="Hours available per week" type="number" value={profile.hours_available_per_week} onChange={(value) => update("hours_available_per_week", value)} />
            <TextField label="Roles of interest" value={profile.roles_of_interest.join(", ")} onChange={(value) => update("roles_of_interest", splitCsv(value))} />
            <TextField label="Industries of interest" value={profile.industries_of_interest.join(", ")} onChange={(value) => update("industries_of_interest", splitCsv(value))} />
            <SelectField label="Work mode" value={profile.preferred_work_mode} onChange={(value) => update("preferred_work_mode", value)} options={["Remote", "Hybrid", "On-site", "Flexible"]} />
            <SelectField label="Willingness to learn" value={profile.willingness_to_learn} onChange={(value) => update("willingness_to_learn", value)} options={["Low", "Medium", "High"]} />
          </div>
        </GuidanceStep>
      )}
      {step === 4 && (
        <GuidanceStep title="Review and analyze">
          <div className="review-grid">
            <MetricCard label="Selected Pathway" value={selectedPathway?.name || "Pathway"} />
            <MetricCard label="Additional Income" value={formatMoney(selectedPathway?.target_additional_income)} />
          </div>
          <label className="text-area-label">
            Career context
            <textarea
              value={profile.career_context}
              onChange={(event) => update("career_context", event.target.value)}
              placeholder="Tell Paytm Sense anything else about your career goals."
            />
          </label>
          <label className="checkbox-row memory-consent">
            <input
              type="checkbox"
              checked={rememberProfile}
              onChange={(event) => setRememberProfile(event.target.checked)}
            />
            Remember my career profile for future guidance
          </label>
        </GuidanceStep>
      )}
      {step === 5 && (
        <GuidanceResults result={result} loading={loading} error={error} onRetry={analyze} />
      )}
      {step < 5 && (
        <div className="guidance-actions">
          <button disabled={step === 1} onClick={() => setStep((value) => Math.max(1, value - 1))}>
            Back
          </button>
          {step < 4 ? (
            <button className="primary-button" onClick={() => setStep((value) => value + 1)}>
              Continue
            </button>
          ) : (
            <button className="primary-button" disabled={loading || !profile.skills.length} onClick={analyze}>
              {loading ? "Analyzing..." : "Analyze My Pathway"}
            </button>
          )}
        </div>
      )}
      {loading && <GuidanceLoading />}
      {error && step < 5 && <p className="error-text">{error}</p>}
    </div>
  );
}

function GuidanceStep({ title, children }) {
  return (
    <section className="guidance-step">
      <h2>{title}</h2>
      {children}
    </section>
  );
}

function TextField({ label, value, onChange, type = "text" }) {
  return (
    <label>
      {label}
      <input type={type} value={value} onChange={(event) => onChange(event.target.value)} />
    </label>
  );
}

function SelectField({ label, value, onChange, options }) {
  return (
    <label>
      {label}
      <select value={value} onChange={(event) => onChange(event.target.value)}>
        {options.map((option) => <option key={option}>{option}</option>)}
      </select>
    </label>
  );
}

function GuidanceLoading() {
  return (
    <section className="guidance-loading">
      <span>Analyzing your profile</span>
      <span>Connecting your skills to opportunities</span>
      <span>Identifying skill gaps</span>
      <span>Building your action plan</span>
    </section>
  );
}

function GuidanceResults({ result, loading, error, onRetry }) {
  if (loading) return null;
  if (error) {
    return (
      <section className="connection-state compact-state">
        <h1>We couldn't analyze your pathway right now.</h1>
        <p>{error}</p>
        <button className="primary-button" onClick={onRetry}>Try Again</button>
      </section>
    );
  }
  if (!result) return null;
  return (
    <section className="guidance-results">
      <div className="guidance-hero">
        <span>Your Income Pathway</span>
        <h2>{result.selected_pathway.name}</h2>
        <strong>{formatMoney(result.selected_pathway.target_additional_income)} / month</strong>
        <p>{result.profile_summary}</p>
      </div>
      <Panel title="Best-fit roles">
        <div className="role-grid">
          {result.recommended_roles.map((role) => (
            <article className="role-card" key={role.role}>
              <h3>{role.role}</h3>
              <p>{role.why_it_fits}</p>
              <ChipGroup label="Existing" items={role.skills_user_already_has} />
              <ChipGroup label="Gaps" items={role.skill_gaps} />
              <ChipGroup label="Search" items={role.search_queries} />
            </article>
          ))}
        </div>
      </Panel>
      <section className="dashboard-grid two">
        <Panel title="Build next">
          <ChipGroup items={result.skill_gaps} />
        </Panel>
        <Panel title="Action plan">
          <div className="action-plan">
            {result.action_plan.map((item) => (
              <article key={item.period}>
                <strong>{item.period}</strong>
                <ul>{item.actions.map((action) => <li key={action}>{action}</li>)}</ul>
              </article>
            ))}
          </div>
        </Panel>
      </section>
      {result.memory_context.enabled && (
        <p className="memory-note">
          {result.memory_context.remembered
            ? "Career memory saved for future guidance."
            : "Career memory was not saved. Configure Cognee to persist this pathway."}
        </p>
      )}
    </section>
  );
}

function ChipGroup({ label, items }) {
  const values = (items || []).filter(Boolean);
  if (!values.length) return null;
  return (
    <div className="chip-group">
      {label && <span>{label}</span>}
      {values.map((item) => <b key={item}>{item}</b>)}
    </div>
  );
}

function normalizeCareerProfile(profile) {
  return {
    ...profile,
    graduation_year: profile.graduation_year ? Number(profile.graduation_year) : null,
    years_of_experience: Number(profile.years_of_experience || 0),
    hours_available_per_week: profile.hours_available_per_week ? Number(profile.hours_available_per_week) : null,
    minimum_additional_income: profile.minimum_additional_income ? Number(profile.minimum_additional_income) : null,
    skills: profile.skills.filter((item) => item.skill.trim()),
  };
}

function splitCsv(value) {
  return value.split(",").map((item) => item.trim()).filter(Boolean);
}

function getDemoUserId() {
  const key = "paytm-sense-demo-user-id";
  const existing = window.localStorage.getItem(key);
  if (existing) return existing;
  const created = `demo-user-${crypto.randomUUID()}`;
  window.localStorage.setItem(key, created);
  return created;
}

function Assistant() {
  const [messages, setMessages] = useState([
    {
      role: "assistant",
      text: "### Paytm Sense\nAsk about safe-to-spend, commitments, income, or forecast.",
    },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(event) {
    event.preventDefault();
    const question = input.trim();
    if (!question) return;
    setMessages((items) => [...items, { role: "user", text: question }]);
    setInput("");
    setLoading(true);
    try {
      const response = await api.chat(question);
      setMessages((items) => [
        ...items,
        {
          role: "assistant",
          text: response.answer,
          response,
        },
      ]);
    } catch (err) {
      setMessages((items) => [
        ...items,
        { role: "assistant", text: err.message || "Assistant is unavailable." },
      ]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="screen">
      <SectionTitle kicker="Ask Paytm Sense" title="Financial assistant." />
      <section className="chat-panel">
        <div className="assistant-intro">
          <strong>Paytm Sense</strong>
          <span>Concise financial answers powered by backend intelligence.</span>
        </div>
        <div className="prompt-row">
          {["Can I afford this purchase?", "How much can I safely spend?", "When is my next major payment?"].map((text) => (
            <button key={text} onClick={() => setInput(text)}>
              {text}
            </button>
          ))}
        </div>
        <div className="messages">
          {messages.map((item, index) => (
            <ChatMessage item={item} key={`${item.role}-${index}`} />
          ))}
          {loading && (
            <article className="message assistant answer-card">
              <div className="answer-brand">Paytm Sense</div>
              <p>Thinking through your financial state...</p>
            </article>
          )}
        </div>
        <form className="chat-form" onSubmit={submit}>
          <input
            value={input}
            onChange={(event) => setInput(event.target.value)}
            placeholder="Ask about your financial state"
            aria-label="Ask Paytm Sense"
          />
          <button className="primary-button">Send</button>
        </form>
      </section>
    </div>
  );
}

function ChatMessage({ item }) {
  if (item.role === "user") {
    return (
      <article className="message user">
        <span>You</span>
        <p>{item.text}</p>
      </article>
    );
  }

  const metrics = getAssistantMetrics(item.response);

  return (
    <article className="message assistant answer-card">
      <div className="answer-brand">Paytm Sense</div>
      {metrics.length > 0 && (
        <div className="answer-metrics">
          {metrics.map((metric) => (
            <div className="answer-metric" key={metric.label}>
              <strong>{metric.value}</strong>
              <span>{metric.label}</span>
            </div>
          ))}
        </div>
      )}
      <div className="markdown-body">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>
          {item.text}
        </ReactMarkdown>
      </div>
    </article>
  );
}

function getAssistantMetrics(response) {
  if (!response?.tool_result) return [];

  const candidates = Array.isArray(response.tool_result)
    ? response.tool_result.map((item) => item?.result ?? item)
    : [response.tool_result];

  const metrics = [];
  const seen = new Set();

  function add(label, value) {
    if (value === undefined || value === null || seen.has(label)) return;
    seen.add(label);
    metrics.push({ label, value: formatMoney(value) });
  }

  for (const candidate of candidates) {
    if (Array.isArray(candidate)) {
      const nextCommitment = candidate.find((item) => item?.amount);
      if (nextCommitment) add("Next Commitment", nextCommitment.amount);
      continue;
    }

    if (!candidate || typeof candidate !== "object") continue;

    add("Safe to Spend", candidate.safe_to_spend);
    add("Protected", candidate.protected_money);
    add("Balance", candidate.balance);
    add("Projected Balance", candidate.projected_balance);
    add("Income Gap", candidate.income_gap);
    add("Comfortable Target", candidate.comfortable_target);
    add("Monthly Income", candidate.current_income);
  }

  return metrics.slice(0, 4);
}

function MetricCard({ label, value }) {
  return (
    <article className="metric-card">
      <span>{label}</span>
      <strong>{value}</strong>
    </article>
  );
}

function Panel({ title, children, cta, onCta }) {
  return (
    <section className="panel">
      <div className="panel-header">
        <h2>{title}</h2>
        {cta && <button onClick={onCta}>{cta}</button>}
      </div>
      {children}
    </section>
  );
}

function SectionTitle({ kicker, title, action }) {
  return (
    <div className="section-title">
      <div>
        <span>{kicker}</span>
        <h1>{title}</h1>
      </div>
      {action}
    </div>
  );
}

function CommitmentList({ items }) {
  if (!items || items.length === 0) {
    return <EmptyState text="No upcoming commitments." />;
  }
  return (
    <div className="commitment-list">
      {items.slice(0, 6).map((item) => (
        <article className="commitment-row" key={`${item.description}-${item.category}`}>
          <div>
            <strong>{item.description}</strong>
            <span>
              {item.category} - {item.frequency} - {formatDate(item.next_expected_date)}
            </span>
          </div>
          <b>{formatMoney(item.amount)}</b>
        </article>
      ))}
    </div>
  );
}

function ForecastTimeline({ forecast }) {
  const rows = forecast?.forecast || [];
  if (!rows.length) {
    return <EmptyState text="No commitment forecast available." />;
  }
  return (
    <div className="timeline">
      <article>
        <span>Current balance</span>
        <strong>{formatMoney(forecast.current_balance)}</strong>
      </article>
      {rows.map((row) => (
        <article key={`${row.description}-${row.projected_balance}`}>
          <span>
            {row.description} - {formatDate(row.next_expected_date)}
          </span>
          <strong>{formatMoney(row.projected_balance)}</strong>
          <small>-{formatMoney(row.amount)}</small>
        </article>
      ))}
    </div>
  );
}

function MonthlyBars({ rows }) {
  const max = Math.max(...rows.map((row) => Math.max(row.income, row.expenses)), 1);
  if (!rows.length) return <EmptyState text="No cash-flow history yet." />;
  return (
    <div className="monthly-bars">
      {rows.slice(-6).map((row) => (
        <article key={row.month}>
          <span>{row.month}</span>
          <div>
            <i style={{ width: `${(row.income / max) * 100}%` }} />
            <b style={{ width: `${(row.expenses / max) * 100}%` }} />
          </div>
          <strong>{formatMoney(row.net)}</strong>
        </article>
      ))}
    </div>
  );
}

function FirewallMini({ safe }) {
  return (
    <div className="mini-copy">
      <p className="status-pill">Protected</p>
      <strong>{formatMoney(safe?.safe_to_spend)} safely available</strong>
      <span>{formatMoney(safe?.protected_money)} remains protected.</span>
    </div>
  );
}

function IncomeMini({ analysis }) {
  return (
    <div className="mini-copy">
      <strong>{formatMoney(analysis?.comfortable_target)}</strong>
      <span>Comfortable monthly target from backend heuristics.</span>
    </div>
  );
}

function Skeleton() {
  return (
    <div className="screen">
      <div className="skeleton title" />
      <section className="hero-metrics">
        <div className="skeleton card" />
        <div className="skeleton card" />
        <div className="skeleton card" />
      </section>
      <div className="skeleton wide" />
    </div>
  );
}

function EmptyState({ text }) {
  return <p className="empty-state">{text}</p>;
}

function ConnectionState({ error, onRetry }) {
  return (
    <section className="connection-state">
      <img src={logo} alt="Paytm Sense" />
      <h1>Unable to load your financial data.</h1>
      <p>
        Check that the FastAPI backend is running at {api.baseUrl}. Paytm Sense
        will not show substitute financial values while the API is unavailable.
      </p>
      <code>{error}</code>
      <button className="primary-button" onClick={onRetry}>
        Try Again
      </button>
    </section>
  );
}

export default App;
