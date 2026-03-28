"""
scheduler.py — interval state machine for jerbs daemon

States:
  off_hours  → 60 min
  biz_hours  → 15 min
  rapid      → 5 min for 30 min, then reverts
"""

import time
from datetime import datetime
from zoneinfo import ZoneInfo

RAPID_INTERVAL_S   = 5  * 60
BIZ_INTERVAL_S     = 15 * 60
OFFHRS_INTERVAL_S  = 60 * 60
RAPID_DURATION_S   = 30 * 60


class Scheduler:
    def __init__(self, biz_start_hour: int = 9, biz_end_hour: int = 17,
                 timezone: str = "America/New_York"):
        self.biz_start  = biz_start_hour
        self.biz_end    = biz_end_hour
        self.tz         = ZoneInfo(timezone)
        self.tz_name    = timezone
        self._rapid_end = 0.0

    def is_biz_hours(self) -> bool:
        now  = datetime.now(self.tz)
        hour = now.hour
        return self.biz_start <= hour < self.biz_end

    def in_rapid(self) -> bool:
        return time.monotonic() < self._rapid_end

    def trigger_rapid(self):
        self._rapid_end = time.monotonic() + RAPID_DURATION_S

    def tick(self):
        """Call after each run to check if rapid mode has expired."""
        pass

    def current_mode(self) -> str:
        if self.in_rapid():
            return "rapid"
        return "biz_hours" if self.is_biz_hours() else "off_hours"

    def current_interval(self) -> int:
        mode = self.current_mode()
        if mode == "rapid":
            return RAPID_INTERVAL_S
        if mode == "biz_hours":
            return BIZ_INTERVAL_S
        return OFFHRS_INTERVAL_S

    def rapid_remaining(self) -> int:
        if not self.in_rapid():
            return 0
        return max(0, int(self._rapid_end - time.monotonic()))
