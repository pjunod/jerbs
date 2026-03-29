"""
screener.py — email screening logic using the Anthropic API

Builds the screening prompt from user criteria, runs two Gmail passes,
screens each email/listing, and returns structured results.
"""

import os
import json
from datetime import datetime
from typing import Optional

try:
    import anthropic
except ImportError:
    raise ImportError("Anthropic SDK not installed. Run: pip install anthropic")


class Screener:
    def __init__(self, api_key: Optional[str] = None):
        self.client = anthropic.Anthropic(
            api_key=api_key or os.environ.get("ANTHROPIC_API_KEY")
        )
        self.model = "claude-sonnet-4-20250514"

    def run(self, criteria: dict, gmail, lookback_days: int = 1,
            max_per_pass: Optional[int] = 100, send_mode: bool = False
            ) -> tuple[list[dict], bool]:
        """
        Run both Gmail passes and screen all results.
        Returns (results, had_drafts).
        """
        raw_ids = criteria.get("screened_message_ids", [])
        screened_ids = {
            e["id"] if isinstance(e, dict) else e for e in raw_ids
        }
        results      = []
        had_drafts   = False
        prompt       = self._build_prompt(criteria)

        pass1_query = (
            f"(subject:(opportunity OR role OR position OR opening OR hiring) OR "
            f"from:(linkedin.com OR jobalerts.indeed.com OR indeedemail.com)) "
            f"newer_than:{lookback_days}d"
        )
        pass2_query = (
            f"newer_than:{lookback_days}d -from:linkedin.com -from:jobalerts.indeed.com "
            f"-from:indeedemail.com -from:noreply -from:no-reply "
            f"(subject:(opportunity OR role OR position OR opening OR hiring OR "
            f"\"reaching out\" OR \"your background\" OR \"your profile\" OR \"came across\") OR "
            f"(\"your experience\" OR \"came across your profile\" OR \"reaching out\" OR "
            f"\"great fit\" OR \"perfect fit\"))"
        )

        extra_kw = criteria.get("search_settings", {}).get("extra_keywords", [])
        if extra_kw:
            pass1_query = pass1_query.replace("newer_than:", " OR ".join(extra_kw) + " newer_than:")

        extra_ex = criteria.get("search_settings", {}).get("extra_exclusions", [])
        for ex in extra_ex:
            pass2_query += f" -from:{ex}"

        for pass_num, query, source_label in [
            (1, pass1_query, "LinkedIn Alert"),
            (2, pass2_query, "Direct Outreach"),
        ]:
            messages = gmail.search(query, max_results=max_per_pass)
            new_msgs = [m for m in messages if m["id"] not in screened_ids]

            if max_per_pass and len(messages) >= max_per_pass:
                print(f"\nPass {pass_num} hit the {max_per_pass}-result limit — "
                      f"there may be more emails. Run with a larger --max to fetch more.")

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

    def _screen_one(self, msg: dict, system_prompt: str,
                    source: str, pass_num: int) -> Optional[dict]:
        """Screen a single email and return a result dict."""
        user_content = (
            f"Subject: {msg.get('subject', '')}\n"
            f"From: {msg.get('from', '')}\n"
            f"Date: {msg.get('date', '')}\n\n"
            f"{msg.get('body', msg.get('snippet', ''))}"
        )

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                system=system_prompt,
                messages=[{"role": "user", "content": user_content}]
            )
            text = response.content[0].text.strip()
            text = text.replace("```json", "").replace("```", "").strip()
            parsed = json.loads(text)
        except (json.JSONDecodeError, Exception) as e:
            return {
                "source":    source,
                "message_id": msg["id"],
                "thread_id":  msg.get("threadId", ""),
                "subject":    msg.get("subject", ""),
                "from":       msg.get("from", ""),
                "email_date": msg.get("date", ""),
                "company":    "?",
                "role":       msg.get("subject", "?"),
                "location":   "",
                "verdict":    "maybe",
                "reason":     f"Screening parse error: {e}",
                "dealbreaker": None,
                "comp_assessment": None,
                "missing_fields": [],
                "reply_draft": None,
            }

        return {
            "source":          source,
            "message_id":      msg["id"],
            "thread_id":       msg.get("threadId", ""),
            "subject":         msg.get("subject", ""),
            "from":            msg.get("from", ""),
            "email_date":      msg.get("date", ""),
            "company":         parsed.get("company", ""),
            "role":            parsed.get("role", msg.get("subject", "")),
            "location":        parsed.get("location", ""),
            "verdict":         parsed.get("verdict", "maybe"),
            "reason":          parsed.get("reason", ""),
            "dealbreaker":     parsed.get("dealbreaker_triggered"),
            "comp_assessment": parsed.get("comp_assessment"),
            "missing_fields":  parsed.get("missing_fields", []),
            "reply_draft":     parsed.get("reply_draft"),
        }

    def _build_prompt(self, criteria: dict) -> str:
        comp    = criteria.get("compensation", {})
        stack   = criteria.get("tech_stack", {})
        reply   = criteria.get("reply_settings", {})
        ident   = criteria.get("identity", {})
        tc      = criteria.get("target_companies", {})
        role_r  = criteria.get("role_requirements", {})
        floor   = comp.get("base_salary_floor", 225000)
        tc_tgt  = comp.get("total_comp_target", 350000)
        sliding = comp.get("sliding_scale_notes", "")
        blk     = tc.get("blacklist", [])
        blk_str = ", ".join(blk) if blk else "none"
        db_list = "\n".join(f"- {d}" for d in criteria.get("hard_dealbreakers", []))
        req_list= "\n".join(f"- {r}" for r in criteria.get("required_info", []))
        sig     = reply.get("signature", "")
        tone    = reply.get("tone", "professional and direct")

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
missing info in one message.

Respond ONLY with valid JSON:
{{
  "company": "company name or empty string",
  "role": "job title",
  "location": "city or remote",
  "verdict": "pass" | "fail" | "maybe",
  "reason": "one sentence",
  "dealbreaker_triggered": "specific dealbreaker or null",
  "comp_assessment": "honest 1-2 sentence sliding-scale take or null",
  "missing_fields": ["list of absent required fields"],
  "reply_draft": "direct reply requesting missing info, signed '{sig}', or null if fail"
}}"""
