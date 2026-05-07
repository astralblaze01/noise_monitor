from __future__ import annotations

import time
from dataclasses import dataclass, field

import requests
import queue
import threading

from noise_monitor.config import AlertConfig
from noise_monitor.core.types import NoiseType, Period, ThresholdViolation


_REFERENCE_SOUNDS = [
    (20, "나뭇잎 바스락거리는 소리"),
    (30, "도서관 내부 수준"),
    (40, "조용한 주거지역 밤"),
    (50, "조용한 사무실"),
    (60, "일반 대화 소리"),
    (70, "청소기 돌리는 소리"),
    (80, "지하철 내부 소음"),
    (90, "오토바이 엔진 소리"),
    (100, "착암기 작업 현장"),
    (110, "락 콘서트 앞자리"),
    (120, "제트기 이륙 근처"),
]


def reference_sound(dba: float) -> str:
    for threshold, label in _REFERENCE_SOUNDS:
        if dba <= threshold:
            return label
    return "제트 엔진 바로 옆"


@dataclass
class GeminiMessageGenerator:
    config: AlertConfig
    _model: object | None = field(default=None, init=False, repr=False)

    def generate(self, violation: ThresholdViolation) -> str:
        fallback = self._fallback_message(violation)
        if not self.config.use_ai_message or not self.config.gemini_api_key:
            return fallback

        try:
            import google.generativeai as genai

            if self._model is None:
                genai.configure(api_key=self.config.gemini_api_key)
                self._model = genai.GenerativeModel(model_name=self.config.gemini_model_name)

            noise_label = "생활 소음(공기전달)" if violation.noise_type == NoiseType.AIR else "충격음(고체전달)"
            prompt = (
                "아파트 층간소음 예방 시스템의 Discord 알림 문구를 한국어로 작성해줘. "
                "갈등을 키우지 않도록 짧고 재치 있게, 하지만 자제 요청은 분명하게 해줘.\n"
                f"소음 유형: {noise_label}\n"
                f"측정값: {violation.measured_dba:.1f} dB(A)\n"
                f"기준치: {violation.threshold_dba:.1f} dB(A)\n"
                f"초과량: {violation.excess_dba:.1f} dB(A)\n"
                f"비슷한 소리: {reference_sound(violation.measured_dba)}\n"
            )
            response = self._model.generate_content(prompt)
            text = getattr(response, "text", "").strip()
            return text or fallback
        except Exception as exc:
            print(f"[alarm] Gemini 메시지 생성 실패: {exc}")
            return fallback

    @staticmethod
    def _fallback_message(violation: ThresholdViolation) -> str:
        return (
            f"🔊 현재 소음이 {violation.measured_dba:.1f} dB(A)로 측정되어 "
            f"기준치 {violation.threshold_dba:.1f} dB(A)를 {violation.excess_dba:.1f} dB(A) 초과했습니다. "
            "소음 발생에 주의해 주세요."
        )


class DiscordNotifier:
    def __init__(self, config: AlertConfig, message_generator: GeminiMessageGenerator | None = None):
        self.config = config
        self.message_generator = message_generator or GeminiMessageGenerator(config)
        self._last_alert_time: dict[tuple[str, str], float] = {}

    def notify(self, violation: ThresholdViolation) -> bool:
        if not self.config.discord_webhook_url:
            print("[alarm] DISCORD_WEBHOOK_URL이 없어 알림을 생략합니다.")
            return False

        key = (violation.noise_type.value, violation.measure_type.value)
        now = time.time()
        last = self._last_alert_time.get(key, 0.0)
        if now - last < self.config.cooldown_sec:
            print(f"[alarm] 쿨다운 중: {key}, {violation.measured_dba:.1f} dB(A)")
            return False

        payload = {"embeds": [self._build_embed(violation, self.message_generator.generate(violation))]}
        try:
            resp = requests.post(self.config.discord_webhook_url, json=payload, timeout=10)
            if resp.status_code == 204:
                self._last_alert_time[key] = now
                print(f"[alarm] Discord 알림 전송 성공: {violation.measured_dba:.1f} dB(A)")
                return True
            print(f"[alarm] Discord 전송 실패: HTTP {resp.status_code} - {resp.text}")
            return False
        except requests.RequestException as exc:
            print(f"[alarm] Discord 요청 오류: {exc}")
            return False

    def _build_embed(self, violation: ThresholdViolation, message: str) -> dict:
        excess = violation.excess_dba
        color = 0xFFCC00 if excess < 5 else 0xFF6600 if excess < 10 else 0xFF0000
        noise_label = "🌬️ 공기전달 소음" if violation.noise_type == NoiseType.AIR else "💥 고체전달 충격음"
        period_label = "☀️ 주간" if violation.period == Period.DAY else "🌙 야간"

        return {
            "title": f"🚨 소음 기준치 초과 알림 ({violation.measure_type.value})",
            "description": message,
            "color": color,
            "fields": [
                {"name": "측정값", "value": f"**{violation.measured_dba:.1f} dB(A)**", "inline": True},
                {"name": "기준치", "value": f"{violation.threshold_dba:.1f} dB(A)", "inline": True},
                {"name": "초과량", "value": f"**+{excess:.1f} dB(A)**", "inline": True},
                {"name": "소음 유형", "value": noise_label, "inline": True},
                {"name": "시간대", "value": f"{period_label} ({violation.current_time.strftime('%H:%M:%S')})", "inline": True},
                {"name": "기준 예시", "value": reference_sound(violation.measured_dba), "inline": True},
            ],
            "footer": {"text": "Noise Monitor System · Raspberry Pi"},
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }


class AsyncNotifier:
    """
    Discord/Gemini 알림을 백그라운드 스레드에서 처리한다.
    같은 noise_type + measure_type 알림이 이미 처리 대기 중이면 중복으로 큐에 넣지 않는다.
    또한 동일 알림을 너무 자주 큐에 넣지 않도록 짧은 재시도 간격을 둔다.
    """

    def __init__(self, notifier, max_queue_size: int = 20, enqueue_interval_sec: float = 1.0):
        self.notifier = notifier
        self.queue: queue.Queue = queue.Queue(maxsize=max_queue_size)
        self._pending_keys: set[tuple[str, str]] = set()
        self._last_enqueue_time: dict[tuple[str, str], float] = {}
        self._enqueue_interval_sec = enqueue_interval_sec
        self._lock = threading.Lock()

        self.worker = threading.Thread(
            target=self._worker_loop,
            name="alert-worker",
            daemon=True,
        )
        self.worker.start()

    def notify(self, violation) -> bool:
        key = (violation.noise_type.value, violation.measure_type.value)
        now = time.monotonic()

        with self._lock:
            if key in self._pending_keys:
                return False

            last_enqueue = self._last_enqueue_time.get(key, 0.0)
            if now - last_enqueue < self._enqueue_interval_sec:
                return False

            try:
                self.queue.put_nowait(violation)
                self._pending_keys.add(key)
                self._last_enqueue_time[key] = now
                return True
            except queue.Full:
                print("[alarm] 알림 큐가 가득 차서 알림 요청을 버렸습니다.")
                return False

    def _worker_loop(self) -> None:
        while True:
            violation = self.queue.get()
            key = (violation.noise_type.value, violation.measure_type.value)

            try:
                self.notifier.notify(violation)
            except Exception as e:
                print(f"[alarm] 비동기 알림 처리 실패: {e}")
            finally:
                with self._lock:
                    self._pending_keys.discard(key)

                self.queue.task_done()