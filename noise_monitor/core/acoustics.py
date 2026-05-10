from __future__ import annotations

from dataclasses import dataclass
import numpy as np


@dataclass(frozen=True)
class AcousticModel:
    mass_per_unit_area: float
    floor_thickness: float
    alpha: float
    sigma: float
    surface_area: float
    absorption: float

    def sound_transmission_loss(self, freq_hz: np.ndarray) -> np.ndarray:
        freq = np.asarray(freq_hz, dtype=float)
        return 20.0 * np.log10(self.mass_per_unit_area * freq) - 47.0

    def solid_body_spreading_attenuation(self, source_db: np.ndarray, freq_hz: np.ndarray) -> np.ndarray:
        source_db = np.asarray(source_db, dtype=float)
        freq = np.asarray(freq_hz, dtype=float)
        r = self.floor_thickness
        return source_db - (self.alpha * np.sqrt(freq) * r) - 20.0 * np.log10(r)


    def radiated_spl_from_solid(self, source_db: np.ndarray, freq_hz: np.ndarray) -> np.ndarray:
        freq = np.asarray(freq_hz, dtype=float)
        source_db = np.asarray(source_db, dtype=float)
        attenuation_db = self.solid_body_spreading_attenuation(source_db, freq)
        radiation_term = 10.0 * np.log10((self.sigma * self.surface_area) / (self.absorption * np.square(freq)))
        return attenuation_db + radiation_term + 36.0


def a_weighting_db(freq_hz: np.ndarray) -> np.ndarray:
    """IEC A-weighting 근사식."""
    freq = np.asarray(freq_hz, dtype=float)
    f2 = np.square(freq)
    with np.errstate(divide="ignore", invalid="ignore"):
        ra = (12194.0**2 * f2**2) / (
            (f2 + 20.6**2)
            * np.sqrt((f2 + 107.7**2) * (f2 + 737.9**2))
            * (f2 + 12194.0**2)
        )
        weight = 20.0 * np.log10(ra) + 2.0
    return weight


def add_a_weighting(db_array: np.ndarray, freq_hz: np.ndarray) -> np.ndarray:
    return np.asarray(db_array, dtype=float) + a_weighting_db(freq_hz)


def sum_db(db_array: np.ndarray) -> float:
    """dB 배열을 에너지 합산 방식으로 하나의 dB 값으로 합친다."""
    db = np.asarray(db_array, dtype=float)
    mask = np.isfinite(db)
    if not np.any(mask):
        return 0.0

    total_energy = float(np.sum(np.power(10.0, db[mask] / 10.0)))
    if total_energy <= 0.0:
        return 0.0
    return float(10.0 * np.log10(total_energy))
