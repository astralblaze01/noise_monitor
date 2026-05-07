from __future__ import annotations

from collections import deque
import numpy as np


class LeqCalculator:
    """최근 N개 dB(A) 값으로 등가소음도 Leq 계산.

    dB는 로그 단위라 산술 평균이 아니라 에너지 평균을 사용한다.
    push()는 O(1)로 동작하므로 실시간 루프에 적합하다.
    """

    def __init__(self, maxlen: int):
        if maxlen <= 0:
            raise ValueError("maxlen must be positive")
        self.maxlen = int(maxlen)
        self._energies: deque[float] = deque()
        self._energy_sum = 0.0

    def push(self, db_value: float | None) -> float:
        if db_value is None or not np.isfinite(db_value):
            return self.value

        energy = float(np.power(10.0, db_value / 10.0))
        if len(self._energies) >= self.maxlen:
            self._energy_sum -= self._energies.popleft()

        self._energies.append(energy)
        self._energy_sum += energy
        return self.value

    @property
    def value(self) -> float:
        if not self._energies or self._energy_sum <= 0.0:
            return 0.0
        return float(10.0 * np.log10(self._energy_sum / len(self._energies)))

    @property
    def size(self) -> int:
        return len(self._energies)

    @property
    def is_full(self) -> bool:
        return len(self._energies) >= self.maxlen

    def clear(self) -> None:
        self._energies.clear()
        self._energy_sum = 0.0
