from __future__ import annotations

import queue
import time

import numpy as np
import sounddevice as sd

from noise_monitor.config import AppConfig
from noise_monitor.core.analyzer import AirNoiseAnalyzer
from noise_monitor.core.dsp import RfftProcessor
from noise_monitor.core.leq import LeqCalculator
from noise_monitor.core.types import NoiseMeasurement, NoiseType
from noise_monitor.alert.rules import NoiseJudge, PeriodResolver
from noise_monitor.alert.notifier import DiscordNotifier, AsyncNotifier
from noise_monitor.utils.plotter import SpectrumPlotter


class SoundNoiseMonitor:
    def __init__(self, config: AppConfig, notifier: DiscordNotifier | None = None):
        self.config = config
        c = config.sound
        self.audio_queue: queue.Queue[bytes] = queue.Queue(maxsize=100)
        self.fft = RfftProcessor(c.frame_size, c.sample_rate_hz)
        self.analyzer = AirNoiseAnalyzer(c.int16_max, c.spl_offset)
        self.leq = LeqCalculator(c.leq_window_size)
        self.period_resolver = PeriodResolver(config.time)
        self.judge = NoiseJudge(config.threshold)
        base_notifier = notifier or DiscordNotifier(config.alert)
        self.notifier = AsyncNotifier(base_notifier)
        self.plotter = SpectrumPlotter(
            path=config.debug.sound_plot_path,
            interval=config.debug.sound_plot_interval,
            enabled=config.debug.plot_enabled,
            xlim=(10, 2000),
            ylim=(0, 100),
            ylabel="Amplitude (dBA)",
            title="Air Sound FFT Spectrum",
        )

    def _callback(self, indata, frames, callback_time, status) -> None:
        if status:
            print(f"[sound] input status: {status}")
        try:
            self.audio_queue.put_nowait(bytes(indata))
        except queue.Full:
            _ = self.audio_queue.get_nowait()
            self.audio_queue.put_nowait(bytes(indata))
            print("[sound] queue full: dropped oldest audio frame")

    def run_forever(self) -> None:
        c = self.config.sound
        with sd.RawInputStream(
            samplerate=c.sample_rate_hz,
            blocksize=c.frame_size,
            device=c.device,
            channels=c.channels,
            dtype="int16",
            callback=self._callback,
        ):
            print("[sound] microphone stream started")
            while True:
                data = self.audio_queue.get()
                audio = np.frombuffer(data, dtype=np.int16)
                if audio.size != c.frame_size:
                    audio = audio[: c.frame_size]
                self._process_frame(audio)

    def _process_frame(self, audio: np.ndarray) -> None:
        t0 = time.perf_counter()
        spectrum = self.fft.transform(audio)
        result = self.analyzer.analyze(spectrum.freq_hz, spectrum.amplitude)
        leq_dba = self.leq.push(result.moment_dba)
        period, current_time = self.period_resolver.resolve()

        measurement = NoiseMeasurement(
            noise_type=NoiseType.AIR,
            moment_dba=result.moment_dba,
            leq_dba=leq_dba,
            period=period,
            current_time=current_time,
        )
        
        if self.config.debug.enabled:
            print("-" * 50)
            print(f"[sound] samples: {audio[:10].tolist()} ... size={audio.size}")
            print(f"[sound] moment={result.moment_dba:.2f} dBA, Leq={leq_dba:.2f} dBA ({self.leq.size}/{self.leq.maxlen})")
            print(f"[sound] processing={time.perf_counter() - t0:.4f}s")

        violations = self.judge.check(measurement)
        if not violations:
            if not violations and self.config.debug.enabled:
                print("[sound] 소음 기준 초과 없음")
                
        for violation in violations:
            self.notifier.notify(violation)

        self.plotter.maybe_save(result.freq_hz, result.spectrum_dba)
