"""
scheduler.py — two-tier interval state machine for jerbs daemon

States:
  off_hours  → 60 min
  biz_hours  → 15 min
"""

from datetime import datetime
from zoneinfo import ZoneInfo

BIZ_INTERVAL_S = 15 * 60
OFFHRS_INTERVAL_S = 60 * 60


class Scheduler:
    def __init__(
        self, biz_start_hour: int = 9, biz_end_hour: int = 17, timezone: str = "America/New_York"
    ):
        self.biz_start = biz_start_hour
        self.biz_end = biz_end_hour
        self.tz = ZoneInfo(timezone)
        self.tz_name = timezone

    def is_biz_hours(self) -> bool:
        now = datetime.now(self.tz)
        hour = now.hour
        return self.biz_start <= hour < self.biz_end

    def current_mode(self) -> str:
        return "biz_hours" if self.is_biz_hours() else "off_hours"

    def current_interval(self) -> int:
        return BIZ_INTERVAL_S if self.is_biz_hours() else OFFHRS_INTERVAL_S
