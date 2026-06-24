"""Experiment configuration dataclass and defaults."""
from __future__ import annotations
import json
from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class SchedulePair:
    ri1_s: float
    ri2_s: float
    duration_s: float = 200.0


@dataclass
class ExperimentConfig:
    version: str = "1.0.0"
    modality: str = "keyboard"          # "keyboard" | "mouse"

    # COD
    cod_ms: int = 500                   # 0 = no COD

    # Schedule durations and RI values
    acquisition_ri_s: float = 0.7
    acquisition_duration_s: float = 60.0
    extinction_duration_s: float = 30.0

    experimental_schedules: list[SchedulePair] = field(default_factory=lambda: [
        SchedulePair(7.00, 1.00),
        SchedulePair(5.00, 1.00),
        SchedulePair(3.00, 1.00),
        SchedulePair(2.00, 1.00),
        SchedulePair(1.50, 1.00),
        SchedulePair(1.00, 1.00),
        SchedulePair(1.00, 1.50),
        SchedulePair(1.00, 2.00),
        SchedulePair(1.00, 3.00),
        SchedulePair(1.00, 5.00),
        SchedulePair(1.00, 7.00),
    ])

    # Blackout
    blackout_ms: int = 5000             # 0 = disabled
    blackout_after_acquisition: bool = True
    blackout_after_extinction: bool = False

    # Breaks (list of schedule indices after which to insert a break; 0 = after acquisition)
    break_positions: list[int] = field(default_factory=list)
    break_minimum_ms: int = 30_000      # 30 s minimum break
    break_maximum_ms: Optional[int] = None  # None = unlimited

    # Forced-choice extension
    forced_choice: bool = True
    forced_choice_extension_s: float = 30.0

    # Misc
    leaderboard_visible: bool = True
    max_session_duration_s: float = 7200.0

    def to_json(self) -> str:
        d = asdict(self)
        return json.dumps(d, indent=2)

    @classmethod
    def from_json(cls, s: str) -> "ExperimentConfig":
        d = json.loads(s)
        schedules = [SchedulePair(**sp) for sp in d.pop("experimental_schedules")]
        return cls(experimental_schedules=schedules, **d)

    @classmethod
    def from_file(cls, path: str) -> "ExperimentConfig":
        with open(path) as f:
            return cls.from_json(f.read())

    def save(self, path: str) -> None:
        with open(path, "w") as f:
            f.write(self.to_json())
