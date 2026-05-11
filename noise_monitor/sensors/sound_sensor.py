from __future__ import annotations

import queue
import time

import numpy as np
import sounddevice as sd

from noise_monitor.config import AppConfig
from noise_monitor.core.acoustics import AcousticModel
from noise_monitor.core.analyzer import AirNoiseAnalyzer
from noise_monitor.core.dsp import RfftProcessor
from noise_monitor.core.leq import LeqCalculator
from noise_monitor.core.types import NoiseMeasurement, NoiseType, Period
from noise_monitor.alert.rules import NoiseJudge, PeriodResolver
from noise_monitor.alert.notifier import DiscordNotifier, AsyncNotifier
from noise_monitor.utils.plotter import SpectrumPlotter


class SoundNoiseMonitor:
    def __init__(self, config: AppConfig, notifier: DiscordNotifier | None = None):
        self.config = config
        c = config.sound
        self.audio_queue: queue.Queue[bytes] = queue.Queue(maxsize=100)
        self.fft = RfftProcessor(c.frame_size, c.sample_rate_hz)
        self.analyzer = AirNoiseAnalyzer(
            AcousticModel(**config.acoustic.__dict__),
            c.int16_max, 
            c.spl_offset,
            c.mic_distance,
            c.reference_distance
        )
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
            last_time = time.perf_counter()
            while True:
                data = self.audio_queue.get()
                now = time.perf_counter()
                sampling_elapsed = now - last_time
                last_time = now

                audio = np.frombuffer(data, dtype=np.int16)
                if audio.size != c.frame_size:
                    audio = audio[: c.frame_size]
                self._process_frame(audio, sampling_elapsed)

    def _process_frame(self, audio: np.ndarray, sampling_elapsed: float) -> None:
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
        
        violations = self.judge.check(measurement)
        self._print_status(audio, sampling_elapsed, result.moment_dba, leq_dba, time.perf_counter() - t0, violations)
        
        if not violations:
            if self.config.debug.enabled:
                print("[sound] 소음 기준 초과 없음")
                
        for violation in violations:
            self.notifier.notify(violation)

        # 순간 소음(moment)이 기준치를 넘을 때만 그래프 저장
        t = self.config.threshold
        threshold = t.daytime_air_leq if period == Period.DAY else t.nighttime_air_leq
        self.plotter.maybe_save(result.freq_hz, spectrum.amplitude[1:-1], force=(result.moment_dba > threshold))

    def _print_status(self, audio: np.ndarray, sampling_elapsed: float, moment_dba: float, leq_dba: float, processing_elapsed: float, violations) -> None:
        if self.config.debug.enabled:
            print("-" * 50)
            print(f"[sound] samples: {audio[:10].tolist()} ... size={audio.size}")
            print(f"[sound] sampling: {sampling_elapsed:.4f}s")
            print(f"[sound] moment={moment_dba:.2f} dBA, Leq={leq_dba:.2f} dBA ({self.leq.size}/{self.leq.maxlen})")
            print(f"[sound] processing={processing_elapsed:.4f}s")
        elif self.config.debug.measure_log_enabled and moment_dba > 5:
            print(f"[sound] moment={moment_dba:.2f} dBA, Leq={leq_dba:.2f} dBA, sampling={sampling_elapsed:.4f}s, processing={processing_elapsed:.4f}s")
        else:
            # 디버그 모드가 아니더라도 핵심 수치와 처리 시간은 한 줄로 출력 (기준치 초과시만)
            if violations:
                print(f"[sound] moment={moment_dba:.2f} dBA, Leq={leq_dba:.2f} dBA, sampling={sampling_elapsed:.4f}s, processing={processing_elapsed:.4f}s")
