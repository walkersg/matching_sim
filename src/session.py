"""Session state machine: manages schedule sequencing, timing, and state transitions."""
from __future__ import annotations
import time
from enum import Enum, auto
from typing import Optional

from .config import ExperimentConfig, SchedulePair
from .schedule import RISchedule, CODTimer
from .data import SessionRecorder, ScheduleSummary


class Phase(Enum):
    CONSENT = auto()
    INSTRUCTIONS = auto()
    LEADERBOARD = auto()
    BLACKOUT = auto()
    ACQUISITION = auto()
    EXPERIMENTAL = auto()
    BREAK = auto()
    EXTINCTION = auto()
    DEBRIEF = auto()
    DONE = auto()


class ScheduleSession:
    """Runs the full PRESS-B schedule sequence."""

    def __init__(self, config: ExperimentConfig, recorder: SessionRecorder) -> None:
        self.config = config
        self.recorder = recorder

        self.phase = Phase.CONSENT
        self._phase_start: float = 0.0
        self._blackout_return_phase: Optional[Phase] = None

        # Schedule tracking
        self._schedule_idx: int = 0          # 0=acquisition, 1..N=experimental
        self._current_pair: Optional[SchedulePair] = None
        self._schedule_start: float = 0.0

        # Per-schedule counters
        self.B1 = 0
        self.B2 = 0
        self.R1 = 0
        self.R2 = 0
        self.CO = 0
        self._extended = False

        # Response state
        self.active_alt: int = 1
        self._ri1: Optional[RISchedule] = None
        self._ri2: Optional[RISchedule] = None
        self._cod: CODTimer = CODTimer(config.cod_ms)

        # Leaderboard
        self.total_reinforcers: int = 0

        # Consent / instructions acknowledgement
        self.consent_given: bool = False
        self.instructions_read: bool = False

        # Break state
        self._break_after_schedule: int = -1  # which schedule index triggered the break

    # ------------------------------------------------------------------
    # Phase transitions
    # ------------------------------------------------------------------

    def acknowledge_consent(self) -> None:
        if self.phase == Phase.CONSENT:
            self.phase = Phase.INSTRUCTIONS
            self._phase_start = time.perf_counter()

    def acknowledge_instructions(self) -> None:
        if self.phase == Phase.INSTRUCTIONS:
            if self.config.leaderboard_visible:
                self.phase = Phase.LEADERBOARD
            else:
                self._start_acquisition()

    def acknowledge_leaderboard(self) -> None:
        if self.phase == Phase.LEADERBOARD:
            self._start_acquisition()

    def acknowledge_break(self) -> None:
        if self.phase == Phase.BREAK:
            elapsed_ms = (time.perf_counter() - self._phase_start) * 1000
            if elapsed_ms >= self.config.break_minimum_ms:
                self._advance_after_break()

    def _start_acquisition(self) -> None:
        self._schedule_idx = 0
        pair = SchedulePair(
            ri1_s=self.config.acquisition_ri_s,
            ri2_s=self.config.acquisition_ri_s,
            duration_s=self.config.acquisition_duration_s,
        )
        self._begin_schedule(Phase.ACQUISITION, pair)

    def _begin_schedule(self, phase: Phase, pair: SchedulePair) -> None:
        self.phase = phase
        self._current_pair = pair
        self._schedule_start = time.perf_counter()
        self._phase_start = self._schedule_start
        self.B1 = self.B2 = self.R1 = self.R2 = self.CO = 0
        self._extended = False
        self.active_alt = 1
        self._cod = CODTimer(self.config.cod_ms)

        self._ri1 = RISchedule(pair.ri1_s)
        self._ri2 = RISchedule(pair.ri2_s)
        self._ri1.start()
        self._ri2.start()

        self.recorder.log_event(
            schedule_index=self._schedule_idx,
            schedule_phase=phase.name.lower(),
            event_type="schedule_start",
            active_alt=self.active_alt,
            cod_active=False,
            reinforcer_collected=False,
            alt1_ri_s=pair.ri1_s,
            alt2_ri_s=pair.ri2_s,
        )

    def _end_schedule(self) -> None:
        assert self._current_pair is not None
        duration = time.perf_counter() - self._schedule_start
        exclusive = (self.R1 == 0) != (self.R2 == 0)  # exactly one is zero

        self.recorder.log_event(
            schedule_index=self._schedule_idx,
            schedule_phase=self.phase.name.lower(),
            event_type="schedule_end",
            active_alt=self.active_alt,
            cod_active=False,
            reinforcer_collected=False,
            alt1_ri_s=self._current_pair.ri1_s,
            alt2_ri_s=self._current_pair.ri2_s,
        )

        summary = ScheduleSummary(
            session_id=self.recorder.session_id,
            participant_id=self.recorder.participant_id,
            schedule_index=self._schedule_idx,
            phase=self.phase.name.lower(),
            ri1_s=self._current_pair.ri1_s,
            ri2_s=self._current_pair.ri2_s,
            duration_actual_s=duration,
            B1=self.B1, B2=self.B2, R1=self.R1, R2=self.R2, CO=self.CO,
            exclusive_acquisition=exclusive,
            extended_duration=self._extended,
        )
        self.recorder.add_summary(summary)

        if self._ri1:
            self._ri1.stop()
        if self._ri2:
            self._ri2.stop()

    def _maybe_blackout(self, next_phase_fn) -> None:
        if self.config.blackout_ms > 0:
            self.phase = Phase.BLACKOUT
            self._phase_start = time.perf_counter()
            self._blackout_return_phase = None
            self._blackout_next_fn = next_phase_fn
        else:
            next_phase_fn()

    def _advance_from_acquisition(self) -> None:
        self._end_schedule()
        if self.config.blackout_after_acquisition and self.config.blackout_ms > 0:
            self._blackout_next_fn = self._start_experimental
            self.phase = Phase.BLACKOUT
            self._phase_start = time.perf_counter()
        else:
            self._start_experimental()

    def _start_experimental(self) -> None:
        self._schedule_idx = 1
        pair = self.config.experimental_schedules[0]
        self._begin_schedule(Phase.EXPERIMENTAL, pair)

    def _advance_experimental(self) -> None:
        self._end_schedule()
        idx = self._schedule_idx
        # Check for break
        if idx in self.config.break_positions:
            self._break_after_schedule = idx
            self.phase = Phase.BREAK
            self._phase_start = time.perf_counter()
            return
        self._next_experimental_or_extinction()

    def _advance_after_break(self) -> None:
        self._next_experimental_or_extinction()

    def _next_experimental_or_extinction(self) -> None:
        next_exp_idx = self._schedule_idx  # 1-based into experimental_schedules list
        # _schedule_idx was set to the index in the full sequence (1..N)
        exp_list_pos = self._schedule_idx  # position in experimental_schedules (0-based: idx-1)
        next_list_pos = exp_list_pos  # after incrementing _schedule_idx

        schedules = self.config.experimental_schedules
        if next_list_pos >= len(schedules):
            # Done with experimental — go to extinction
            self._start_extinction()
            return
        pair = schedules[next_list_pos]
        self._schedule_idx += 1
        # Blackout between experimental schedules
        if self.config.blackout_ms > 0:
            self._blackout_next_fn = lambda: self._begin_schedule(Phase.EXPERIMENTAL, pair)
            self.phase = Phase.BLACKOUT
            self._phase_start = time.perf_counter()
        else:
            self._begin_schedule(Phase.EXPERIMENTAL, pair)

    def _start_extinction(self) -> None:
        self._schedule_idx = -1
        pair = SchedulePair(ri1_s=999.0, ri2_s=999.0, duration_s=self.config.extinction_duration_s)
        self._begin_schedule(Phase.EXTINCTION, pair)

    def _end_extinction(self) -> None:
        self._end_schedule()
        if self.config.blackout_after_extinction and self.config.blackout_ms > 0:
            self._blackout_next_fn = self._go_debrief
            self.phase = Phase.BLACKOUT
            self._phase_start = time.perf_counter()
        else:
            self._go_debrief()

    def _go_debrief(self) -> None:
        self.phase = Phase.DEBRIEF
        self._phase_start = time.perf_counter()

    # ------------------------------------------------------------------
    # Tick (called every frame)
    # ------------------------------------------------------------------

    def tick(self) -> None:
        if self.phase in (Phase.ACQUISITION, Phase.EXPERIMENTAL, Phase.EXTINCTION):
            if self._ri1:
                self._ri1.tick()
            if self._ri2:
                self._ri2.tick()
            self._check_schedule_end()
        elif self.phase == Phase.BLACKOUT:
            elapsed_ms = (time.perf_counter() - self._phase_start) * 1000
            if elapsed_ms >= self.config.blackout_ms:
                self._blackout_next_fn()

    def _check_schedule_end(self) -> None:
        assert self._current_pair is not None
        elapsed = time.perf_counter() - self._schedule_start
        nominal_done = elapsed >= self._current_pair.duration_s

        if not nominal_done:
            return

        if self.phase == Phase.EXTINCTION:
            self._end_extinction()
            return

        # Forced-choice: extend if one alt has zero reinforcers
        if self.config.forced_choice and (self.R1 == 0 or self.R2 == 0):
            if not self._extended:
                self._extended = True
            max_ext = self._current_pair.duration_s + self.config.forced_choice_extension_s
            if elapsed < max_ext:
                return
            # Extension exhausted — proceed anyway

        if self.phase == Phase.ACQUISITION:
            self._advance_from_acquisition()
        elif self.phase == Phase.EXPERIMENTAL:
            self._advance_experimental()

    # ------------------------------------------------------------------
    # Response handling
    # ------------------------------------------------------------------

    def _active_ri(self) -> Optional[RISchedule]:
        return self._ri1 if self.active_alt == 1 else self._ri2

    def _active_ri_s(self) -> float:
        assert self._current_pair is not None
        return self._current_pair.ri1_s if self.active_alt == 1 else self._current_pair.ri2_s

    @property
    def cod_active(self) -> bool:
        return self._cod.active

    @property
    def active_ri_armed(self) -> bool:
        ri = self._active_ri()
        return ri.is_armed if ri else False

    def respond(self) -> bool:
        """Process a response on the active alternative. Returns True if reinforcer collected."""
        if self.phase not in (Phase.ACQUISITION, Phase.EXPERIMENTAL, Phase.EXTINCTION):
            return False
        assert self._current_pair is not None

        if self.active_alt == 1:
            self.B1 += 1
        else:
            self.B2 += 1

        collected = False
        if not self._cod.active:
            ri = self._active_ri()
            if ri and ri.collect():
                collected = True
                self.total_reinforcers += 1
                if self.active_alt == 1:
                    self.R1 += 1
                else:
                    self.R2 += 1

        self.recorder.log_event(
            schedule_index=self._schedule_idx,
            schedule_phase=self.phase.name.lower(),
            event_type="response",
            active_alt=self.active_alt,
            cod_active=self._cod.active,
            reinforcer_collected=collected,
            alt1_ri_s=self._current_pair.ri1_s,
            alt2_ri_s=self._current_pair.ri2_s,
        )
        return collected

    def changeover(self) -> None:
        """Switch active alternative."""
        if self.phase not in (Phase.ACQUISITION, Phase.EXPERIMENTAL, Phase.EXTINCTION):
            return
        assert self._current_pair is not None
        self.active_alt = 2 if self.active_alt == 1 else 1
        self.CO += 1
        self._cod.record_changeover()

        self.recorder.log_event(
            schedule_index=self._schedule_idx,
            schedule_phase=self.phase.name.lower(),
            event_type="changeover",
            active_alt=self.active_alt,
            cod_active=True,
            reinforcer_collected=False,
            alt1_ri_s=self._current_pair.ri1_s,
            alt2_ri_s=self._current_pair.ri2_s,
        )

    # ------------------------------------------------------------------
    # Schedule progress info for display
    # ------------------------------------------------------------------

    @property
    def schedule_elapsed_s(self) -> float:
        return time.perf_counter() - self._schedule_start

    @property
    def schedule_duration_s(self) -> float:
        if self._current_pair is None:
            return 1.0
        return self._current_pair.duration_s

    @property
    def blackout_elapsed_s(self) -> float:
        return time.perf_counter() - self._phase_start

    @property
    def blackout_duration_s(self) -> float:
        return self.config.blackout_ms / 1000.0

    @property
    def break_elapsed_s(self) -> float:
        return time.perf_counter() - self._phase_start

    @property
    def break_minimum_s(self) -> float:
        return self.config.break_minimum_ms / 1000.0

    @property
    def n_experimental_schedules(self) -> int:
        return len(self.config.experimental_schedules)

    @property
    def current_experimental_position(self) -> int:
        """1-based position within experimental schedules (0 if not experimental)."""
        if self.phase != Phase.EXPERIMENTAL:
            return 0
        return self._schedule_idx

    @property
    def ri1_s(self) -> float:
        return self._current_pair.ri1_s if self._current_pair else 0.0

    @property
    def ri2_s(self) -> float:
        return self._current_pair.ri2_s if self._current_pair else 0.0
