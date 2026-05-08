"""Project configuration.

실제 값은 기존 프로젝트의 config.py 값으로 바꿔도 됩니다.
환경변수로 덮어쓸 수 있게 구성했습니다.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import time
from dotenv import load_dotenv
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1] #프로젝트 폴더 위치 찾기
load_dotenv(PROJECT_ROOT / ".env") #env 파일 위치 찾기

def _env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    return default if value is None else float(value)


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    return default if value is None else int(value)


def _env_str(name: str, default: str) -> str:
    return os.getenv(name, default)


@dataclass(frozen=True)
class TimeConfig:
    day_start: time = time(6, 0)
    night_start: time = time(22, 0)


@dataclass(frozen=True)
class ThresholdConfig:
    daytime_air_leq: float = _env_float("DAYTIME_AIR_LEQ", 45.0)
    nighttime_air_leq: float = _env_float("NIGHTTIME_AIR_LEQ", 40.0)
    daytime_solid_lmax: float = _env_float("DAYTIME_SOLID_LMAX", 57.0)
    daytime_solid_leq: float = _env_float("DAYTIME_SOLID_LEQ", 43.0)
    nighttime_solid_lmax: float = _env_float("NIGHTTIME_SOLID_LMAX", 52.0)
    nighttime_solid_leq: float = _env_float("NIGHTTIME_SOLID_LEQ", 38.0)


@dataclass(frozen=True)
class AcousticConfig:
    mass_per_unit_area: float = _env_float("MASS_PER_UNIT_AREA", 2400.0 * 0.21)
    floor_thickness: float = _env_float("FLOOR_THICKNESS", 0.21)
    alpha: float = _env_float("ALPHA", 0.03)
    sigma: float = _env_float("SIGMA", 1.0)
    surface_area: float = _env_float("SURFACE_AREA", 10.0)
    absorption: float = _env_float("ABSORPTION", 10.0)


@dataclass(frozen=True)
class SolidSensorConfig:
    serial_port: str = _env_str("SOLID_SERIAL_PORT", "/dev/ttyACM0")
    baud_rate: int = _env_int("SOLID_BAUD_RATE", 230400)
    timeout: float = _env_float("SOLID_TIMEOUT", 1.0)
    chunk_bytes: int = _env_int("SOLID_CHUNK_BYTES", 128)
    frame_size: int = _env_int("SOLID_FRAME_SIZE", 1024)
    sample_rate_hz: int = _env_int("SOLID_SAMPLE_RATE_HZ", 1600)
    initial_offset: float = _env_float("SOLID_INITIAL_OFFSET", 256.0)
    offset_alpha: float = _env_float("SOLID_OFFSET_ALPHA", 0.01)
    g_per_lsb: float = _env_float("SOLID_G_PER_LSB", 0.0039)
    gravity: float = _env_float("GRAVITY", 9.80665)
    acc_cutoff: float = _env_float("SOLID_ACC_CUTOFF", 0.05)
    acc_reference: float = _env_float("SOLID_ACC_REFERENCE", 1e-5)
    leq_window_size: int = _env_int("SOLID_LEQ_WINDOW_SIZE", 100)


@dataclass(frozen=True)
class SoundSensorConfig:
    sample_rate_hz: int = _env_int("SOUND_SAMPLE_RATE_HZ", 44100)
    frame_size: int = _env_int("SOUND_FRAME_SIZE", 1024)
    channels: int = _env_int("SOUND_CHANNELS", 1)
    device: int | None = None if os.getenv("SOUND_DEVICE") in (None, "") else _env_int("SOUND_DEVICE", 0)
    int16_max: float = _env_float("SOUND_INT16_MAX", 32768.0)
    spl_offset: float = _env_float("SOUND_SPL_OFFSET", 100.0)
    leq_window_size: int = _env_int("SOUND_LEQ_WINDOW_SIZE", 13040)


@dataclass(frozen=True)
class DebugConfig:
    enabled: bool = os.getenv("DEBUG", "0") == "1"
    plot_enabled: bool = os.getenv("PLOT_ENABLED", "0") == "1"
    solid_plot_interval: int = _env_int("SOLID_PLOT_INTERVAL", 10) 
    sound_plot_interval: int = _env_int("SOUND_PLOT_INTERVAL", 100)
    solid_plot_path: str = _env_str("SOLID_PLOT_PATH", "fft_result_solid.png")
    sound_plot_path: str = _env_str("SOUND_PLOT_PATH", "fft_result_sound.png")


@dataclass(frozen=True)
class AlertConfig:
    discord_webhook_url: str | None = os.getenv("DISCORD_WEBHOOK_URL")
    gemini_api_key: str | None = os.getenv("GEMINI_API_KEY")
    cooldown_sec: int = _env_int("ALERT_COOLDOWN_SEC", 600) # 10분 간격으로 알람 보내기(기준치 초과할경우)
    gemini_model_name: str = _env_str("GEMINI_MODEL_NAME", "gemini-2.5-flash")
    use_ai_message: bool = os.getenv("USE_AI_MESSAGE", "1") == "1"


@dataclass(frozen=True)
class AppConfig:
    time: TimeConfig = TimeConfig()
    threshold: ThresholdConfig = ThresholdConfig()
    acoustic: AcousticConfig = AcousticConfig()
    solid: SolidSensorConfig = SolidSensorConfig()
    sound: SoundSensorConfig = SoundSensorConfig()
    debug: DebugConfig = DebugConfig()
    alert: AlertConfig = AlertConfig()


APP_CONFIG = AppConfig()
