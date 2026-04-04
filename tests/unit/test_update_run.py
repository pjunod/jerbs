"""
Unit tests for scripts/update_run.py — lock guard and criteria.json updater.
"""

import json
import sys
from datetime import date
from pathlib import Path

import pytest

# Make the scripts/ directory importable
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))
import update_run  # noqa: E402

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def patch_paths(tmp_path, monkeypatch):
    """Redirect CRITERIA_PATH and LOCK_PATH to tmp_path for every test."""
    criteria = tmp_path / "criteria.json"
    lock = tmp_path / ".running"
    monkeypatch.setattr(update_run, "CRITERIA_PATH", str(criteria))
    monkeypatch.setattr(update_run, "LOCK_PATH", str(lock))
    return criteria, lock


def _write_criteria(tmp_path, data):
    (tmp_path / "criteria.json").write_text(json.dumps(data), encoding="utf-8")


def _read_criteria(tmp_path):
    return json.loads((tmp_path / "criteria.json").read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Lock guard
# ---------------------------------------------------------------------------


class TestLockGuard:
    def test_check_lock_clear(self, tmp_path, capsys):
        update_run.check_lock()
        assert capsys.readouterr().out.strip() == "CLEAR"

    def test_check_lock_locked(self, tmp_path, capsys):
        (tmp_path / ".running").write_text("x", encoding="utf-8")
        update_run.check_lock()
        assert capsys.readouterr().out.strip() == "LOCKED"

    def test_set_lock_creates_file(self, tmp_path):
        update_run.set_lock()
        assert (tmp_path / ".running").exists()

    def test_set_lock_writes_timestamp(self, tmp_path):
        update_run.set_lock()
        content = (tmp_path / ".running").read_text(encoding="utf-8")
        assert "T" in content  # ISO 8601 contains a T

    def test_clear_lock_removes_file(self, tmp_path):
        (tmp_path / ".running").write_text("x", encoding="utf-8")
        update_run.clear_lock()
        assert not (tmp_path / ".running").exists()

    def test_clear_lock_noop_when_not_locked(self, tmp_path):
        update_run.clear_lock()  # should not raise
        assert not (tmp_path / ".running").exists()


# ---------------------------------------------------------------------------
# add_ids
# ---------------------------------------------------------------------------


class TestAddIds:
    def test_adds_new_ids(self, tmp_path):
        _write_criteria(tmp_path, {"screened_message_ids": []})
        update_run.add_ids(["abc", "def"])
        data = _read_criteria(tmp_path)
        ids = [e["id"] for e in data["screened_message_ids"]]
        assert "abc" in ids
        assert "def" in ids

    def test_skips_duplicate_ids(self, tmp_path):
        existing = [{"id": "abc", "screened_at": "2026-01-01"}]
        _write_criteria(tmp_path, {"screened_message_ids": existing})
        update_run.add_ids(["abc", "new"])
        data = _read_criteria(tmp_path)
        ids = [e["id"] for e in data["screened_message_ids"]]
        assert ids.count("abc") == 1
        assert "new" in ids

    def test_sets_last_run_date(self, tmp_path):
        _write_criteria(tmp_path, {"screened_message_ids": []})
        update_run.add_ids(["x"])
        data = _read_criteria(tmp_path)
        assert data["last_run_date"] == date.today().isoformat()

    def test_migrates_legacy_string_format(self, tmp_path):
        _write_criteria(tmp_path, {"screened_message_ids": ["old1", "old2"]})
        update_run.add_ids(["new1"])
        data = _read_criteria(tmp_path)
        entries = data["screened_message_ids"]
        assert all(isinstance(e, dict) for e in entries)
        legacy = next(e for e in entries if e["id"] == "old1")
        assert legacy["screened_at"] == "2000-01-01"

    def test_new_ids_use_object_format(self, tmp_path):
        _write_criteria(tmp_path, {"screened_message_ids": []})
        update_run.add_ids(["fresh"])
        data = _read_criteria(tmp_path)
        entry = data["screened_message_ids"][0]
        assert isinstance(entry, dict)
        assert entry["id"] == "fresh"
        assert entry["screened_at"] == date.today().isoformat()


# ---------------------------------------------------------------------------
# enable_scheduler / disable_scheduler
# ---------------------------------------------------------------------------


class TestSchedulerEnableDisable:
    def test_enable_scheduler(self, tmp_path):
        _write_criteria(tmp_path, {"scheduler": {"enabled": False, "cron_jobs": []}})
        update_run.enable_scheduler(["biz123", "off456"])
        data = _read_criteria(tmp_path)
        assert data["scheduler"]["enabled"] is True
        assert data["scheduler"]["cron_jobs"] == ["biz123", "off456"]

    def test_disable_scheduler(self, tmp_path):
        _write_criteria(tmp_path, {"scheduler": {"enabled": True, "cron_jobs": ["x"]}})
        update_run.disable_scheduler()
        data = _read_criteria(tmp_path)
        assert data["scheduler"]["enabled"] is False
        assert data["scheduler"]["cron_jobs"] == []

    def test_enable_creates_scheduler_key_if_absent(self, tmp_path):
        _write_criteria(tmp_path, {})
        update_run.enable_scheduler(["j1"])
        data = _read_criteria(tmp_path)
        assert data["scheduler"]["enabled"] is True

    def test_disable_creates_scheduler_key_if_absent(self, tmp_path):
        _write_criteria(tmp_path, {})
        update_run.disable_scheduler()
        data = _read_criteria(tmp_path)
        assert data["scheduler"]["enabled"] is False
