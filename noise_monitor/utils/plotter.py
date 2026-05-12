from __future__ import annotations

import numpy as np
from dataclasses import dataclass
from pathlib import Path


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

    def maybe_save(self, freq_hz: np.ndarray, values: np.ndarray, force: bool = False) -> None:
        """
        설정된 interval을 최소 간격(쿨다운)으로 사용하여 그래프를 저장합니다.
        스레드 없이 동기 방식으로 동작하며, 간격이 충분히 크다면 큐 오버플로우를 방지할 수 있습니다.
        """
        self._counter += 1
        
        # 1. 설정된 interval만큼 프레임이 지나지 않았으면 즉시 리턴
        if self._counter < self.interval:
            return

        # 2. 저장 조건: (디버그 모드 주기적 저장) OR (기준치 초과 강제 저장)
        if self.enabled or force:
            self._counter = 0  # 카운터 초기화
            self._save_plot(freq_hz, values)

    def _save_plot(self, freq_hz: np.ndarray, values: np.ndarray) -> None:
        """그래프를 생성하고 파일로 저장합니다. (동기 방식)"""
        try:
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
            
            save_path = Path(self.path)
            save_path.parent.mkdir(parents=True, exist_ok=True) if save_path.parent != Path('.') else None
            
            plt.savefig(str(save_path))
            plt.close()
            print(f"[plot] saved: {self.path}")
        except Exception as e:
            print(f"[plot] error saving graph: {e}")
