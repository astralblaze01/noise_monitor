from __future__ import annotations

from datetime import datetime

from noise_monitor.config import TimeConfig, ThresholdConfig
from noise_monitor.core.types import MeasureType, NoiseMeasurement, NoiseType, Period, ThresholdViolation


class PeriodResolver:
    def __init__(self, config: TimeConfig):
        self.config = config

    def resolve(self, now: datetime | None = None) -> tuple[Period, object]:
        now = now or datetime.now()
        current_time = now.time()
        if self.config.day_start <= current_time < self.config.night_start:
            return Period.DAY, current_time
        return Period.NIGHT, current_time


class NoiseJudge:
    def __init__(self, thresholds: ThresholdConfig):
        self.thresholds = thresholds

    def check(self, measurement: NoiseMeasurement) -> list[ThresholdViolation]:
        violations: list[ThresholdViolation] = []
        t = self.thresholds

        if measurement.noise_type == NoiseType.AIR:
            threshold = t.daytime_air_leq if measurement.period == Period.DAY else t.nighttime_air_leq
            if measurement.leq_dba > threshold:
                violations.append(self._violation(measurement, MeasureType.LEQ, measurement.leq_dba, threshold))
            return violations

        if measurement.period == Period.DAY:
            lmax_threshold = t.daytime_solid_lmax
            leq_threshold = t.daytime_solid_leq
        else:
            lmax_threshold = t.nighttime_solid_lmax
            leq_threshold = t.nighttime_solid_leq

        if measurement.moment_dba > lmax_threshold:
            violations.append(self._violation(measurement, MeasureType.MOMENT, measurement.moment_dba, lmax_threshold))
        if measurement.leq_dba > leq_threshold:
            violations.append(self._violation(measurement, MeasureType.LEQ, measurement.leq_dba, leq_threshold))
        return violations

    @staticmethod
    def _violation(measurement: NoiseMeasurement, measure_type: MeasureType, measured: float, threshold: float) -> ThresholdViolation:
        return ThresholdViolation(
            noise_type=measurement.noise_type,
            measure_type=measure_type,
            measured_dba=measured,
            threshold_dba=threshold,
            period=measurement.period,
            current_time=measurement.current_time,
        )
