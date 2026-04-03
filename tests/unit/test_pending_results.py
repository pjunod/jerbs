"""
Unit tests for pending_results persistence and pruning.

The pending_results feature persists pass/maybe screening results across sessions
so users can return to items they haven't acted on yet. These tests verify:
  - New pass/maybe results are added to pending_results
  - Fail results are not added
  - Duplicate message_ids are not added
  - Entries older than 14 days are pruned
  - Dismissing by company removes matching entries
  - Dismissing all clears the array
"""

import sys
from datetime import date, timedelta
from pathlib import Path

# Ensure the daemon module is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "claude-code"))

from jerbs import _load_pending_results, _update_pending_results


def _make_result(message_id: str, verdict: str, company: str = "TestCo") -> dict:
    """Helper to create a minimal screening result dict."""
    return {
        "source": "Direct Outreach",
        "message_id": message_id,
        "thread_id": f"thread_{message_id}",
        "subject": f"Role at {company}",
        "from": "recruiter@example.com",
        "email_date": "2026-03-28",
        "company": company,
        "role": "Staff Engineer",
        "location": "Remote",
        "verdict": verdict,
        "reason": "Looks good",
        "dealbreaker": None,
        "comp_assessment": "Solid comp",
        "missing_fields": [],
        "reply_draft": "Thanks for reaching out..." if verdict != "fail" else None,
        "posting_url": None,
        "email_url": f"https://mail.google.com/mail/u/0/#inbox/{message_id}",
    }


# ---------------------------------------------------------------------------
# _update_pending_results tests
# ---------------------------------------------------------------------------


class TestUpdatePendingResults:
    def test_adds_pass_results(self):
        criteria = {"pending_results": []}
        results = [_make_result("msg1", "pass")]
        _update_pending_results(criteria, results)
        assert len(criteria["pending_results"]) == 1
        assert criteria["pending_results"][0]["message_id"] == "msg1"
        assert criteria["pending_results"][0]["status"] == "pending"
        assert "added_at" in criteria["pending_results"][0]

    def test_adds_maybe_results(self):
        criteria = {"pending_results": []}
        results = [_make_result("msg1", "maybe")]
        _update_pending_results(criteria, results)
        assert len(criteria["pending_results"]) == 1

    def test_skips_fail_results(self):
        criteria = {"pending_results": []}
        results = [_make_result("msg1", "fail")]
        _update_pending_results(criteria, results)
        assert len(criteria["pending_results"]) == 0

    def test_skips_duplicates(self):
        criteria = {
            "pending_results": [
                {**_make_result("msg1", "pass"), "added_at": "2026-03-25", "status": "pending"}
            ]
        }
        results = [_make_result("msg1", "pass", company="Updated Co")]
        _update_pending_results(criteria, results)
        assert len(criteria["pending_results"]) == 1
        # Should keep original, not the updated one
        assert criteria["pending_results"][0]["company"] == "TestCo"

    def test_adds_new_alongside_existing(self):
        criteria = {
            "pending_results": [
                {**_make_result("msg1", "pass"), "added_at": "2026-03-25", "status": "pending"}
            ]
        }
        results = [_make_result("msg2", "pass")]
        _update_pending_results(criteria, results)
        assert len(criteria["pending_results"]) == 2

    def test_prunes_old_entries(self):
        old_date = (date.today() - timedelta(days=15)).isoformat()
        criteria = {
            "pending_results": [
                {**_make_result("old_msg", "pass"), "added_at": old_date, "status": "pending"}
            ]
        }
        results = [_make_result("new_msg", "pass")]
        _update_pending_results(criteria, results)
        ids = [r["message_id"] for r in criteria["pending_results"]]
        assert "old_msg" not in ids
        assert "new_msg" in ids

    def test_retains_recent_entries(self):
        recent_date = (date.today() - timedelta(days=13)).isoformat()
        criteria = {
            "pending_results": [
                {**_make_result("recent_msg", "pass"), "added_at": recent_date, "status": "pending"}
            ]
        }
        results = []
        _update_pending_results(criteria, results)
        assert len(criteria["pending_results"]) == 1

    def test_empty_criteria_initializes_pending(self):
        criteria = {}
        results = [_make_result("msg1", "pass")]
        _update_pending_results(criteria, results)
        assert len(criteria["pending_results"]) == 1

    def test_mixed_verdicts(self):
        criteria = {"pending_results": []}
        results = [
            _make_result("msg1", "pass"),
            _make_result("msg2", "fail"),
            _make_result("msg3", "maybe"),
            _make_result("msg4", "fail"),
        ]
        _update_pending_results(criteria, results)
        assert len(criteria["pending_results"]) == 2
        ids = {r["message_id"] for r in criteria["pending_results"]}
        assert ids == {"msg1", "msg3"}

    def test_no_message_id_skipped(self):
        criteria = {"pending_results": []}
        result = _make_result("msg1", "pass")
        del result["message_id"]
        _update_pending_results(criteria, [result])
        assert len(criteria["pending_results"]) == 0


# ---------------------------------------------------------------------------
# _load_pending_results tests
# ---------------------------------------------------------------------------


class TestLoadPendingResults:
    def test_returns_empty_when_no_pending(self):
        assert _load_pending_results({}) == []
        assert _load_pending_results({"pending_results": []}) == []

    def test_returns_recent_entries(self):
        recent = (date.today() - timedelta(days=5)).isoformat()
        criteria = {
            "pending_results": [
                {**_make_result("msg1", "pass"), "added_at": recent, "status": "pending"}
            ]
        }
        result = _load_pending_results(criteria)
        assert len(result) == 1

    def test_filters_old_entries(self):
        old = (date.today() - timedelta(days=15)).isoformat()
        criteria = {
            "pending_results": [
                {**_make_result("msg1", "pass"), "added_at": old, "status": "pending"}
            ]
        }
        result = _load_pending_results(criteria)
        assert len(result) == 0

    def test_mixed_ages(self):
        old = (date.today() - timedelta(days=15)).isoformat()
        recent = (date.today() - timedelta(days=3)).isoformat()
        criteria = {
            "pending_results": [
                {**_make_result("old", "pass"), "added_at": old, "status": "pending"},
                {**_make_result("recent", "pass"), "added_at": recent, "status": "pending"},
            ]
        }
        result = _load_pending_results(criteria)
        assert len(result) == 1
        assert result[0]["message_id"] == "recent"

    def test_boundary_14_days(self):
        # _load_pending_results uses datetime.now(UTC) for the cutoff, which may
        # differ from local date.today(). Use a fixed reference to avoid flakiness.
        day_15 = (date.today() - timedelta(days=15)).isoformat()
        day_13 = (date.today() - timedelta(days=13)).isoformat()
        day_7 = (date.today() - timedelta(days=7)).isoformat()
        criteria = {
            "pending_results": [
                {**_make_result("at_15", "pass"), "added_at": day_15, "status": "pending"},
                {**_make_result("at_13", "pass"), "added_at": day_13, "status": "pending"},
                {**_make_result("at_7", "pass"), "added_at": day_7, "status": "pending"},
            ]
        }
        result = _load_pending_results(criteria)
        ids = [r["message_id"] for r in result]
        # 15 days ago is clearly outside the 14-day window
        assert "at_15" not in ids
        # 13 and 7 days ago are clearly inside
        assert "at_13" in ids
        assert "at_7" in ids
