#!/usr/bin/env python3
"""
MAXIM の MAX31856 を使って、熱電対で温度計測を行うライブラリです。

Usage:
  max31856.py [-D]

Options:
  -D                : デバッグモードで動作します。
"""

from __future__ import annotations

import logging
import struct
import time
from typing import ClassVar

import spidev  # type: ignore[import-untyped]

from my_lib.sensor.base import SensorBase, SensorValue
from my_lib.sensor.exceptions import SensorCommunicationError


class MAX31856(SensorBase):
    NAME: str = "MAX31856"
    TYPE: str = "SPI"

    REG_CR0: int = 0x00
    REG_CR1: int = 0x01
    REG_LTCBH: int = 0x0C
    REG_SR: int = 0x0F

    AVG_SEL_MAP: ClassVar[dict[str, int]] = {
        "ave1": 0b000,
        "ave2": 0b001,
        "ave4": 0b010,
        "ave8": 0b011,
        "ave16": 0b100,
    }
    TC_TYPE_MAP: ClassVar[dict[str, int]] = {
        "B": 0b0000,
        "E": 0b0001,
        "J": 0b0010,
        "K": 0b0011,
        "N": 0b0100,
        "R": 0b0101,
        "S": 0b0110,
        "T": 0b0111,
    }
    NOISE_FILTER_MAP: ClassVar[dict[str, int]] = {
        "60Hz": 0,
        "50Hz": 1,
    }

    def __init__(self, spi_bus: int = 0, spi_dev: int = 0) -> None:
        super().__init__()

        spi = spidev.SpiDev()
        spi.open(spi_bus, spi_dev)
        spi.max_speed_hz = 1000000
        spi.mode = 1

        self.spi: spidev.SpiDev = spi
        self.init()

    def init(self, avg_sel: str = "ave16", tc_type: str = "T", noise_filter: str = "60Hz") -> None:
        self.avg_sel: str = avg_sel
        self.tc_type: str = tc_type
        self.noise_filter: str = noise_filter

    def close(self) -> None:
        """SPI ハンドルを解放する。"""
        self.spi.close()

    def reg_write(self, reg: int, val: int) -> None:
        self.spi.xfer2([reg | 0x80, val])

    def reg_read(self, reg: int, size: int = 1) -> list[int]:
        return self.spi.xfer2([reg] + ([0x00] * size))[1:]

    def ping(self) -> bool:
        try:
            # NOTE: CR1 レジスタは初期値が 0x03 で、0x00 で使うこともないので、
            # デバイスの存在確認に使う。
            return self.reg_read(self.REG_CR1)[0] != 0x00
        except Exception:
            logging.debug("Failed to detect %s", self.NAME, exc_info=True)
            return False

    def get_value(self) -> float:
        oneshot = 1
        ocfault = 1  # NOTE: オープンサーモカップル検出を有効化

        self.reg_write(
            self.REG_CR1,
            (self.AVG_SEL_MAP[self.avg_sel] << 4) | (self.TC_TYPE_MAP[self.tc_type] << 0),
        )
        self.reg_write(
            self.REG_CR0,
            (oneshot << 6) | (ocfault << 4) | (self.NOISE_FILTER_MAP[self.noise_filter] << 0),
        )

        # NOTE: ave16 + 60Hz フィルタの変換時間は約 700ms
        time.sleep(0.8)

        fault = self.reg_read(self.REG_SR)[0]
        if fault != 0x00:
            raise SensorCommunicationError(f"フォルト検出 (SR=0x{fault:02X})。熱電対の断線等を確認")

        # NOTE: 変換結果は 3 バイト (19bit, 2^-7 ℃/LSB)。符号付き 24bit として読み、
        # 下位 5bit の未使用ビットを除して 2^12 で割る。
        return (struct.unpack(">i", bytes([*self.reg_read(self.REG_LTCBH, 3), 0]))[0] >> 8) / 4096.0

    def get_value_map(self) -> dict[str, SensorValue]:
        value = self.get_value()

        return {"temp": round(value, 2)}


if __name__ == "__main__":
    # TEST Code
    import docopt

    import my_lib.logger

    assert __doc__ is not None  # noqa: S101
    args = docopt.docopt(__doc__)
    debug_mode = args["-D"]

    my_lib.logger.init("test", level=logging.DEBUG if debug_mode else logging.INFO)

    sensor = MAX31856()

    ping = sensor.ping()
    logging.info("PING: %s", ping)
    if ping:
        logging.info("VALUE: %s", sensor.get_value_map())
