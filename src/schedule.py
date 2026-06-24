"""RI schedule and COD timer logic."""
from __future__ import annotations
import math
import random
import time


class RISchedule:
    """Random-interval schedule for one alternative.

    Arms after an exponentially distributed interval; stays armed until
    a response collects the reinforcer.
    """

    def __init__(self, ri_s: float) -> None:
        self.ri_s = ri_s
        self._armed = False
        self._next_arm_time: float = 0.0
        self._active = False

    def start(self) -> None:
        self._active = True
        self._armed = False
        self._schedule_next()

    def stop(self) -> None:
        self._active = False

    def _schedule_next(self) -> None:
        interval = random.expovariate(1.0 / self.ri_s)
        self._next_arm_time = time.perf_counter() + interval

    def tick(self) -> None:
        if self._active and not self._armed:
            if time.perf_counter() >= self._next_arm_time:
                self._armed = True

    @property
    def is_armed(self) -> bool:
        return self._armed

    def collect(self) -> bool:
        """Attempt to collect a reinforcer. Returns True if one was available."""
        if self._armed and self._active:
            self._armed = False
            self._schedule_next()
            return True
        return False


class CODTimer:
    """Changeover delay: locks out reinforcer collection for cod_ms after a switch."""

    def __init__(self, cod_ms: int) -> None:
        self.cod_ms = cod_ms
        self._changeover_time: float = -math.inf

    def record_changeover(self) -> None:
        self._changeover_time = time.perf_counter()

    @property
    def active(self) -> bool:
        if self.cod_ms == 0:
            return False
        return (time.perf_counter() - self._changeover_time) < (self.cod_ms / 1000.0)

    def reset(self) -> None:
        self._changeover_time = -math.inf
