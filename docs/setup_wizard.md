# Setup Wizard — First-time profile creation

Walk through these sections conversationally. Ask one section at a time. Offer sensible
defaults and examples. At the end, confirm the full profile before saving.

**Do not rush.** The quality of screening depends entirely on the depth of this profile.
Every field with a narrative answer (background_summary, remote_preference,
sliding_scale_notes, prestige_requirement, tone) needs the user's actual thinking — not
a one-word default. If a user gives a surface-level answer to a narrative field, follow up
once to draw out the nuance. Don't accept "open to anything" without asking what would
make them *prefer* one option over another.

**Ask conversationally.** Present each section's questions naturally, show examples and
suggested defaults inline, and let the user respond in their own words. For list fields
(dealbreakers, required info, etc.), show the suggested defaults as a numbered or bulleted
list and ask the user to pick the ones that apply, remove any that don't, and add their
own. Always include space for free-form additions — the best criteria come from the user's
own words, not from picking checkboxes.

---

## 1a — Identity

```
What's your name and current title?
Briefly describe your background (e.g. "10 years backend engineering, Apple and Meta").
What roles are you targeting? (can be multiple, e.g. "Staff Engineer, Principal SRE, Engineering Manager")
What seniority level? (e.g. Senior and above / mid-level and above / executive)
```

The background_summary should capture years of experience, domain expertise, and notable
employers — it powers the screening logic for role-fit evaluation.

---

## 1b — Target companies

```
What industries or company types are you interested in?
  Examples: FAANG-tier tech, fintech, crypto, hedge funds / HFT, healthcare tech,
  e-commerce, startups, enterprise SaaS, government, non-profit

Any company stages you prefer? (early-stage, Series B+, public, any)

Any prestige / pedigree requirement?
  Examples: "top-tier only — no unknown companies", "any legitimate company", "prefer well-known brands"

Are there specific companies you ALWAYS want to hear about (dream companies)?
Are there specific companies or recruiters you want to ALWAYS ignore (blacklist)?

Any entire industries to block?
  Examples: defense / weapons, tobacco, gambling, MLM, predatory lending
```

**Do not leave whitelist or blacklist empty without explicitly asking.** Most candidates
have at least one dream company and at least one company they'd never work for. If they
say "none", that's fine — but ask.

---

## 1c — Role requirements

```
Employment type: full-time only / open to contract / open to part-time?
Remote preference: remote only / hybrid OK / depends on location / open to on-site?
  If hybrid is OK, what's the max number of in-office days per week you'd consider?
Maximum travel you'd accept? (e.g. none, <10%, <25%, doesn't matter)
Do you need visa/work authorization sponsorship?
```

**Probe for conditions on remote_preference.** This field is almost never a simple
"remote only" or "open to anything" — most people have conditional preferences:
- "Remote preferred, but I'd go hybrid for the right company in [city]"
- "On-site is fine but only in major metros, not suburban office parks"
- "Hybrid OK up to 2 days, but 4+ days in-office needs to pay significantly more"

Ask: "Does your remote preference depend on other factors like location, company, or comp?"

---

## 1d — Compensation

```
What's your minimum acceptable base salary? (hard floor — reject anything explicitly listed below this)
  Currency? (USD, GBP, EUR, etc.)

What's your target total compensation? (including equity, bonus, etc.)

Is equity required, or is a strong cash bonus acceptable instead?

Any nuances to your comp expectations? This is your sliding scale — describe how your
expectations shift based on factors like:
  - Remote vs. in-office (and how many days)
  - How interesting / novel the work is
  - Company prestige or brand value
  - Startup equity upside potential
  - Seniority / scope of the role
  - Cost of living / location

Examples:
  "I'll accept lower base for fully remote roles or for genuinely exciting greenfield work"
  "In-office 4+ days needs to pay significantly more to be worth it"
  "Founding-team equity can offset a lower base if the company is promising"
```

**The sliding_scale_notes field is critical.** It's what separates a useful screener from
a blunt keyword filter. If the user doesn't volunteer nuance, prompt with: "Would you
accept different comp for different situations — like remote vs. in-office, or a dream
company vs. an unknown startup?" Most candidates have at least one trade-off worth
capturing here.

---

## 1e — Tech/stack (skip if not applicable)

```
Any tech/stack that's a hard requirement? (e.g. Linux-only environments, specific languages)
Any tech/stack that's an immediate dealbreaker? (e.g. Windows servers, legacy COBOL)
Any preferred stack or tech that would make a role more attractive?
```

Skip this section entirely for non-technical roles.

---

## 1f — Hard dealbreakers

Start with common suggestions and let them add/remove:

Suggested defaults (user picks which apply):
- Contract / part-time / freelance (when targeting full-time)
- Wrong seniority level (junior/intern/mid-level if targeting senior)
- Salary explicitly listed below base floor
- Generic/mass emails with no personalization (no name, boilerplate, "Hi there")
- Completely unknown company with no pedigree, funding signal, or recognizable name
- Company on personal blacklist
- Industry on personal blocklist
- Requires relocation to unwanted location
- Unpaid trial or take-home assignment
- Requires security clearance (if not applicable)
- Role is in entirely wrong field

Let user add any custom dealbreakers. Ask: "Any other instant deal-killers I should know
about?" Common custom ones include: third-party recruiters, specific interview practices,
mandatory return-to-office policies, non-compete requirements.

---

## 1g — Required info (what to always ask about if missing)

Start with common suggestions:

Suggested defaults:
- Salary / compensation range (base + total comp)
- Equity details (type, vesting schedule)
- Remote / hybrid / in-office policy
- Number of in-office days if hybrid
- Interview process overview
- Company name (if obscured)

Additional options to suggest:
- Nature of work (greenfield vs. maintenance)
- Tech stack details
- Team size
- Reporting structure
- Benefits (health, 401k, etc.)
- Bonus structure
- Start date flexibility

---

## 1h — Interview process preferences (optional)

```
Maximum number of interview rounds you'll tolerate? (or leave blank for no limit)
Unpaid take-home assignments: dealbreaker yes/no?
Any other interview process dealbreakers?
```

If the user has opinions about take-home assignments, probe for specifics — many people
accept them conditionally (e.g. "fine if under 2 hours", "only if they pay for it",
"only with guaranteed feedback").

---

## 1i — Reply settings

```
What tone should draft replies use? (professional / direct / warm / brief)
What name/signature should replies use?
  Example: "Best, Sarah Chen" or "Thanks, Marcus | Staff Engineer"
```

Ask if the tone or signature should evolve as rapport builds (e.g. "Paul Junod" initially,
"Paul" after a few exchanges).

---

## 1j — Search settings

```
Any extra keywords to include in searches beyond the defaults?
Any specific senders or domains to always exclude?
```

Do NOT ask about lookback window or max results — set automatically from run history.

---

## 1k — LinkedIn DM screening (optional)

If the LinkedIn MCP is connected, ask if the user wants to enable LinkedIn DM screening.
If yes, cookies are configured via the setup wizard in the daemon or via MCP connection
in Claude Code/Claude.ai.

If the LinkedIn MCP is not connected, skip this section entirely — don't prompt the user
to set it up.

---

## Confirm and save

Show the **full** criteria summary — every field, not just the highlights. The user needs
to see everything they entered to catch mistakes or gaps. Ask: "Does this look right?
Anything to adjust before I save it?"

Then write to the criteria JSON file.
