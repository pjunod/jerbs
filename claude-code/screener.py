"""
screener.py — email screening logic using the Anthropic API

Builds the screening prompt from user criteria, runs two Gmail passes,
screens each email/listing, and returns structured results.
"""

import os
import time

try:
    import anthropic
except ImportError as e:
    raise ImportError("Anthropic SDK not installed. Run: pip install anthropic") from e

_HAIKU_MODEL = "claude-haiku-4-5-20251001"
_THINKING_BUDGET = 5000  # tokens; only used when escalating to Sonnet
_BATCH_THRESHOLD = 3  # use Batch API when new email count exceeds this

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
        use_batch: bool = False,
        on_result=None,
        linkedin=None,
    ) -> tuple[list[dict], bool]:
        """
        Run Gmail passes and an optional LinkedIn DM pass, screen all results.

        Args:
            use_batch: Use Anthropic Batch API when >3 emails (50% cost reduction).
                       Ideal for daemon runs; keep False for interactive sessions.
            on_result: Optional callback invoked immediately after each message is
                       screened. Called with the result dict. Only fires in
                       real-time (non-batch) mode.
            linkedin: Optional LinkedInClient instance. When provided, adds a 3rd
                      pass that screens recent LinkedIn DMs.
        Returns (results, had_drafts).
        """
        raw_ids = criteria.get("screened_message_ids", [])
        screened_ids = {e["id"] if isinstance(e, dict) else e for e in raw_ids}
        results = []
        had_drafts = False
        prompt = self._get_prompt(criteria)

        # Build pass list: Gmail passes + optional LinkedIn pass
        passes = [
            (1, self._build_pass1_query(criteria, lookback_days), "LinkedIn Alert", gmail),
            (2, self._build_pass2_query(criteria, lookback_days), "Direct Outreach", gmail),
        ]
        if linkedin:
            passes.append((3, "", "LinkedIn DM", linkedin))

        # Collect all new full messages up front
        all_messages: list[dict] = []
        for pass_num, query, source_label, client in passes:
            messages = client.search(query, max_results=max_per_pass)
            new_msgs = [m for m in messages if m["id"] not in screened_ids]

            if max_per_pass and len(messages) >= max_per_pass:
                print(
                    f"\nPass {pass_num} hit the {max_per_pass}-result limit"
                    f" — there may be more. Run with a larger --max."
                )

            for meta in new_msgs:
                msg = client.get_message(meta["id"])
                if msg:
                    msg["_source"] = source_label
                    msg["_pass_num"] = pass_num
                    all_messages.append(msg)

        if use_batch and len(all_messages) > _BATCH_THRESHOLD:
            # Batch API path — submits all emails at once for 50% cost reduction.
            # Results arrive after polling; on_result is not called (no streaming in batch mode).
            for result in self._screen_batch(all_messages, prompt):
                if result:
                    results.append(result)
                    screened_ids.add(result["message_id"])
                    if result.get("reply_draft"):
                        had_drafts = True
        else:
            # Real-time API path — screen each email immediately.
            # on_result fires after each email so callers can stream output progressively.
            for msg in all_messages:
                result = self._screen_one(msg, prompt, msg["_source"])
                if result:
                    results.append(result)
                    screened_ids.add(msg["id"])
                    if result.get("reply_draft"):
                        had_drafts = True
                    if on_result:
                        on_result(result)

        return results, had_drafts

    # ── Shared helpers ────────────────────────────────────────────────────────

    def _format_email_content(self, msg: dict) -> str:
        return (
            f"Subject: {msg.get('subject', '')}\n"
            f"From: {msg.get('from', '')}\n"
            f"Date: {msg.get('date', '')}\n\n"
            f"{msg.get('body', msg.get('snippet', ''))}"
        )

    def _build_result_dict(self, msg: dict, parsed: dict) -> dict:
        return {
            "source": msg.get("_source", ""),
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

    def _build_api_params(
        self,
        user_content: str,
        system_prompt: str,
        model: str,
        extended_thinking: bool = False,
    ) -> dict:
        """Build kwargs dict shared between real-time and batch API calls."""
        params: dict = {
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
            params["thinking"] = {"type": "enabled", "budget_tokens": _THINKING_BUDGET}
            params["max_tokens"] = _THINKING_BUDGET + 1024
        else:
            params["max_tokens"] = 1024
        return params

    # ── Real-time API ─────────────────────────────────────────────────────────

    def _call_api(
        self,
        user_content: str,
        system_prompt: str,
        model: str,
        extended_thinking: bool = False,
    ) -> dict:
        """Call the Anthropic API and return the tool_use input dict."""
        params = self._build_api_params(user_content, system_prompt, model, extended_thinking)
        response = self.client.messages.create(**params)
        tool_block = next(b for b in response.content if b.type == "tool_use")
        return tool_block.input

    def _screen_one(self, msg: dict, system_prompt: str, source: str) -> dict | None:
        """
        Screen a single email using two-tier model selection.

        Haiku handles the fast-path: clear fails are returned immediately at low cost.
        Haiku pass/maybe results escalate to Sonnet with extended thinking for reliable
        judgment on ambiguous or high-value cases.
        """
        user_content = self._format_email_content(msg)

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
                **self._build_result_dict(msg, {}),
                "source": source,
                "verdict": "maybe",
                "reason": f"Screening error: {e}",
            }

        result = self._build_result_dict(msg, parsed)
        result["source"] = source
        return result

    # ── Batch API ─────────────────────────────────────────────────────────────

    def _screen_batch(self, msgs: list[dict], system_prompt: str) -> list[dict]:
        """
        Screen emails using the Anthropic Batch API.

        Two sequential batches: Haiku for all emails (cheap fast-path), then Sonnet
        with extended thinking only for pass/maybe verdicts. 50% cost vs real-time.
        Blocks until both batches complete (suitable for daemon/background use).
        """
        # Stage 1: Haiku batch — cheap rejection of clear fails
        haiku_requests = [
            {
                "custom_id": f"h{i}",
                "params": self._build_api_params(
                    self._format_email_content(msg), system_prompt, _HAIKU_MODEL
                ),
            }
            for i, msg in enumerate(msgs)
        ]
        haiku_results = self._wait_for_batch(
            self.client.messages.batches.create(requests=haiku_requests).id
        )

        # Stage 2: Sonnet batch — extended thinking for pass/maybe only
        escalate_indices = [
            i
            for i, msg in enumerate(msgs)
            if (haiku_results.get(f"h{i}") or {}).get("verdict") != "fail"
        ]
        sonnet_results: dict[int, dict] = {}
        if escalate_indices:
            sonnet_requests = [
                {
                    "custom_id": f"s{i}",
                    "params": self._build_api_params(
                        self._format_email_content(msgs[i]),
                        system_prompt,
                        self.model,
                        extended_thinking=True,
                    ),
                }
                for i in escalate_indices
            ]
            raw = self._wait_for_batch(
                self.client.messages.batches.create(requests=sonnet_requests).id
            )
            sonnet_results = {int(k[1:]): v for k, v in raw.items() if v is not None}

        # Assemble final results
        results = []
        for i, msg in enumerate(msgs):
            haiku = haiku_results.get(f"h{i}") or {}
            if haiku.get("verdict") == "fail":
                parsed = haiku
            else:
                parsed = sonnet_results.get(i, haiku)
            results.append(self._build_result_dict(msg, parsed))
        return results

    def _wait_for_batch(self, batch_id: str, poll_interval: int = 5) -> dict[str, dict | None]:
        """Poll until a batch completes. Returns {custom_id: tool_input or None}."""
        while True:
            batch = self.client.messages.batches.retrieve(batch_id)
            if batch.processing_status == "ended":
                break
            time.sleep(poll_interval)

        results: dict[str, dict | None] = {}
        for item in self.client.messages.batches.results(batch_id):
            if item.result.type == "succeeded":
                try:
                    tool_block = next(
                        b for b in item.result.message.content if b.type == "tool_use"
                    )
                    results[item.custom_id] = tool_block.input
                except StopIteration:
                    results[item.custom_id] = None
            else:
                results[item.custom_id] = None
        return results

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

Pass 3 (LinkedIn DMs): Direct messages from recruiters on LinkedIn. The "subject"
field is synthesized from the sender name and first line of the message (LinkedIn
DMs have no real subject). Apply the same criteria as Pass 2 — the generic mass
message dealbreaker applies: a generic InMail template with no personalization is
a hard fail.

REPLY SETTINGS:
Tone: {tone}
Sign off: {sig}
Draft replies for pass/maybe only. Direct opener — no sycophantic greeting. Request all
missing info in one message."""
