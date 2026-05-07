from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import numpy as np


@dataclass
class SpectrumPlotter:
    path: str
    interval: int
    enabled: bool = False
    xlim: tuple[float, float] | None = None
    ylim: tuple[float, float] | None = None
    xlabel: str = "Frequency (Hz)"
    ylabel: str = "Amplitude"
    title: str = "FFT Spectrum"

    def __post_init__(self) -> None:
        self._counter = 0

    def maybe_save(self, freq_hz: np.ndarray, values: np.ndarray) -> None:
        if not self.enabled:
            return
        self._counter += 1
        if self._counter < self.interval:
            return
        self._counter = 0

        import matplotlib.pyplot as plt

        plt.figure(figsize=(9, 4))
        plt.plot(freq_hz, values)
        plt.xlabel(self.xlabel)
        plt.ylabel(self.ylabel)
        plt.title(self.title)
        if self.xlim:
            plt.xlim(*self.xlim)
        if self.ylim:
            plt.ylim(*self.ylim)
        plt.tight_layout()
        Path(self.path).parent.mkdir(parents=True, exist_ok=True) if Path(self.path).parent != Path('.') else None
        plt.savefig(self.path)
        plt.close()
        print(f"[plot] saved: {self.path}")
