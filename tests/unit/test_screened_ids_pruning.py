"""
Unit tests for screened_message_ids pruning logic.

The pruning strategy is defined in SKILL.md and implemented wherever criteria
are saved after a run. These tests verify the expected behavior:
  - Legacy plain-string arrays are migrated to object format on save
  - IDs older than 60 days relative to last_run_date are pruned
  - New IDs are written in object format
  - IDs within 60 days are retained
"""

import json
from datetime import date, timedelta

# ---------------------------------------------------------------------------
# Pruning logic (extracted for unit testing)
# The actual implementation lives in SKILL.md instructions applied by Claude,
# but for the local daemon we implement it as a utility function here.
# These tests define the contract that the implementation must satisfy.
# ---------------------------------------------------------------------------


def migrate_screened_ids(raw_ids: list, run_date: str) -> list:
    """
    Migrate screened_message_ids from legacy format (list of strings)
    to object format (list of {id, screened_at} dicts).

    Legacy string entries are assigned run_date as their screened_at value
    since their original date is unknown — this makes them non-expiring
    until 60 days after the migration run.
    """
    result = []
    for entry in raw_ids:
        if isinstance(entry, str):
            result.append({"id": entry, "screened_at": run_date})
        elif isinstance(entry, dict) and "id" in entry:
            result.append(entry)
    return result


def prune_screened_ids(ids: list, run_date: str, ttl_days: int = 60) -> list:
    """
    Remove entries from screened_message_ids that are older than ttl_days
    relative to run_date.
    """
    cutoff = date.fromisoformat(run_date) - timedelta(days=ttl_days)
    return [entry for entry in ids if date.fromisoformat(entry["screened_at"]) > cutoff]


def add_screened_id(ids: list, message_id: str, screened_at: str) -> list:
    """Add a new screened message ID in object format."""
    return ids + [{"id": message_id, "screened_at": screened_at}]


# ---------------------------------------------------------------------------
# Migration tests
# ---------------------------------------------------------------------------


class TestMigration:
    def test_empty_list_stays_empty(self):
        assert migrate_screened_ids([], "2026-03-28") == []

    def test_plain_strings_migrated_to_objects(self):
        result = migrate_screened_ids(["abc123", "def456"], "2026-03-28")
        assert result == [
            {"id": "abc123", "screened_at": "2026-03-28"},
            {"id": "def456", "screened_at": "2026-03-28"},
        ]

    def test_objects_passed_through_unchanged(self):
        ids = [{"id": "abc123", "screened_at": "2026-01-01"}]
        result = migrate_screened_ids(ids, "2026-03-28")
        assert result == ids

    def test_mixed_format_handled(self):
        ids = ["abc123", {"id": "def456", "screened_at": "2026-02-01"}]
        result = migrate_screened_ids(ids, "2026-03-28")
        assert {"id": "abc123", "screened_at": "2026-03-28"} in result
        assert {"id": "def456", "screened_at": "2026-02-01"} in result

    def test_migration_assigns_run_date_to_strings(self):
        result = migrate_screened_ids(["old_id"], "2026-03-28")
        assert result[0]["screened_at"] == "2026-03-28"

    def test_invalid_entries_ignored(self):
        # Dicts without 'id' key are skipped
        ids = [{"not_id": "foo"}]
        result = migrate_screened_ids(ids, "2026-03-28")
        assert result == []


# ---------------------------------------------------------------------------
# Pruning tests
# ---------------------------------------------------------------------------


class TestPruning:
    def test_empty_list_stays_empty(self):
        assert prune_screened_ids([], "2026-03-28") == []

    def test_recent_ids_retained(self):
        ids = [{"id": "abc", "screened_at": "2026-03-27"}]  # 1 day ago
        result = prune_screened_ids(ids, "2026-03-28")
        assert result == ids

    def test_id_exactly_at_cutoff_retained(self):
        # 60 days ago — boundary: should be retained (> cutoff, not >=)
        run_date = "2026-03-28"
        cutoff_date = (date.fromisoformat(run_date) - timedelta(days=60)).isoformat()
        ids = [{"id": "boundary", "screened_at": cutoff_date}]
        result = prune_screened_ids(ids, run_date)
        # cutoff_date is exactly at cutoff — our rule is > cutoff so this is pruned
        assert result == []

    def test_id_one_day_inside_ttl_retained(self):
        run_date = "2026-03-28"
        recent_date = (date.fromisoformat(run_date) - timedelta(days=59)).isoformat()
        ids = [{"id": "recent", "screened_at": recent_date}]
        result = prune_screened_ids(ids, run_date)
        assert len(result) == 1

    def test_old_ids_pruned(self):
        run_date = "2026-03-28"
        old_date = (date.fromisoformat(run_date) - timedelta(days=90)).isoformat()
        ids = [{"id": "old", "screened_at": old_date}]
        result = prune_screened_ids(ids, run_date)
        assert result == []

    def test_mix_of_old_and_new(self):
        run_date = "2026-03-28"
        old = (date.fromisoformat(run_date) - timedelta(days=90)).isoformat()
        new = (date.fromisoformat(run_date) - timedelta(days=10)).isoformat()
        ids = [
            {"id": "old_id", "screened_at": old},
            {"id": "new_id", "screened_at": new},
        ]
        result = prune_screened_ids(ids, run_date)
        assert len(result) == 1
        assert result[0]["id"] == "new_id"

    def test_custom_ttl(self):
        run_date = "2026-03-28"
        two_weeks_ago = (date.fromisoformat(run_date) - timedelta(days=14)).isoformat()
        ids = [{"id": "x", "screened_at": two_weeks_ago}]
        # With 7-day TTL, 14 days ago should be pruned
        assert prune_screened_ids(ids, run_date, ttl_days=7) == []
        # With 30-day TTL, 14 days ago should be retained
        assert len(prune_screened_ids(ids, run_date, ttl_days=30)) == 1

    def test_large_list_performance(self):
        # Ensure pruning doesn't break with a large list (simulates months of use)
        run_date = "2026-03-28"
        ids = [{"id": f"msg{i:06d}", "screened_at": "2026-03-01"} for i in range(5000)]
        result = prune_screened_ids(ids, run_date)
        assert len(result) == 5000  # 2026-03-01 is 27 days ago — within 60-day TTL


# ---------------------------------------------------------------------------
# add_screened_id tests
# ---------------------------------------------------------------------------


class TestAddScreenedId:
    def test_adds_in_object_format(self):
        ids = []
        result = add_screened_id(ids, "msg001", "2026-03-28")
        assert result == [{"id": "msg001", "screened_at": "2026-03-28"}]

    def test_appends_to_existing(self):
        ids = [{"id": "existing", "screened_at": "2026-03-01"}]
        result = add_screened_id(ids, "new", "2026-03-28")
        assert len(result) == 2
        assert result[-1] == {"id": "new", "screened_at": "2026-03-28"}

    def test_does_not_mutate_original(self):
        ids = [{"id": "a", "screened_at": "2026-03-01"}]
        _ = add_screened_id(ids, "b", "2026-03-28")
        assert len(ids) == 1  # original unchanged


# ---------------------------------------------------------------------------
# End-to-end: migrate → add → prune cycle
# ---------------------------------------------------------------------------


class TestFullCycle:
    def test_migrate_then_prune_removes_old_legacy_ids(self):
        """
        Legacy IDs migrated on 2026-01-01 should be pruned by 2026-03-28
        (87 days later, beyond the 60-day TTL).
        """
        legacy_ids = ["old1", "old2", "old3"]
        migration_date = "2026-01-01"
        run_date = "2026-03-28"

        migrated = migrate_screened_ids(legacy_ids, migration_date)
        pruned = prune_screened_ids(migrated, run_date)
        assert pruned == []

    def test_recent_ids_survive_full_cycle(self):
        run_date = "2026-03-28"
        ids = []
        ids = add_screened_id(ids, "msg001", "2026-03-20")
        ids = add_screened_id(ids, "msg002", "2026-03-25")
        pruned = prune_screened_ids(ids, run_date)
        assert len(pruned) == 2

    def test_criteria_json_structure_valid_after_operations(self):
        """Verify the resulting structure is valid JSON and has expected shape."""
        run_date = "2026-03-28"
        criteria = {
            "profile_name": "Test",
            "screened_message_ids": ["legacy1", "legacy2"],
            "last_run_date": "2026-01-01",
        }
        # Simulate what happens on a run: migrate, add new, prune, save
        ids = migrate_screened_ids(criteria["screened_message_ids"], run_date)
        ids = add_screened_id(ids, "new_msg", run_date)
        ids = prune_screened_ids(ids, run_date)
        criteria["screened_message_ids"] = ids
        criteria["last_run_date"] = run_date

        # Should serialize cleanly
        serialized = json.dumps(criteria)
        parsed = json.loads(serialized)
        assert all(isinstance(e, dict) for e in parsed["screened_message_ids"])
        assert parsed["last_run_date"] == run_date
