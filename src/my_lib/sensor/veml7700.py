#!/usr/bin/env python3
"""
VEML7700 を使って照度 (LUX) を取得するライブラリです。

Usage:
  veml7700.py [-b BUS] [-d DEV_ADDR] [-D]

Options:
  -b BUS            : I2C バス番号。[default: 0x01]
  -d DEV_ADDR       : デバイスアドレス(7bit)。 [default: 0x10]
  -D                : デバッグモードで動作します。
"""

# NOTE: VEML6075 とデバイスアドレス (0x10) が同じため、同一バスでの併用はできない。
# 併用する場合は片方を別バス (i2c_bus: VC) に接続すること。

from __future__ import annotations

import time
from typing import ClassVar

from my_lib.sensor.base import I2CSensorBase


class VEML7700(I2CSensorBase):
    NAME: str = "VEML7700"
    DEV_ADDR: int = 0x10  # 7bit

    REG_ALS_CONF: int = 0x00
    REG_ALS: int = 0x04

    ALS_GAIN: ClassVar[dict[float, int]] = {
        1: 0x0 << 11,
        2: 0x1 << 11,
        0.125: 0x2 << 11,
        0.25: 0x3 << 11,
    }
    ALS_IT: ClassVar[dict[int, int]] = {
        100: 0x0 << 6,
        200: 0x1 << 6,
        400: 0x2 << 6,
        800: 0x3 << 6,
        50: 0x8 << 6,
        25: 0xC << 6,
    }

    ALS_SD_POWER_ON: int = 0x00
    ALS_SD_POWER_OFF: int = 0x01

    def __init__(self, bus_id: int | None = None, dev_addr: int | None = None) -> None:
        from my_lib.sensor import i2cbus

        super().__init__(
            bus_id=bus_id if bus_id is not None else i2cbus.I2CBUS.ARM,
            dev_addr=dev_addr,
        )
        self.gain: float = 0.125
        self.integ: int = 25

    def _write_conf(self, value: int) -> None:
        self.i2cbus.i2c_rdwr(
            self.i2cbus.msg.write(self.dev_addr, [self.REG_ALS_CONF, value & 0xFF, (value >> 8) & 0xFF])
        )

    def enable(self) -> None:
        self._write_conf(self.ALS_GAIN[self.gain] | self.ALS_IT[self.integ] | self.ALS_SD_POWER_ON)

    def disable(self) -> None:
        self._write_conf(self.ALS_GAIN[self.gain] | self.ALS_IT[self.integ] | self.ALS_SD_POWER_OFF)

    def set_integ(self, integ: int) -> None:
        self.integ = integ

    def set_gain(self, gain: float) -> None:
        self.gain = gain

    def wait(self) -> None:
        time.sleep(self.integ / 1000.0 + 0.1)

    def _ping_impl(self) -> bool:
        # NOTE: 読み出しエラーが起こらなければセンサーが接続されていると見なす
        self.i2cbus.read_i2c_block_data(self.dev_addr, self.REG_ALS_CONF, 2)
        return True

    def get_value_impl(self) -> list[float]:
        self.enable()
        self.wait()

        data = self.i2cbus.read_i2c_block_data(self.dev_addr, self.REG_ALS, 2)

        self.disable()

        als: float = int.from_bytes(bytes(data), byteorder="little")
        als *= 0.0036 * (800 / self.integ) * (2 / self.gain)

        if self.gain == 0.125:
            # NOTE:
            # https://www.vishay.com/docs/84367/designingveml6030.pdf
            als = (6.0135e-13 * als**4) - (9.3924e-9 * als**3) + (8.1488e-5 * als**2) + (1.0023e0 * als)

        return [als]

    def get_value(self) -> list[float]:
        # NOTE: まず短い積分時間で測り、暗い場合は積分時間を伸ばして測り直す。
        # 前回の呼び出しで積分時間が変わっていることがあるため、毎回リセットする。
        self.set_integ(25)
        value = self.get_value_impl()

        if value[0] < 1000:
            self.set_integ(100)
            return self.get_value_impl()
        else:
            return value

    def get_value_map(self) -> dict[str, float]:
        value = self.get_value()

        return {"lux": round(value[0], 1)}


if __name__ == "__main__":
    # TEST Code
    import logging

    import docopt

    import my_lib.logger

    assert __doc__ is not None  # noqa: S101
    args = docopt.docopt(__doc__)
    bus_id = int(args["-b"], 0)
    dev_addr = int(args["-d"], 0)
    debug_mode = args["-D"]

    my_lib.logger.init("test", level=logging.DEBUG if debug_mode else logging.INFO)

    sensor = VEML7700(bus_id=bus_id, dev_addr=dev_addr)

    ping = sensor.ping()
    logging.info("PING: %s", ping)
    if ping:
        logging.info("VALUE: %s", sensor.get_value_map())
