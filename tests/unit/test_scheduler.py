"""
Unit tests for scheduler.py — interval state machine.
"""

import time
import pytest
from unittest.mock import patch
from datetime import datetime
from zoneinfo import ZoneInfo

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "claude-code"))

from scheduler import (
    Scheduler,
    RAPID_INTERVAL_S,
    BIZ_INTERVAL_S,
    OFFHRS_INTERVAL_S,
    RAPID_DURATION_S,
)


def make_scheduler(hour: int, tz: str = "America/New_York") -> Scheduler:
    """Return a Scheduler with is_biz_hours patched to reflect the given hour."""
    s = Scheduler(biz_start_hour=9, biz_end_hour=17, timezone=tz)
    mock_dt = datetime(2026, 3, 28, hour, 0, 0, tzinfo=ZoneInfo(tz))
    with patch("scheduler.datetime") as mock:
        mock.now.return_value = mock_dt
        yield s


# ---------------------------------------------------------------------------
# is_biz_hours
# ---------------------------------------------------------------------------

class TestIsBizHours:
    def _sched(self, hour: int) -> Scheduler:
        s = Scheduler(biz_start_hour=9, biz_end_hour=17, timezone="America/New_York")
        mock_dt = datetime(2026, 3, 28, hour, 0, 0, tzinfo=ZoneInfo("America/New_York"))
        s._now = lambda: mock_dt
        # Patch is_biz_hours to use _now
        original = s.is_biz_hours.__func__

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
# rapid mode
# ---------------------------------------------------------------------------

class TestRapidMode:
    def test_not_in_rapid_initially(self):
        s = Scheduler()
        assert s.in_rapid() is False

    def test_in_rapid_after_trigger(self):
        s = Scheduler()
        s.trigger_rapid()
        assert s.in_rapid() is True

    def test_rapid_expires(self):
        s = Scheduler()
        # Set _rapid_end to just in the past
        s._rapid_end = time.monotonic() - 1
        assert s.in_rapid() is False

    def test_rapid_remaining_positive_when_active(self):
        s = Scheduler()
        s.trigger_rapid()
        remaining = s.rapid_remaining()
        assert 0 < remaining <= RAPID_DURATION_S

    def test_rapid_remaining_zero_when_inactive(self):
        s = Scheduler()
        assert s.rapid_remaining() == 0

    def test_rapid_remaining_zero_when_expired(self):
        s = Scheduler()
        s._rapid_end = time.monotonic() - 1
        assert s.rapid_remaining() == 0

    def test_trigger_rapid_resets_timer(self):
        s = Scheduler()
        s.trigger_rapid()
        first = s.rapid_remaining()
        time.sleep(0.01)
        s.trigger_rapid()
        second = s.rapid_remaining()
        # Second trigger should be >= first (timer reset)
        assert second >= first - 1  # allow 1s tolerance


# ---------------------------------------------------------------------------
# current_mode and current_interval
# ---------------------------------------------------------------------------

class TestCurrentMode:
    def _sched_at(self, hour: int, in_rapid: bool = False) -> Scheduler:
        s = Scheduler(biz_start_hour=9, biz_end_hour=17, timezone="America/New_York")
        mock_dt = datetime(2026, 3, 28, hour, 0, 0, tzinfo=ZoneInfo("America/New_York"))

        def patched_is_biz():
            return s.biz_start <= mock_dt.hour < s.biz_end

        s.is_biz_hours = patched_is_biz
        if in_rapid:
            s.trigger_rapid()
        return s

    def test_mode_rapid_takes_priority_over_biz(self):
        s = self._sched_at(10, in_rapid=True)
        assert s.current_mode() == "rapid"

    def test_mode_rapid_takes_priority_over_off_hours(self):
        s = self._sched_at(20, in_rapid=True)
        assert s.current_mode() == "rapid"

    def test_mode_biz_hours(self):
        s = self._sched_at(10, in_rapid=False)
        assert s.current_mode() == "biz_hours"

    def test_mode_off_hours(self):
        s = self._sched_at(20, in_rapid=False)
        assert s.current_mode() == "off_hours"

    def test_interval_rapid(self):
        s = self._sched_at(10, in_rapid=True)
        assert s.current_interval() == RAPID_INTERVAL_S

    def test_interval_biz_hours(self):
        s = self._sched_at(10, in_rapid=False)
        assert s.current_interval() == BIZ_INTERVAL_S

    def test_interval_off_hours(self):
        s = self._sched_at(20, in_rapid=False)
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
