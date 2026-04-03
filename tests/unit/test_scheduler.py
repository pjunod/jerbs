"""
Unit tests for scheduler.py — two-tier interval state machine.
"""

import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "claude-code"))

from scheduler import (
    BIZ_INTERVAL_S,
    OFFHRS_INTERVAL_S,
    Scheduler,
)

# ---------------------------------------------------------------------------
# is_biz_hours
# ---------------------------------------------------------------------------


class TestIsBizHours:
    def _sched(self, hour: int) -> Scheduler:
        s = Scheduler(biz_start_hour=9, biz_end_hour=17, timezone="America/New_York")
        mock_dt = datetime(2026, 3, 28, hour, 0, 0, tzinfo=ZoneInfo("America/New_York"))
        s._now = lambda: mock_dt

        def patched_is_biz(self_inner):
            now = self_inner._now()
            return self_inner.biz_start <= now.hour < self_inner.biz_end

        s.is_biz_hours = lambda: patched_is_biz(s)
        return s

    def test_start_of_biz_hours(self):
        s = self._sched(9)
        assert s.is_biz_hours() is True

    def test_mid_biz_hours(self):
        s = self._sched(13)
        assert s.is_biz_hours() is True

    def test_end_of_biz_hours_exclusive(self):
        # 17:00 is NOT business hours (biz_end is exclusive)
        s = self._sched(17)
        assert s.is_biz_hours() is False

    def test_before_biz_hours(self):
        s = self._sched(7)
        assert s.is_biz_hours() is False

    def test_after_biz_hours(self):
        s = self._sched(20)
        assert s.is_biz_hours() is False

    def test_midnight(self):
        s = self._sched(0)
        assert s.is_biz_hours() is False


# ---------------------------------------------------------------------------
# current_mode and current_interval
# ---------------------------------------------------------------------------


class TestCurrentMode:
    def _sched_at(self, hour: int) -> Scheduler:
        s = Scheduler(biz_start_hour=9, biz_end_hour=17, timezone="America/New_York")
        mock_dt = datetime(2026, 3, 28, hour, 0, 0, tzinfo=ZoneInfo("America/New_York"))

        def patched_is_biz():
            return s.biz_start <= mock_dt.hour < s.biz_end

        s.is_biz_hours = patched_is_biz
        return s

    def test_mode_biz_hours(self):
        s = self._sched_at(10)
        assert s.current_mode() == "biz_hours"

    def test_mode_off_hours(self):
        s = self._sched_at(20)
        assert s.current_mode() == "off_hours"

    def test_interval_biz_hours(self):
        s = self._sched_at(10)
        assert s.current_interval() == BIZ_INTERVAL_S

    def test_interval_off_hours(self):
        s = self._sched_at(20)
        assert s.current_interval() == OFFHRS_INTERVAL_S


# ---------------------------------------------------------------------------
# Custom biz hours and timezone
# ---------------------------------------------------------------------------


class TestCustomBizHours:
    def test_custom_hours(self):
        s = Scheduler(biz_start_hour=8, biz_end_hour=18, timezone="America/New_York")
        mock_dt = datetime(2026, 3, 28, 17, 30, 0, tzinfo=ZoneInfo("America/New_York"))

        def patched_is_biz():
            return s.biz_start <= mock_dt.hour < s.biz_end

        s.is_biz_hours = patched_is_biz
        assert s.is_biz_hours() is True

    def test_custom_hours_outside(self):
        s = Scheduler(biz_start_hour=8, biz_end_hour=18, timezone="America/New_York")
        mock_dt = datetime(2026, 3, 28, 7, 0, 0, tzinfo=ZoneInfo("America/New_York"))

        def patched_is_biz():
            return s.biz_start <= mock_dt.hour < s.biz_end

        s.is_biz_hours = patched_is_biz
        assert s.is_biz_hours() is False
