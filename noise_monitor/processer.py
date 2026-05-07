from __future__ import annotations

import argparse
import multiprocessing as mp
import sys
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime
from pathlib import Path
from typing import Callable

from noise_monitor.config import APP_CONFIG
from noise_monitor.sensors.solid_sensor import SolidNoiseMonitor
from noise_monitor.sensors.sound_sensor import SoundNoiseMonitor


class DailyLogFile:
    """
    실행할 때마다 새 파일을 만들지 않고,
    날짜 기준으로 로그 파일을 자동 분리한다.

    예:
      logs/air/air_2026-05-07_Thu.log
      logs/solid/solid_2026-05-07_Thu.log
    """

    def __init__(self, sensor_name: str):
        self.sensor_name = sensor_name
        self.log_dir = Path("logs") / sensor_name
        self.log_dir.mkdir(parents=True, exist_ok=True)

        self._current_key: str | None = None
        self._file = None

    def _get_log_path(self) -> Path:
        now = datetime.now()
        date_key = now.strftime("%Y-%m-%d_%a")
        return self.log_dir / f"{self.sensor_name}_{date_key}.log"

    def _ensure_file(self):
        now_key = datetime.now().strftime("%Y-%m-%d_%a")

        if self._file is not None and self._current_key == now_key:
            return self._file

        if self._file is not None:
            self._file.close()

        self._current_key = now_key
        log_path = self._get_log_path()
        self._file = open(log_path, "a", encoding="utf-8", buffering=1)

        return self._file

    def write(self, data: str) -> None:
        file = self._ensure_file()
        file.write(data)
        file.flush()

    def flush(self) -> None:
        if self._file is not None:
            self._file.flush()

    def close(self) -> None:
        if self._file is not None:
            self._file.close()
            self._file = None


class TimestampTee:
    """
    콘솔과 파일에 동시에 출력한다.
    각 줄 앞에 시간과 센서 이름 prefix를 붙인다.
    """

    def __init__(self, console_stream, file_stream, prefix: str):
        self.console_stream = console_stream
        self.file_stream = file_stream
        self.prefix = prefix
        self._line_start = True

    def write(self, data: str) -> None:
        if not data:
            return

        for chunk in data.splitlines(True):
            if self._line_start and chunk not in ("\n", "\r\n"):
                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                header = f"[{now}] {self.prefix}"

                self.console_stream.write(header)
                self.file_stream.write(header)

            self.console_stream.write(chunk)
            self.file_stream.write(chunk)

            self._line_start = chunk.endswith("\n")

        self.flush()

    def flush(self) -> None:
        self.console_stream.flush()
        self.file_stream.flush()


def process_air_sound() -> None:
    SoundNoiseMonitor(APP_CONFIG).run_forever()


def process_solid_sound() -> None:
    SolidNoiseMonitor(APP_CONFIG).run_forever()


def _run_with_log(target: Callable[[], None], sensor_name: str) -> None:
    """
    air/solid 각각의 출력 내용을
    콘솔에도 보여주고 날짜별 로그 파일에도 저장한다.
    """
    log_file = DailyLogFile(sensor_name)

    stdout_tee = TimestampTee(
        console_stream=sys.__stdout__,
        file_stream=log_file,
        prefix=f"[{sensor_name}] ",
    )

    stderr_tee = TimestampTee(
        console_stream=sys.__stderr__,
        file_stream=log_file,
        prefix=f"[{sensor_name}:ERR] ",
    )

    try:
        with redirect_stdout(stdout_tee), redirect_stderr(stderr_tee):
            print(f"[log] {sensor_name} 로그 시작")
            print(f"[log] 로그 폴더: {(Path('logs') / sensor_name).resolve()}")
            target()
    finally:
        log_file.close()


def process_both() -> None:
    processes = [
        mp.Process(
            target=_run_with_log,
            args=(process_air_sound, "air"),
            name="air-sound",
        ),
        mp.Process(
            target=_run_with_log,
            args=(process_solid_sound, "solid"),
            name="solid-sound",
        ),
    ]

    for process in processes:
        process.start()

    print("[main] both 모드 실행")
    print("[main] air 로그:   logs/air/air_YYYY-MM-DD_Day.log")
    print("[main] solid 로그: logs/solid/solid_YYYY-MM-DD_Day.log")

    try:
        for process in processes:
            process.join()
    except KeyboardInterrupt:
        print("[main] 종료 요청 감지. 센서 프로세스를 종료합니다.")

        for process in processes:
            if process.is_alive():
                process.terminate()

        for process in processes:
            process.join()


def main() -> None:
    parser = argparse.ArgumentParser(description="층간소음 예방 알림 시스템")
    parser.add_argument("mode", choices=("air", "solid", "both"), help="실행할 센서 모드")
    args = parser.parse_args()

    if args.mode == "air":
        print("[main] air 모드 실행")
        print("[main] air 로그: logs/air/air_YYYY-MM-DD_Day.log")
        _run_with_log(process_air_sound, "air")

    elif args.mode == "solid":
        print("[main] solid 모드 실행")
        print("[main] solid 로그: logs/solid/solid_YYYY-MM-DD_Day.log")
        _run_with_log(process_solid_sound, "solid")

    else:
        process_both()


if __name__ == "__main__":
    mp.freeze_support()
    main()