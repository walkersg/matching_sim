"""Data recording: event log and per-schedule summaries."""
from __future__ import annotations
import csv
import json
import os
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Optional


@dataclass
class BehaviorEvent:
    session_id: str
    participant_id: str
    timestamp_ms: float          # perf_counter relative to session start, ms
    wall_clock: str              # ISO-8601
    schedule_index: int          # 0=acquisition, 1–N=experimental, -1=extinction
    schedule_phase: str          # "acquisition" | "experimental" | "extinction"
    event_type: str              # "response" | "reinforcer" | "changeover" | "schedule_start" | "schedule_end"
    active_alt: int              # 1 or 2
    cod_active: bool
    reinforcer_collected: bool
    modality: str
    alt1_ri_s: float
    alt2_ri_s: float


@dataclass
class ScheduleSummary:
    session_id: str
    participant_id: str
    schedule_index: int
    phase: str
    ri1_s: float
    ri2_s: float
    duration_actual_s: float
    B1: int                      # responses on alt 1
    B2: int                      # responses on alt 2
    R1: int                      # reinforcers from alt 1
    R2: int                      # reinforcers from alt 2
    CO: int                      # changeovers
    exclusive_acquisition: bool  # True if reinforcers only from one alt
    extended_duration: bool      # True if forced-choice extension triggered


@dataclass
class GMLFit:
    session_id: str
    participant_id: str
    schedules_included: list[int]
    n: int
    sensitivity: float           # a
    log_bias: float              # log(b)
    r_squared: float
    fitting_method: str = "ols"


class SessionRecorder:
    def __init__(self, session_id: str, participant_id: str, output_dir: str, modality: str) -> None:
        self.session_id = session_id
        self.participant_id = participant_id
        self.output_dir = output_dir
        self.modality = modality
        self._t0 = time.perf_counter()
        self._events: list[BehaviorEvent] = []
        self._summaries: list[ScheduleSummary] = []
        os.makedirs(output_dir, exist_ok=True)

    def _elapsed_ms(self) -> float:
        return (time.perf_counter() - self._t0) * 1000.0

    def log_event(
        self,
        schedule_index: int,
        schedule_phase: str,
        event_type: str,
        active_alt: int,
        cod_active: bool,
        reinforcer_collected: bool,
        alt1_ri_s: float,
        alt2_ri_s: float,
    ) -> None:
        self._events.append(BehaviorEvent(
            session_id=self.session_id,
            participant_id=self.participant_id,
            timestamp_ms=self._elapsed_ms(),
            wall_clock=datetime.now(timezone.utc).isoformat(),
            schedule_index=schedule_index,
            schedule_phase=schedule_phase,
            event_type=event_type,
            active_alt=active_alt,
            cod_active=cod_active,
            reinforcer_collected=reinforcer_collected,
            modality=self.modality,
            alt1_ri_s=alt1_ri_s,
            alt2_ri_s=alt2_ri_s,
        ))

    def add_summary(self, summary: ScheduleSummary) -> None:
        self._summaries.append(summary)

    def save(self, config_json: str) -> None:
        prefix = os.path.join(self.output_dir, f"{self.session_id}")
        # Events CSV
        if self._events:
            keys = list(asdict(self._events[0]).keys())
            with open(f"{prefix}_events.csv", "w", newline="") as f:
                w = csv.DictWriter(f, fieldnames=keys)
                w.writeheader()
                for e in self._events:
                    w.writerow(asdict(e))
        # Summaries CSV
        if self._summaries:
            keys = list(asdict(self._summaries[0]).keys())
            with open(f"{prefix}_summaries.csv", "w", newline="") as f:
                w = csv.DictWriter(f, fieldnames=keys)
                w.writeheader()
                for s in self._summaries:
                    w.writerow(asdict(s))
        # Config JSON embedded in session file
        with open(f"{prefix}_config.json", "w") as f:
            f.write(config_json)

    @property
    def summaries(self) -> list[ScheduleSummary]:
        return list(self._summaries)
