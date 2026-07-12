#!/usr/bin/env python3
"""
RG-15 を使って雨量を計測するライブラリです。

Usage:
  rg_15.py [-d DEV] [-D]

Options:
  -d DEV            : シリアルポート。 [default: /dev/ttyAMA0]
  -D                : デバッグモードで動作します。
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass
from typing import Any

import serial

from my_lib.sensor.base import UARTSensorBase


@dataclass
class RainEvent:
    """降雨イベントの状態を管理するクラス

    状態管理のため frozen=False（状態更新が必要）
    """

    fall_sum: float = 0.0
    fall_time_last: float | None = None
    fall_time_start: float | None = None
    fall_stop: bool = True
    fall_start: bool = False


class RG_15(UARTSensorBase):
    NAME: str = "RG_15"
    DEV: str = "/dev/ttyAMA0"
    BAUDRATE: int = 9600

    RAIN_START_INTERVAL_SEC: int = 30
    RAIN_START_ACC_SUM: float = 0.04
    RAIN_STOP_INTERVAL_SEC: int = 120

    def __init__(self, dev: str = DEV, param: dict[str, Any] | None = None) -> None:
        """RG-15 ドライバを初期化する。

        Args:
            dev: シリアルデバイスファイル
            param: UART ドライバ共通シグネチャのための追加パラメータ (RG-15 では未使用)
        """
        super().__init__()
        self.dev: str = dev
        self.ser: serial.Serial = serial.Serial(self.dev, self.BAUDRATE, timeout=2)
        self.sum_by_minute: dict[int, float] = {}
        self.event: RainEvent = RainEvent()

    def close(self) -> None:
        """シリアルポートを閉じる。"""
        self.ser.close()

    def update_stat(self, data: dict[str, float]) -> list[float | bool]:
        minute = int(time.time() / 60)

        if data["acc"] == 0:
            if (not self.event.fall_stop) and (
                self.event.fall_time_last is not None
                and (time.time() - self.event.fall_time_last) > self.RAIN_STOP_INTERVAL_SEC
            ):
                self.ser.write("O\r\n".encode(encoding="utf-8"))  # noqa: UP012
                self.ser.flush()

                self.event.fall_stop = True
                self.event.fall_start = False
                self.event.fall_time_start = None
                self.event.fall_sum = 0.0
        else:
            self.event.fall_time_last = time.time()
            self.event.fall_sum += data["acc"]

            if minute in self.sum_by_minute:
                self.sum_by_minute[minute] += data["acc"]
            else:
                self.sum_by_minute[minute] = data["acc"]

            if self.event.fall_time_start is None:
                self.event.fall_time_start = time.time()

            if (
                (not self.event.fall_start)
                and self.event.fall_time_start is not None
                and ((time.time() - self.event.fall_time_start) > self.RAIN_START_INTERVAL_SEC)
                and (self.event.fall_sum >= self.RAIN_START_ACC_SUM)
            ):
                self.event.fall_start = True
                self.event.fall_stop = False

        # NOTE: 直前の1分間降水量を返す
        rain = self.sum_by_minute.get(minute - 1, 0.0)

        # NOTE: 参照するのは直前 1 分だけなので、それより古い集計は捨てる (無限成長防止)
        for old_minute in [m for m in self.sum_by_minute if m < minute - 1]:
            del self.sum_by_minute[old_minute]

        return [rain, self.event.fall_start]

    def ping(self) -> bool:
        try:
            self.ser.reset_input_buffer()
            self.ser.write("P\r\n".encode(encoding="utf-8"))  # noqa: UP012
            self.ser.flush()

            res = self.ser.read(1).decode(encoding="utf-8")

            # NOTE: 応答の残りバイトが次回の read に混入しないように捨てる
            self.ser.reset_input_buffer()

            return res == "p"
        except Exception:
            return False

    def get_value(self) -> list[float | bool]:
        self.ser.reset_input_buffer()
        self.ser.write("R\r\n".encode(encoding="utf-8"))  # noqa: UP012
        self.ser.flush()

        # NOTE: 応答は 1 行なので行末まで読む (固定長 read だと毎回タイムアウトまで待つ)
        res = self.ser.read_until(expected=b"\n", size=200).decode(encoding="utf-8").strip()

        logging.debug(res)

        data: dict[str, float] = {
            label.lower(): float(value)
            for label, value in re.findall(r"(Acc|EventAcc|TotalAcc|RInt)\s+(\d+\.\d+)", res)
        }

        logging.info(data)

        return self.update_stat(data)

    def get_value_map(self) -> dict[str, float | bool]:
        value = self.get_value()

        return {"rain": value[0], "raining": value[1]}


if __name__ == "__main__":
    # TEST Code
    import docopt

    import my_lib.logger

    assert __doc__ is not None  # noqa: S101
    args = docopt.docopt(__doc__)
    dev = args["-d"]
    debug_mode = args["-D"]

    my_lib.logger.init("test", level=logging.DEBUG if debug_mode else logging.INFO)

    sensor = RG_15(dev=dev)

    ping = sensor.ping()
    logging.info("PING: %s", ping)
    if ping:
        while True:
            logging.info("VALUE: %s", sensor.get_value_map())
            time.sleep(5)
