# 층간소음 예방 알림 시스템 (noise_monitor)

층간소음을 실시간으로 감지하고 분석하여 기준치 초과 시 Discord 알림을 전송하는 스마트 소음 모니터링 시스템입니다.

마이크 기반 공기전달 소음과 진동 센서 기반 고체전달 충격음을 모두 지원하며, FFT 분석 / dBA 계산 / Leq 계산 / AI 기반 알림 메시지 생성 기능을 포함합니다.

---

# 주요 기능

- 공기전달 소음 측정 (마이크 입력)
- 고체전달 충격음 측정 (시리얼 진동 센서 입력)
- FFT 기반 주파수 분석
- dB / dBA 계산
- 등가소음도(Leq) 계산
- 주야간 기준치 자동 판단
- Discord Webhook 알림 전송
- Gemini AI 기반 자연어 알림 메시지 생성
- 알림 중복 방지 및 쿨다운 시스템
- 로그 저장 및 FFT 그래프 저장
- air / solid / both 모드 지원

---

# 시스템 구조

```text
noise_monitor/
│
├── main.py
├── requirements.txt
├── setup.sh
├── .env
│
├── noise_monitor/
│   ├── config.py
│   ├── processer.py
│   │
│   ├── sensors/
│   │   ├── sound_sensor.py
│   │   └── solid_sensor.py
│   │
│   ├── core/
│   │   ├── dsp.py
│   │   ├── analyzer.py
│   │   ├── leq.py
│   │   └── types.py
│   │
│   ├── alert/
│   │   ├── rules.py
│   │   └── notifier.py
│   │
│   └── utils/
│       └── plotter.py
│
└── logs/
    ├── air/
    └── solid/
```

---

# 동작 방식

## 공기전달 소음 처리

```text
마이크 입력
 → RawInputStream
 → FFT 변환
 → dB 변환
 → 감쇠식 계산
 → A-weighting 적용
 → 순간 dBA 계산
 → Leq 계산
 → 기준 초과 판단
 → Discord 알림
```

## 고체전달 충격음 처리

```text
시리얼 센서 입력
 → frame buffer 누적
 → FFT 변환
 → 진동 분석
 → 감쇠식 계산
 → dBA 계산
 → Leq 계산
 → 기준 초과 판단
 → Discord 알림
```

---

# 설치 방법

## 1. 저장소 클론

```bash
git clone https://github.com/astralblaze01/noise_monitor.git
cd noise_monitor
```

---

## 2. Python 가상환경 생성

```bash
python -m venv .venv
```

### Linux / macOS

```bash
source .venv/bin/activate
```

### Windows

```powershell
.venv\Scripts\activate
```

---

## 3. 패키지 설치

```bash
pip install -r requirements.txt
```

또는:

```bash
bash setup.sh
```

---

# 환경 변수 설정

`.env` 파일을 생성하고 아래 값을 설정합니다.

```env
# Discord
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...

# Gemini
GEMINI_API_KEY=YOUR_API_KEY

# 오디오 입력 장치 번호
SOUND_DEVICE=0

# FFT 그래프 저장 여부
PLOT_ENABLED=1

# AI 메시지 사용 여부
USE_AI_MESSAGE=1
```

---

# 실행 방법

## 공기전달 소음 측정

```bash
python main.py air
```

마이크를 사용하여 공기전달 소음을 측정합니다.

---

## 고체전달 충격음 측정

```bash
python main.py solid
```

시리얼 기반 진동 센서를 사용하여 충격음을 측정합니다.

---

## 두 센서 동시에 실행

```bash
python main.py both
```

공기전달 소음과 고체전달 충격음을 동시에 분석합니다.

---

# 로그 저장

로그는 날짜별로 자동 저장됩니다.

```text
logs/
├── air/
└── solid/
```

콘솔 출력과 파일 저장이 동시에 수행됩니다.

---

# Discord 알림 시스템

기준치를 초과하면 Discord Webhook으로 자동 알림이 전송됩니다.

기능:

- 중복 알림 방지
- 쿨다운 기반 재전송 제한
- AI 기반 자연어 메시지 생성
- 비동기 알림 처리

예시:

```text
⚠️ 야간 층간소음 기준 초과
현재 소음도: 48.2 dBA
Leq: 44.7 dBA
```

---

# FFT 및 dBA 분석

시스템은 다음 과정을 통해 소음을 분석합니다.

```text
raw signal
 → np.fft.rfft()
 → amplitude 계산
 → dB 변환
 → 감쇠식 계산
 → A-weighting 적용
 → dBA 계산
 → Leq 계산
```

---

# 주요 모듈 설명

| 모듈 | 역할 |
|---|---|
| `dsp.py` | FFT 처리 |
| `analyzer.py` | dB / dBA 계산 |
| `leq.py` | 등가소음도 계산 |
| `rules.py` | 기준치 초과 판단 |
| `notifier.py` | Discord / Gemini 알림 |
| `sound_sensor.py` | 마이크 입력 처리 |
| `solid_sensor.py` | 진동 센서 처리 |
| `plotter.py` | FFT 그래프 저장 |

---

# 지원 환경

- Python 3.10+
- Linux
- Raspberry Pi
- Windows (일부 오디오 장치 설정 필요)

---

# 사용 기술

- Python
- NumPy
- SciPy
- sounddevice
- pyserial
- Discord Webhook
- Google Gemini API

---

# 향후 개선 예정

- 웹 대시보드
- 실시간 그래프 UI
- DB 기반 통계 저장
- 모바일 알림 연동
- 머신러닝 기반 소음 분류

---

# 라이선스

MIT License

---

# 참고

오디오 입력 장치 확인:

```python
import sounddevice as sd
print(sd.query_devices())
```
또는
```bash
python tools/index_check.py
```

출력된 장치 번호를 `SOUND_DEVICE` 값으로 설정하면 됩니다.

