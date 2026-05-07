from __future__ import annotations

from dataclasses import dataclass
import numpy as np


@dataclass(frozen=True)
class Spectrum:
    freq_hz: np.ndarray
    amplitude: np.ndarray


class RfftProcessor:
    """실시간 처리를 위한 rFFT 처리기.

    효율 개선점:
    - 주파수축과 window를 매 프레임마다 새로 만들지 않고 초기화 시 1회만 계산
    - Hann window 사용 시 coherent gain으로 진폭 스케일 보정
    """
    def __init__(self, frame_size: int, sample_rate_hz: int):
        self.frame_size = int(frame_size)
        self.sample_rate_hz = int(sample_rate_hz)
        self.freq_hz = np.fft.rfftfreq(
            self.frame_size,
            d=1.0 / self.sample_rate_hz,
        )

    def transform(self, samples: np.ndarray) -> Spectrum:
        x = np.asarray(samples, dtype=np.float32)

        if x.size != self.frame_size:
            x = x[: self.frame_size]

        complex_fft = np.fft.rfft(x)
        amplitude = np.abs(complex_fft) * (2.0 / self.frame_size)
        amplitude[0] = 0.0

        return Spectrum(
            freq_hz=self.freq_hz,
            amplitude=amplitude,
        )


class SolidPreprocessor:
    def __init__(self, initial_offset: float, offset_alpha: float, g_per_lsb: float, gravity: float):
        self.current_offset = float(initial_offset)
        self.offset_alpha = float(offset_alpha)
        self.g_per_lsb = float(g_per_lsb)
        self.gravity = float(gravity)

    def to_acceleration(self, raw_frame: np.ndarray) -> np.ndarray:
        buffer_np = np.asarray(raw_frame, dtype=np.float32)

        self.current_offset = (
            (1.0 - self.offset_alpha) * self.current_offset
            + self.offset_alpha * np.mean(buffer_np)
        )

        return (buffer_np - self.current_offset) * self.g_per_lsb * self.gravity


def amplitude_to_db(amplitude: np.ndarray, reference: float, cutoff: float | None = None) -> np.ndarray:
    """선형 진폭 배열을 dB 배열로 변환.

    cutoff 이하 값은 0 dB가 아니라 -inf로 둬서 dB 합산 때 에너지 0으로 처리한다.
    """
    amplitude_np = np.asarray(amplitude, dtype=float)
    db = np.full_like(amplitude_np, -np.inf, dtype=float)

    if cutoff is None:
        mask = amplitude_np > 0
    else:
        mask = amplitude_np > cutoff

    if np.any(mask):
        db[mask] = 20.0 * np.log10(amplitude_np[mask] / reference)
    return db


def int16_fft_amplitude_to_spl_db(amplitude: np.ndarray, int16_max: float, spl_offset: float) -> np.ndarray:
    """int16 PCM FFT 진폭을 간이 dB SPL로 변환.

    실제 절대 dB SPL은 마이크 캘리브레이션이 필요하다. 기존 코드의 offset 방식은 유지하되
    로그 0 방지를 위해 -inf 대신 매우 작은 epsilon을 사용한다.
    """
    amplitude_np = np.asarray(amplitude, dtype=float)
    dbfs = 20.0 * np.log10(np.maximum(amplitude_np, 1e-12) / float(int16_max))
    return dbfs + float(spl_offset)
