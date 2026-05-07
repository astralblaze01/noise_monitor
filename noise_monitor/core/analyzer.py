from __future__ import annotations

from dataclasses import dataclass
import numpy as np

from noise_monitor.core.acoustics import AcousticModel, a_weighting_db, sum_db
from noise_monitor.core.dsp import amplitude_to_db, int16_fft_amplitude_to_spl_db


@dataclass(frozen=True)
class AnalyzeResult:
    moment_dba: float
    spectrum_dba: np.ndarray
    freq_hz: np.ndarray


class BaseAnalyzer:
    def __init__(self):
        self._weight_cache: dict[tuple[int, float, float], np.ndarray] = {}

    def _valid_bins(self, freq_hz: np.ndarray, values: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        # 0Hz와 Nyquist 끝 bin 제거. 기존 코드의 [1:-1] 의도를 명확히 함수화했다.
        freq = np.asarray(freq_hz, dtype=float)
        val = np.asarray(values, dtype=float)
        if freq.size <= 2:
            return freq, val
        return freq[1:-1], val[1:-1]

    def _a_weight(self, freq_hz: np.ndarray) -> np.ndarray:
        freq = np.asarray(freq_hz, dtype=float)
        key = (freq.size, float(freq[0]) if freq.size else 0.0, float(freq[-1]) if freq.size else 0.0)
        cached = self._weight_cache.get(key)
        if cached is None:
            cached = a_weighting_db(freq)
            self._weight_cache[key] = cached
        return cached


class AirNoiseAnalyzer(BaseAnalyzer):
    def __init__(self, int16_max: float, spl_offset: float):
        super().__init__()
        self.int16_max = float(int16_max)
        self.spl_offset = float(spl_offset)

    def analyze(self, freq_hz: np.ndarray, amplitude_fft: np.ndarray) -> AnalyzeResult:
        db_spl = int16_fft_amplitude_to_spl_db(amplitude_fft, self.int16_max, self.spl_offset)
        freq, db_spl = self._valid_bins(freq_hz, db_spl)
        dba = db_spl + self._a_weight(freq)
        return AnalyzeResult(moment_dba=sum_db(dba), spectrum_dba=dba, freq_hz=freq)


class SolidNoiseAnalyzer(BaseAnalyzer):
    def __init__(self, acoustic_model: AcousticModel, acc_reference: float, acc_cutoff: float):
        super().__init__()
        self.acoustic_model = acoustic_model
        self.acc_reference = float(acc_reference)
        self.acc_cutoff = float(acc_cutoff)

    def analyze(self, freq_hz: np.ndarray, amplitude_acc: np.ndarray) -> AnalyzeResult:
        acc_db = amplitude_to_db(amplitude_acc, reference=self.acc_reference, cutoff=self.acc_cutoff)
        freq, acc_db = self._valid_bins(freq_hz, acc_db)
        spl_db = self.acoustic_model.radiated_spl_from_solid(acc_db, freq)
        dba = spl_db + self._a_weight(freq)
        return AnalyzeResult(moment_dba=sum_db(dba), spectrum_dba=dba, freq_hz=freq)
