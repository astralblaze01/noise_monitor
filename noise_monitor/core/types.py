from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from datetime import time


class NoiseType(StrEnum):
    AIR = "air"
    SOLID = "solid"


class Period(StrEnum):
    DAY = "day"
    NIGHT = "night"


class MeasureType(StrEnum):
    MOMENT = "Lmax"
    LEQ = "Leq"


@dataclass(frozen=True)
class NoiseMeasurement:
    noise_type: NoiseType
    moment_dba: float
    leq_dba: float
    period: Period
    current_time: time


@dataclass(frozen=True)
class ThresholdViolation:
    noise_type: NoiseType
    measure_type: MeasureType
    measured_dba: float
    threshold_dba: float
    period: Period
    current_time: time

    @property
    def excess_dba(self) -> float:
        return self.measured_dba - self.threshold_dba
