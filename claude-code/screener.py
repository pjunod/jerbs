"""
screener.py — email screening logic using the Anthropic API

Builds the screening prompt from user criteria, runs two Gmail passes,
screens each email/listing, and returns structured results.
"""

import os

try:
    import anthropic
except ImportError as e:
    raise ImportError("Anthropic SDK not installed. Run: pip install anthropic") from e

_HAIKU_MODEL = "claude-haiku-4-5-20251001"
_THINKING_BUDGET = 5000  # tokens; only used when escalating to Sonnet

_SCREENING_TOOL = {
    "name": "record_screening_result",
    "description": "Record the structured screening verdict for a job email or listing.",
    "input_schema": {
        "type": "object",
        "properties": {
            "company": {
                "type": "string",
                "description": "Company name, or empty string if unknown",
            },
            "role": {"type": "string", "description": "Job title"},
            "location": {"type": "string", "description": "City, region, or 'remote'"},
            "verdict": {
                "type": "string",
                "enum": ["pass", "fail", "maybe"],
                "description": "pass = interested, fail = dealbreaker hit, maybe = needs more info",
            },
            "reason": {"type": "string", "description": "One sentence explaining the verdict"},
            "dealbreaker_triggered": {
                "type": ["string", "null"],
                "description": "The specific dealbreaker that caused a fail, or null",
            },
            "comp_assessment": {
                "type": ["string", "null"],
                "description": "Honest 1-2 sentence sliding-scale comp take, or null",
            },
            "missing_fields": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Required info fields absent from the email",
            },
            "reply_draft": {
                "type": ["string", "null"],
                "description": "Draft reply for pass/maybe requesting missing info, or null for fail",
            },
        },
        "required": ["verdict", "reason", "missing_fields"],
    },
}


class Screener:
    def __init__(self, api_key: str | None = None):
        self.client = anthropic.Anthropic(api_key=api_key or os.environ.get("ANTHROPIC_API_KEY"))
        self.model = "claude-sonnet-4-20250514"
        self._prompt_cache: str | None = None
        self._criteria_hash: str | None = None

    def _get_prompt(self, criteria: dict) -> str:
        """Return cached system prompt, rebuilding only when criteria changes."""
        import hashlib
        import json

        h = hashlib.md5(json.dumps(criteria, sort_keys=True).encode()).hexdigest()[:8]
        if h != self._criteria_hash:
            self._prompt_cache = self._build_prompt(criteria)
            self._criteria_hash = h
        return self._prompt_cache  # type: ignore[return-value]

    def _build_pass1_query(self, criteria: dict, lookback_days: int) -> str:
        """Build Gmail query for job alert digest emails (LinkedIn, Indeed, etc.)."""
        base_keywords = ["opportunity", "role", "position", "opening", "hiring"]
        extra = criteria.get("search_settings", {}).get("extra_keywords", [])
        kw_clause = " OR ".join(base_keywords + extra)
        sources = "linkedin.com OR jobalerts.indeed.com OR indeedemail.com"
        return f"(subject:({kw_clause}) OR from:({sources})) newer_than:{lookback_days}d"

    def _build_pass2_query(self, criteria: dict, lookback_days: int) -> str:
        """Build Gmail query for direct recruiter outreach emails."""
        exclusions = [
            "-from:linkedin.com",
            "-from:jobalerts.indeed.com",
            "-from:indeedemail.com",
            "-from:noreply",
            "-from:no-reply",
        ]
        for ex in criteria.get("search_settings", {}).get("extra_exclusions", []):
            exclusions.append(f"-from:{ex}")
        excl_str = " ".join(exclusions)

        subject_kw = [
            "opportunity",
            "role",
            "position",
            "opening",
            "hiring",
            '"reaching out"',
            '"your background"',
            '"your profile"',
            '"came across"',
        ]
        body_phrases = [
            '"your experience"',
            '"came across your profile"',
            '"reaching out"',
            '"great fit"',
            '"perfect fit"',
        ]
        subj_str = " OR ".join(subject_kw)
        body_str = " OR ".join(body_phrases)
        return f"newer_than:{lookback_days}d {excl_str} (subject:({subj_str}) OR ({body_str}))"

    def run(
        self,
        criteria: dict,
        gmail,
        lookback_days: int = 1,
        max_per_pass: int | None = 100,
        send_mode: bool = False,
    ) -> tuple[list[dict], bool]:
        """
        Run both Gmail passes and screen all results.
        Returns (results, had_drafts).
        """
        raw_ids = criteria.get("screened_message_ids", [])
        screened_ids = {e["id"] if isinstance(e, dict) else e for e in raw_ids}
        results = []
        had_drafts = False
        prompt = self._get_prompt(criteria)

        for pass_num, query, source_label in [
            (1, self._build_pass1_query(criteria, lookback_days), "LinkedIn Alert"),
            (2, self._build_pass2_query(criteria, lookback_days), "Direct Outreach"),
        ]:
            messages = gmail.search(query, max_results=max_per_pass)
            new_msgs = [m for m in messages if m["id"] not in screened_ids]

            if max_per_pass and len(messages) >= max_per_pass:
                print(
                    f"\nPass {pass_num} hit the {max_per_pass}-result limit — "
                    f"there may be more emails. Run with a larger --max to fetch more."
                )

            for msg_meta in new_msgs:
                msg = gmail.get_message(msg_meta["id"])
                if not msg:
                    continue

                result = self._screen_one(msg, prompt, source_label, pass_num)
                if result:
                    results.append(result)
                    screened_ids.add(msg_meta["id"])
                    if result.get("reply_draft"):
                        had_drafts = True

        return results, had_drafts

    def _call_api(
        self,
        user_content: str,
        system_prompt: str,
        model: str,
        extended_thinking: bool = False,
    ) -> dict:
        """Call the Anthropic API and return the tool_use input dict."""
        kwargs: dict = {
            "model": model,
            "system": [
                {
                    "type": "text",
                    "text": system_prompt,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            "tools": [_SCREENING_TOOL],
            "tool_choice": {"type": "tool", "name": "record_screening_result"},
            "messages": [{"role": "user", "content": user_content}],
        }
        if extended_thinking:
            kwargs["thinking"] = {"type": "enabled", "budget_tokens": _THINKING_BUDGET}
            kwargs["max_tokens"] = _THINKING_BUDGET + 1024
        else:
            kwargs["max_tokens"] = 1024

        response = self.client.messages.create(**kwargs)
        tool_block = next(b for b in response.content if b.type == "tool_use")
        return tool_block.input

    def _screen_one(self, msg: dict, system_prompt: str, source: str, pass_num: int) -> dict | None:
        """
        Screen a single email using two-tier model selection.

        Haiku handles the fast-path: clear fails are returned immediately at low cost.
        Haiku pass/maybe results escalate to Sonnet with extended thinking for reliable
        judgment on ambiguous or high-value cases.
        """
        user_content = (
            f"Subject: {msg.get('subject', '')}\n"
            f"From: {msg.get('from', '')}\n"
            f"Date: {msg.get('date', '')}\n\n"
            f"{msg.get('body', msg.get('snippet', ''))}"
        )

        try:
            # Stage 1: Haiku fast path — cheap rejection of clear fails
            haiku = self._call_api(user_content, system_prompt, _HAIKU_MODEL)
            if haiku.get("verdict") == "fail":
                parsed = haiku
            else:
                # Stage 2: Sonnet with extended thinking for genuine judgment calls
                parsed = self._call_api(
                    user_content, system_prompt, self.model, extended_thinking=True
                )
        except Exception as e:
            return {
                "source": source,
                "message_id": msg["id"],
                "thread_id": msg.get("threadId", ""),
                "subject": msg.get("subject", ""),
                "from": msg.get("from", ""),
                "email_date": msg.get("date", ""),
                "company": "?",
                "role": msg.get("subject", "?"),
                "location": "",
                "verdict": "maybe",
                "reason": f"Screening error: {e}",
                "dealbreaker": None,
                "comp_assessment": None,
                "missing_fields": [],
                "reply_draft": None,
            }

        return {
            "source": source,
            "message_id": msg["id"],
            "thread_id": msg.get("threadId", ""),
            "subject": msg.get("subject", ""),
            "from": msg.get("from", ""),
            "email_date": msg.get("date", ""),
            "company": parsed.get("company", ""),
            "role": parsed.get("role", msg.get("subject", "")),
            "location": parsed.get("location", ""),
            "verdict": parsed.get("verdict", "maybe"),
            "reason": parsed.get("reason", ""),
            "dealbreaker": parsed.get("dealbreaker_triggered"),
            "comp_assessment": parsed.get("comp_assessment"),
            "missing_fields": parsed.get("missing_fields", []),
            "reply_draft": parsed.get("reply_draft"),
        }

    def _build_prompt(self, criteria: dict) -> str:
        comp = criteria.get("compensation", {})
        stack = criteria.get("tech_stack", {})
        reply = criteria.get("reply_settings", {})
        ident = criteria.get("identity", {})
        tc = criteria.get("target_companies", {})
        role_r = criteria.get("role_requirements", {})
        floor = comp.get("base_salary_floor", 225000)
        tc_tgt = comp.get("total_comp_target", 350000)
        sliding = comp.get("sliding_scale_notes", "")
        blk = tc.get("blacklist", [])
        blk_str = ", ".join(blk) if blk else "none"
        db_list = "\n".join(f"- {d}" for d in criteria.get("hard_dealbreakers", []))
        req_list = "\n".join(f"- {r}" for r in criteria.get("required_info", []))
        sig = reply.get("signature", "")
        tone = reply.get("tone", "professional and direct")

        return f"""You are screening job recruiter emails for a candidate. Apply genuine judgment.

CANDIDATE: {ident.get("background_summary", "")}
ROLES TARGETING: {", ".join(ident.get("target_roles", []))}
SENIORITY: {ident.get("seniority_level", "Senior and above")}

TARGET COMPANIES:
Industries: {", ".join(tc.get("industries", []))}
Prestige: {tc.get("prestige_requirement", "Upper-tier only")}
Blacklist: {blk_str}

ROLE REQUIREMENTS:
Employment type: {", ".join(role_r.get("employment_type", ["full-time"]))}
Remote: {role_r.get("remote_preference", "must be disclosed")}

COMPENSATION:
Base floor: ${floor:,}
SALARY RANGE RULE: If the floor (${floor:,}) falls within a stated range, the role PASSES.
Only fail on salary if the TOP of the stated range is below ${floor:,}.
TC target: ${tc_tgt:,}+ (must include equity or substantial cash bonus)
Comp assessment sliding scale (informational only — never affects verdict):
{sliding}

STACK:
Required: {", ".join(stack.get("required", []))}
Dealbreaker: {", ".join(stack.get("dealbreaker", []))}

HARD DEALBREAKERS (verdict = fail if any are true):
{db_list}

REQUIRED INFO (flag missing, request in reply draft):
{req_list}

Pass 2 only (direct outreach): Generic/mass email (no name, boilerplate, no reference
to specific background) = hard fail. Pass 1 (digest alerts) = exempt from this rule.

REPLY SETTINGS:
Tone: {tone}
Sign off: {sig}
Draft replies for pass/maybe only. Direct opener — no sycophantic greeting. Request all
missing info in one message."""
