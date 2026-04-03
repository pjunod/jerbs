/*
 * JERBS RESULTS ARTIFACT TEMPLATE
 * ================================
 * Claude: Copy this file and replace RESULTS_DATA below with actual screening data.
 * Save the populated file as a .jsx artifact and present it to the user.
 * Do NOT put individual job details in the chat message — only a brief summary.
 *
 * DATA SCHEMA — each item in RESULTS_DATA.results and RESULTS_DATA.pending_results:
 * {
 *   source:         "Job Alert Listings" | "Direct Outreach" | "LinkedIn DMs"
 *   message_id:     string   (Gmail message ID)
 *   thread_id:      string
 *   subject:        string
 *   from:           string   (sender name + address)
 *   email_date:     string
 *   company:        string
 *   role:           string
 *   location:       string
 *   verdict:        "pass" | "maybe" | "fail"
 *   reason:         string   (1-sentence explanation)
 *   dealbreaker:    string   (fail only, else "")
 *   comp_assessment: string  (pass/maybe only, else "")
 *   missing_fields: string[] (e.g. ["salary", "equity"])
 *   reply_draft:    string   (full reply text, pass/maybe only, else "")
 *   draft_url:      string   (https://mail.google.com/mail/u/0/#drafts?compose=<id>)
 *   posting_url:    string   (job posting URL if found, else "")
 *   email_url:      string   (https://mail.google.com/mail/u/0/#inbox/<message_id>)
 *   sent:           boolean
 *   from_previous_run: boolean  (true for items from pending_results)
 * }
 *
 * RESULTS_DATA wrapper:
 * {
 *   run_date:      string   ("YYYY-MM-DD")
 *   profile_name:  string
 *   mode:          "dry-run" | "send"
 *   lookback_days: number
 *   pending_results: []     (previous-run items, already merged into results below)
 *   results:       []       (ALL items to display — new + pending combined)
 * }
 *
 * INSTRUCTIONS FOR CLAUDE:
 * 1. Replace the RESULTS_DATA object below with actual data from the screening run.
 * 2. Merge pending_results into results, marking each with from_previous_run: true.
 * 3. Keep all other code exactly as-is.
 * 4. Write the file as a .jsx artifact.
 * 5. In your chat message, include ONLY the brief summary (counts + top leads).
 */

// ─── REPLACE THIS WITH ACTUAL SCREENING DATA ───────────────────────────────
const RESULTS_DATA = {
  run_date: "YYYY-MM-DD",
  profile_name: "My Profile",
  mode: "dry-run",
  lookback_days: 7,
  results: [
    // Example item — Claude replaces this array with real results
    {
      source: "Direct Outreach",
      message_id: "example123",
      thread_id: "thread123",
      subject: "Staff Engineer opportunity at Acme",
      from: "Jane Recruiter <jane@acme.com>",
      email_date: "2026-04-01",
      company: "Acme Corp",
      role: "Staff Engineer",
      location: "Remote (US)",
      verdict: "pass",
      reason: "Strong role match, remote-friendly, comp range covers floor.",
      dealbreaker: "",
      comp_assessment: "Range of $220k–$310k base; solid but ask for upper bound.",
      missing_fields: ["equity"],
      reply_draft: "Hi Jane,\n\nThanks for reaching out — Acme is on my radar and the Staff Engineer scope sounds interesting.\n\nCould you share more about equity and the expected vesting schedule? Happy to set up a call once I have a fuller picture.\n\nBest,\n[Name]",
      draft_url: "https://mail.google.com/mail/u/0/#drafts?compose=example",
      posting_url: "https://acme.com/jobs/staff-engineer",
      email_url: "https://mail.google.com/mail/u/0/#inbox/example123",
      sent: false,
      from_previous_run: false,
    },
  ],
};
// ───────────────────────────────────────────────────────────────────────────

function App() {
  const prefersDark =
    typeof window !== "undefined" &&
    window.matchMedia &&
    window.matchMedia("(prefers-color-scheme: dark)").matches;

  const [dark, setDark] = React.useState(prefersDark);
  const [activeFilter, setActiveFilter] = React.useState("all");
  const [expandedCards, setExpandedCards] = React.useState({});
  const [collapsedSections, setCollapsedSections] = React.useState({});
  const [copiedId, setCopiedId] = React.useState(null);

  const theme = dark ? DARK : LIGHT;

  const results = RESULTS_DATA.results || [];

  const counts = {
    interested: results.filter((r) => r.verdict === "pass").length,
    maybe: results.filter((r) => r.verdict === "maybe").length,
    filtered: results.filter((r) => r.verdict === "fail").length,
  };

  const filtered = results.filter((r) => {
    if (activeFilter === "all") return true;
    if (activeFilter === "interested") return r.verdict === "pass";
    if (activeFilter === "maybe") return r.verdict === "maybe";
    if (activeFilter === "filtered") return r.verdict === "fail";
    return true;
  });

  const passes = ["Job Alert Listings", "Direct Outreach", "LinkedIn DMs"];

  function toggleCard(id) {
    setExpandedCards((prev) => ({ ...prev, [id]: !prev[id] }));
  }

  function toggleSection(section) {
    setCollapsedSections((prev) => ({ ...prev, [section]: !prev[section] }));
  }

  function copyToClipboard(text, id) {
    navigator.clipboard.writeText(text).then(() => {
      setCopiedId(id);
      setTimeout(() => setCopiedId(null), 2000);
    });
  }

  const verdictColor = {
    pass: "#22c55e",
    maybe: "#eab308",
    fail: "#ef4444",
  };

  const verdictLabel = {
    pass: "Interested",
    maybe: "Maybe",
    fail: "Filtered",
  };

  return (
    <div style={{ ...s.page, background: theme.pageBg, color: theme.text, fontFamily: s.page.fontFamily }}>
      {/* Header */}
      <div style={{ ...s.header, background: theme.cardBg, borderBottom: `1px solid ${theme.border}` }}>
        <div>
          <div style={{ ...s.headerTitle, color: theme.text }}>Jerbs Results</div>
          <div style={{ fontSize: "0.75rem", color: theme.muted }}>
            {RESULTS_DATA.run_date} · {RESULTS_DATA.profile_name} ·{" "}
            <span style={{ color: RESULTS_DATA.mode === "send" ? "#ef4444" : theme.muted }}>
              {RESULTS_DATA.mode === "send" ? "SEND MODE" : "dry-run"}
            </span>
          </div>
        </div>
        <button
          onClick={() => setDark((d) => !d)}
          aria-label="Toggle dark/light mode"
          style={{ ...s.iconBtn, background: theme.pillBg, color: theme.text }}
        >
          {dark ? "☀️" : "🌙"}
        </button>
      </div>

      <div style={s.body}>
        {/* Summary stats */}
        <div style={s.statsRow}>
          <Stat label="Interested" count={counts.interested} color="#22c55e" theme={theme} />
          <Stat label="Maybe" count={counts.maybe} color="#eab308" theme={theme} />
          <Stat label="Filtered" count={counts.filtered} color="#ef4444" theme={theme} />
        </div>

        {/* Filter pills */}
        <div style={s.pillRow}>
          {[
            { key: "all", label: `All (${results.length})` },
            { key: "interested", label: `Interested (${counts.interested})` },
            { key: "maybe", label: `Maybe (${counts.maybe})` },
            { key: "filtered", label: `Filtered (${counts.filtered})` },
          ].map((p) => (
            <button
              key={p.key}
              onClick={() => setActiveFilter(p.key)}
              style={{
                ...s.pill,
                background: activeFilter === p.key ? theme.pillActive : theme.pillBg,
                color: activeFilter === p.key ? theme.pillActiveText : theme.text,
                border: `1px solid ${activeFilter === p.key ? theme.pillActive : theme.border}`,
              }}
            >
              {p.label}
            </button>
          ))}
        </div>

        {/* Passes */}
        {passes.map((pass) => {
          const items = filtered.filter((r) => r.source === pass);
          if (items.length === 0) return null;

          // Filtered section collapsed by default
          const defaultCollapsed =
            activeFilter === "all" && items.every((r) => r.verdict === "fail");
          const isCollapsed =
            collapsedSections[pass] !== undefined
              ? collapsedSections[pass]
              : defaultCollapsed;

          return (
            <div key={pass} style={{ marginBottom: "1.25rem" }}>
              {/* Section header */}
              <button
                onClick={() => toggleSection(pass)}
                style={{
                  ...s.sectionHeader,
                  background: theme.sectionBg,
                  color: theme.text,
                  border: `1px solid ${theme.border}`,
                }}
              >
                <span style={s.sectionTitle}>{pass}</span>
                <span style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                  <span style={{ fontSize: "0.75rem", color: theme.muted }}>{items.length} items</span>
                  <span style={{ fontSize: "0.85rem" }}>{isCollapsed ? "▶" : "▼"}</span>
                </span>
              </button>

              {/* Cards */}
              {!isCollapsed &&
                items.map((item, idx) => {
                  const cardId = `${pass}-${idx}`;
                  const expanded = expandedCards[cardId];
                  const hasDetails =
                    item.reason || item.comp_assessment || item.missing_fields?.length || item.reply_draft;

                  return (
                    <div
                      key={cardId}
                      style={{
                        ...s.card,
                        background: theme.cardBg,
                        border: `1px solid ${theme.border}`,
                        borderLeft: `3px solid ${verdictColor[item.verdict] || theme.border}`,
                      }}
                    >
                      {/* Card header — always visible */}
                      <div
                        onClick={() => hasDetails && toggleCard(cardId)}
                        style={{ ...s.cardHeader, cursor: hasDetails ? "pointer" : "default" }}
                      >
                        <div style={s.cardMeta}>
                          <span
                            style={{
                              ...s.verdictDot,
                              background: verdictColor[item.verdict] || theme.border,
                            }}
                          />
                          <div>
                            <div style={{ ...s.companyName, color: theme.text }}>
                              {item.company || "(unknown company)"}
                              {item.from_previous_run && (
                                <span style={{ ...s.badge, background: theme.pillBg, color: theme.muted }}>
                                  prev
                                </span>
                              )}
                            </div>
                            <div style={{ fontSize: "0.8125rem", color: theme.muted }}>
                              {item.role}{item.location ? ` · ${item.location}` : ""}
                            </div>
                          </div>
                        </div>
                        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                          <span
                            style={{
                              fontSize: "0.6875rem",
                              fontWeight: 600,
                              color: verdictColor[item.verdict],
                              textTransform: "uppercase",
                              letterSpacing: "0.03em",
                            }}
                          >
                            {verdictLabel[item.verdict]}
                          </span>
                          {hasDetails && (
                            <span style={{ fontSize: "0.75rem", color: theme.muted }}>
                              {expanded ? "▲" : "▼"}
                            </span>
                          )}
                        </div>
                      </div>

                      {/* Expanded detail */}
                      {expanded && (
                        <div style={{ ...s.cardBody, borderTop: `1px solid ${theme.border}` }}>
                          {item.reason && (
                            <Field label="Reason" value={item.reason} theme={theme} />
                          )}
                          {item.comp_assessment && (
                            <Field label="Comp" value={item.comp_assessment} theme={theme} />
                          )}
                          {item.dealbreaker && (
                            <Field label="Dealbreaker" value={item.dealbreaker} theme={theme} color="#ef4444" />
                          )}
                          {item.missing_fields?.length > 0 && (
                            <Field
                              label="Missing"
                              value={item.missing_fields.join(", ")}
                              theme={theme}
                            />
                          )}

                          {/* Links */}
                          <div style={s.linkRow}>
                            {item.email_url && (
                              <a href={item.email_url} target="_blank" rel="noreferrer" style={{ ...s.link, color: theme.linkColor }}>
                                View email ↗
                              </a>
                            )}
                            {item.posting_url && (
                              <a href={item.posting_url} target="_blank" rel="noreferrer" style={{ ...s.link, color: theme.linkColor }}>
                                Job posting ↗
                              </a>
                            )}
                            {item.draft_url && (
                              <a href={item.draft_url} target="_blank" rel="noreferrer" style={{ ...s.link, color: theme.linkColor }}>
                                Review draft ↗
                              </a>
                            )}
                          </div>

                          {/* Draft reply */}
                          {item.reply_draft && (
                            <div style={{ marginTop: "0.75rem" }}>
                              <div style={{ ...s.fieldLabel, color: theme.muted }}>Draft reply</div>
                              <div
                                style={{
                                  ...s.draftBox,
                                  background: theme.draftBg,
                                  border: `1px solid ${theme.border}`,
                                  color: theme.text,
                                }}
                              >
                                <pre style={s.draftText}>{item.reply_draft}</pre>
                                <button
                                  onClick={() => copyToClipboard(item.reply_draft, cardId)}
                                  style={{
                                    ...s.copyBtn,
                                    background: theme.pillBg,
                                    color: copiedId === cardId ? "#22c55e" : theme.text,
                                    border: `1px solid ${theme.border}`,
                                  }}
                                >
                                  {copiedId === cardId ? "Copied!" : "Copy"}
                                </button>
                              </div>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })}
            </div>
          );
        })}

        {filtered.length === 0 && (
          <div style={{ textAlign: "center", color: theme.muted, padding: "2rem 0" }}>
            No results to show.
          </div>
        )}
      </div>
    </div>
  );
}

function Stat({ label, count, color, theme }) {
  return (
    <div
      style={{
        flex: 1,
        textAlign: "center",
        padding: "0.75rem 0.5rem",
        background: theme.cardBg,
        borderRadius: "0.5rem",
        border: `1px solid ${theme.border}`,
      }}
    >
      <div style={{ fontSize: "1.5rem", fontWeight: 700, color }}>{count}</div>
      <div style={{ fontSize: "0.75rem", color: theme.muted }}>{label}</div>
    </div>
  );
}

function Field({ label, value, theme, color }) {
  return (
    <div style={{ marginBottom: "0.5rem" }}>
      <span style={{ ...s.fieldLabel, color: theme.muted }}>{label}: </span>
      <span style={{ fontSize: "0.8125rem", color: color || theme.text }}>{value}</span>
    </div>
  );
}

// ─── Styles ────────────────────────────────────────────────────────────────

const LIGHT = {
  pageBg: "#f5f5f5",
  cardBg: "#ffffff",
  sectionBg: "#f0f0f0",
  draftBg: "#f9f9f9",
  text: "#111111",
  muted: "#6b7280",
  border: "#e5e7eb",
  pillBg: "#e5e7eb",
  pillActive: "#111111",
  pillActiveText: "#ffffff",
  linkColor: "#2563eb",
};

const DARK = {
  pageBg: "#0f0f0f",
  cardBg: "#1a1a1a",
  sectionBg: "#222222",
  draftBg: "#141414",
  text: "#f0f0f0",
  muted: "#9ca3af",
  border: "#2d2d2d",
  pillBg: "#2d2d2d",
  pillActive: "#f0f0f0",
  pillActiveText: "#111111",
  linkColor: "#60a5fa",
};

const s = {
  page: {
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
    maxWidth: "640px",
    margin: "0 auto",
    minHeight: "100vh",
    fontSize: "0.875rem",
  },
  header: {
    position: "sticky",
    top: 0,
    zIndex: 10,
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    padding: "0.75rem 1rem",
  },
  headerTitle: {
    fontWeight: 700,
    fontSize: "1rem",
  },
  iconBtn: {
    minWidth: "44px",
    minHeight: "44px",
    borderRadius: "50%",
    border: "none",
    cursor: "pointer",
    fontSize: "1.1rem",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
  },
  body: {
    padding: "1rem",
  },
  statsRow: {
    display: "flex",
    gap: "0.5rem",
    marginBottom: "1rem",
  },
  pillRow: {
    display: "flex",
    flexWrap: "wrap",
    gap: "0.4rem",
    marginBottom: "1.25rem",
  },
  pill: {
    padding: "0.4rem 0.75rem",
    borderRadius: "999px",
    fontSize: "0.8125rem",
    cursor: "pointer",
    minHeight: "44px",
    display: "inline-flex",
    alignItems: "center",
    fontWeight: 500,
    lineHeight: 1,
  },
  sectionHeader: {
    width: "100%",
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    padding: "0.625rem 0.75rem",
    borderRadius: "0.375rem",
    cursor: "pointer",
    minHeight: "44px",
    marginBottom: "0.5rem",
    textAlign: "left",
    fontWeight: 600,
    fontSize: "0.8125rem",
  },
  sectionTitle: {
    fontWeight: 600,
  },
  card: {
    borderRadius: "0.5rem",
    marginBottom: "0.5rem",
    overflow: "hidden",
  },
  cardHeader: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    padding: "0.75rem",
    minHeight: "44px",
  },
  cardMeta: {
    display: "flex",
    alignItems: "flex-start",
    gap: "0.5rem",
  },
  verdictDot: {
    width: "8px",
    height: "8px",
    borderRadius: "50%",
    marginTop: "5px",
    flexShrink: 0,
  },
  companyName: {
    fontWeight: 600,
    fontSize: "0.875rem",
    display: "flex",
    alignItems: "center",
    gap: "0.4rem",
    flexWrap: "wrap",
  },
  badge: {
    fontSize: "0.625rem",
    padding: "0.1rem 0.35rem",
    borderRadius: "999px",
    fontWeight: 500,
    textTransform: "uppercase",
    letterSpacing: "0.04em",
  },
  cardBody: {
    padding: "0.75rem",
  },
  fieldLabel: {
    fontSize: "0.6875rem",
    fontWeight: 600,
    textTransform: "uppercase",
    letterSpacing: "0.04em",
  },
  linkRow: {
    display: "flex",
    flexWrap: "wrap",
    gap: "0.75rem",
    marginTop: "0.625rem",
  },
  link: {
    fontSize: "0.8125rem",
    textDecoration: "none",
    minHeight: "44px",
    display: "inline-flex",
    alignItems: "center",
  },
  draftBox: {
    borderRadius: "0.375rem",
    padding: "0.625rem",
    marginTop: "0.375rem",
    position: "relative",
  },
  draftText: {
    margin: 0,
    fontFamily: "inherit",
    fontSize: "0.8125rem",
    whiteSpace: "pre-wrap",
    wordBreak: "break-word",
    paddingRight: "4rem",
    lineHeight: 1.5,
  },
  copyBtn: {
    position: "absolute",
    top: "0.5rem",
    right: "0.5rem",
    padding: "0.3rem 0.6rem",
    borderRadius: "0.25rem",
    fontSize: "0.75rem",
    fontWeight: 600,
    cursor: "pointer",
    minHeight: "32px",
    minWidth: "60px",
  },
};

export default App;
