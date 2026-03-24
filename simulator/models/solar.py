import math
import random

# Daylight window as fractions of the day (0.0 = midnight)
_DAYLIGHT_START = 6 / 24   # 06:00
_DAYLIGHT_END = 20 / 24    # 20:00


class SolarModel:
    """
    Models solar PV production using a sine curve over daylight hours
    with per-step Gaussian noise to simulate cloud cover.
    """

    def __init__(self, max_kw: float = 100.0, noise_std: float = 5.0):
        self._max_kw = max_kw
        self._noise_std = noise_std

    def generate(self, time_of_day_fraction: float) -> float:
        """
        Returns pv_power_kw for the given time of day fraction (0.0–1.0).
        Zero outside daylight hours; sine curve within, clamped to [0, max_kw].
        """
        if time_of_day_fraction < _DAYLIGHT_START or time_of_day_fraction > _DAYLIGHT_END:
            return 0.0

        daylight_range = _DAYLIGHT_END - _DAYLIGHT_START
        position = (time_of_day_fraction - _DAYLIGHT_START) / daylight_range
        base_power = self._max_kw * math.sin(math.pi * position)
        noise = random.gauss(0, self._noise_std)
        return max(0.0, min(self._max_kw, base_power + noise))
