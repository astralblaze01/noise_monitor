from __future__ import annotations

import struct
import time
from collections.abc import Iterator

import numpy as np
import serial

from noise_monitor.config import AppConfig
from noise_monitor.core.acoustics import AcousticModel
from noise_monitor.core.analyzer import SolidNoiseAnalyzer
from noise_monitor.core.dsp import RfftProcessor, SolidPreprocessor
from noise_monitor.core.leq import LeqCalculator
from noise_monitor.core.types import NoiseMeasurement, NoiseType
from noise_monitor.alert.rules import NoiseJudge, PeriodResolver
from noise_monitor.alert.notifier import DiscordNotifier, AsyncNotifier
from noise_monitor.utils.plotter import SpectrumPlotter


class SolidSerialReader:
    def __init__(self, port: str, baud_rate: int, timeout: float, chunk_bytes: int, frame_size: int):
        self.port = port
        self.baud_rate = baud_rate
        self.timeout = timeout
        self.chunk_bytes = chunk_bytes
        self.frame_size = frame_size
        self.values_per_chunk = chunk_bytes // 2
        self.unpack_format = f"<{self.values_per_chunk}h"
        self._serial: serial.Serial | None = None

    def __enter__(self) -> "SolidSerialReader":
        self._serial = serial.Serial(self.port, self.baud_rate, timeout=self.timeout)
        time.sleep(2)
        self._serial.reset_input_buffer()
        print(f"[solid] opened serial port {self.port} at {self.baud_rate}bps")
        
        # 바이트 정렬 자동 맞춤 (Auto-Sync)
        self._sync_alignment()
        return self

    def _sync_alignment(self) -> None:
        """첫 번째 샘플이 음수이면 바이트가 밀린 것으로 간주하고 교정합니다."""
        if self._serial is None:
            return

        # 첫 2바이트(1개 샘플) 읽기
        sample_bytes = self._serial.read(2)
        if len(sample_bytes) < 2:
            return
        
        val = struct.unpack("<h", sample_bytes)[0]
        
        # 센서가 위를 향하면 200~250 양수여야 함. 거대한 음수(-9000 등)는 바이트 밀림의 증거.
        if val < 0:
            print(f"[solid] alignment fixed: negative value {val} detected, skipping 1 byte")
            self._serial.read(1)

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._serial is not None:
            self._serial.close()
            print("[solid] serial port closed")

    def frames(self) -> Iterator[np.ndarray]:
        if self._serial is None:
            raise RuntimeError("SolidSerialReader must be used as a context manager")

        buffer: list[int] = []
        while True:
            raw = self._read_exact(self.chunk_bytes)
            buffer.extend(struct.unpack(self.unpack_format, raw))

            if len(buffer) >= self.frame_size:
                frame = np.asarray(buffer[: self.frame_size], dtype=np.int16)
                del buffer[: self.frame_size]
                yield frame

    def _read_exact(self, size: int) -> bytes:
        assert self._serial is not None
        raw = b""
        while len(raw) < size:
            part = self._serial.read(size - len(raw))
            if not part:
                raise TimeoutError(f"serial read timeout: expected {size} bytes, got {len(raw)} bytes")
            raw += part
        return raw


class SolidNoiseMonitor:
    def __init__(self, config: AppConfig, notifier: DiscordNotifier | None = None):
        self.config = config
        c = config.solid
        self.reader = SolidSerialReader(c.serial_port, c.baud_rate, c.timeout, c.chunk_bytes, c.frame_size)
        self.preprocessor = SolidPreprocessor(c.initial_offset, c.offset_alpha, c.g_per_lsb, c.gravity)
        self.fft = RfftProcessor(c.frame_size, c.sample_rate_hz)
        self.analyzer = SolidNoiseAnalyzer(
            AcousticModel(**config.acoustic.__dict__),
            acc_reference=c.acc_reference,
            acc_cutoff=c.acc_cutoff,
        )
        self.leq = LeqCalculator(c.leq_window_size)
        self.period_resolver = PeriodResolver(config.time)
        self.judge = NoiseJudge(config.threshold)
        base_notifier = notifier or DiscordNotifier(config.alert)
        self.notifier = AsyncNotifier(base_notifier)
        self.plotter = SpectrumPlotter(
            path=config.debug.solid_plot_path,
            interval=config.debug.solid_plot_interval,
            enabled=config.debug.plot_enabled,
            xlim=(10, 500),
            ylim=(0, 1),
            ylabel="Amplitude (m/s^2)",
            title="Solid FFT Spectrum",
        )

    def run_forever(self) -> None:
        with self.reader as reader:
            start = time.perf_counter()
            for raw_frame in reader.frames():
                elapsed = time.perf_counter() - start
                start = time.perf_counter()
                self._process_frame(raw_frame, elapsed)

    def _process_frame(self, raw_frame: np.ndarray, sampling_elapsed: float) -> None:
        t0 = time.perf_counter()
        acceleration = self.preprocessor.to_acceleration(raw_frame)
        spectrum = self.fft.transform(acceleration)
        result = self.analyzer.analyze(spectrum.freq_hz, spectrum.amplitude)
        leq_dba = self.leq.push(result.moment_dba)
        period, current_time = self.period_resolver.resolve()

        measurement = NoiseMeasurement(
            noise_type=NoiseType.SOLID,
            moment_dba=result.moment_dba,
            leq_dba=leq_dba,
            period=period,
            current_time=current_time,
        )

        self._print_status(raw_frame, sampling_elapsed, result.moment_dba, leq_dba, time.perf_counter() - t0)
        violations = self.judge.check(measurement)
        if not violations:
            if not violations and self.config.debug.enabled:
                print("[solid] 소음 기준 초과 없음")
                
        for violation in violations:
            self.notifier.notify(violation)

        self.plotter.maybe_save(result.freq_hz, spectrum.amplitude[1:-1], force=bool(violations))

    def _print_status(self, raw_frame: np.ndarray, sampling_elapsed: float, moment_dba: float, leq_dba: float, processing_elapsed: float) -> None:
        real_hz = self.config.solid.frame_size / sampling_elapsed if sampling_elapsed > 0 else 0.0
        if self.config.debug.enabled:
            print("-" * 50)
            print(f"[solid] samples: {raw_frame[:5].tolist()} ...")
            print(f"[solid] sampling: {sampling_elapsed:.4f}s, real_hz={real_hz:.2f}Hz")
            print(f"[solid] moment={moment_dba:.2f} dBA, Leq={leq_dba:.2f} dBA ({self.leq.size}/{self.leq.maxlen})")
            print(f"[solid] processing={processing_elapsed:.4f}s")
        else:
            # 디버그 모드가 아니더라도 핵심 수치와 처리 시간은 한 줄로 출력
            print(f"[solid] moment={moment_dba:.2f} dBA, Leq={leq_dba:.2f} dBA, sampling={sampling_elapsed:.4f}s, processing={processing_elapsed:.4f}s")
