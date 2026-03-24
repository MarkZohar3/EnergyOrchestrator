from datetime import datetime, timedelta


class SimClock:
    """Tracks simulated time, advancing by a fixed step each tick."""

    SECONDS_PER_DAY = 86400

    def __init__(self, start_time: str, step_interval_s: int):
        """
        start_time: "HH:MM:SS" string (e.g. "00:00:00")
        step_interval_s: seconds to advance per tick
        """
        self._step_interval_s = step_interval_s
        self._elapsed_s = self._parse_time_of_day(start_time)
        self._tick = 0

    def _parse_time_of_day(self, time_str: str) -> int:
        t = datetime.strptime(time_str, "%H:%M:%S")
        return t.hour * 3600 + t.minute * 60 + t.second

    def tick(self):
        self._elapsed_s += self._step_interval_s
        self._tick += 1

    @property
    def time_of_day_fraction(self) -> float:
        """Current time of day as a fraction 0.0 (midnight) to 1.0 (next midnight)."""
        return (self._elapsed_s % self.SECONDS_PER_DAY) / self.SECONDS_PER_DAY

    @property
    def simulated_time(self) -> str:
        """Current simulated time as HH:MM:SS string."""
        total_s = self._elapsed_s % self.SECONDS_PER_DAY
        h = total_s // 3600
        m = (total_s % 3600) // 60
        s = total_s % 60
        return f"{h:02d}:{m:02d}:{s:02d}"

    @property
    def tick_number(self) -> int:
        return self._tick
