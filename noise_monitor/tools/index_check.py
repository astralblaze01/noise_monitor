from __future__ import annotations

import sounddevice as sd


def main() -> None:
    print("--- 입력 가능한 오디오 장치 목록 ---")
    devices = sd.query_devices()
    for index, dev in enumerate(devices):
        if dev.get("max_input_channels", 0) > 0:
            print(f"Index {index}: {dev.get('name')}")


if __name__ == "__main__":
    main()
