#!/usr/bin/env python3
"""
VEML6075 を使って紫外線 (UVA/UVB/UV インデックス) を計測するライブラリです。

Usage:
  veml6075.py [-b BUS] [-d DEV_ADDR] [-D]

Options:
  -b BUS            : I2C バス番号。[default: 0x01]
  -d DEV_ADDR       : デバイスアドレス(7bit)。 [default: 0x10]
  -D                : デバッグモードで動作します。
"""

# NOTE: VEML7700 とデバイスアドレス (0x10) が同じため、同一バスでの併用はできない。
# 併用する場合は片方を別バス (i2c_bus: VC) に接続すること。

from __future__ import annotations

import time

from my_lib.sensor.base import I2CSensorBase


class VEML6075(I2CSensorBase):
    NAME: str = "VEML6075"
    DEV_ADDR: int = 0x10  # 7bit

    REG_UV_CONF: int = 0x00
    REG_UVA: int = 0x07
    REG_UVB: int = 0x09
    REG_UVCOMP1: int = 0x0A
    REG_UVCOMP2: int = 0x0B
    REG_DEVID: int = 0x0C

    DEVICE_ID: int = 0x26

    CONF_IT_50MS: int = 0 << 4
    CONF_IT_100MS: int = 1 << 4

    CONF_AF_ENABLE: int = 1 << 1

    CONF_TRIG_ONE: int = 1 << 2

    CONF_SD_POWERON: int = 0 << 0
    CONF_SD_SHUTDOWN: int = 1 << 0

    # designingveml6075.pdf
    # For responsivity without a diffusor and IT = 100 ms:
    # UVA sensing resolution of 0.01 UVI = 9 counts
    # UVB sensing resolution of 0.01 UVI = 8 counts
    UVA_RESP_100MS: float = 0.01 / 9
    UVB_RESP_100MS: float = 0.01 / 8
    # From SparkFun_VEML6075_Arduino_Library.cpp
    UVA_RESP_50MS: float = (0.01 / 9) / 0.5016286645
    UVB_RESP_50MS: float = (0.01 / 8) / 0.5016286645

    # UV 補正係数 (designingveml6075.pdf, オープンエア)
    UVA_A_COEF: float = 2.22
    UVA_B_COEF: float = 1.33
    UVB_C_COEF: float = 2.95
    UVB_D_COEF: float = 1.75

    def __init__(self, bus_id: int | None = None, dev_addr: int | None = None) -> None:
        from my_lib.sensor import i2cbus

        super().__init__(
            bus_id=bus_id if bus_id is not None else i2cbus.I2CBUS.ARM,
            dev_addr=dev_addr,
        )
        self.it: int = self.CONF_IT_50MS

    def _write_conf(self, value: int) -> None:
        self.i2cbus.i2c_rdwr(self.i2cbus.msg.write(self.dev_addr, [self.REG_UV_CONF, value & 0xFF, 0x00]))

    def enable(self) -> None:
        self._write_conf(self.it | self.CONF_TRIG_ONE | self.CONF_AF_ENABLE | self.CONF_SD_POWERON)
        # NOTE: アクティブフォース (単発トリガ) の変換完了を待つ
        time.sleep(1.1)

    def disable(self) -> None:
        self._write_conf(self.it | self.CONF_AF_ENABLE | self.CONF_SD_SHUTDOWN)

    def _ping_impl(self) -> bool:
        data = self.i2cbus.read_i2c_block_data(self.dev_addr, self.REG_DEVID, 2)
        return int.from_bytes(bytes(data), byteorder="little") == self.DEVICE_ID

    def _read_word(self, reg: int) -> int:
        data = self.i2cbus.read_i2c_block_data(self.dev_addr, reg, 2)
        return int.from_bytes(bytes(data), byteorder="little")

    def get_value(self) -> list[float]:
        self.enable()

        uva = self._read_word(self.REG_UVA)
        uvb = self._read_word(self.REG_UVB)
        uvcomp1 = self._read_word(self.REG_UVCOMP1)
        uvcomp2 = self._read_word(self.REG_UVCOMP2)

        self.disable()

        uva_calc = uva - (self.UVA_A_COEF * uvcomp1) - (self.UVA_B_COEF * uvcomp2)
        uvb_calc = uvb - (self.UVB_C_COEF * uvcomp1) - (self.UVB_D_COEF * uvcomp2)

        if self.it == self.CONF_IT_50MS:
            uvi = ((uva_calc * self.UVA_RESP_50MS) + (uvb_calc * self.UVB_RESP_50MS)) / 2
        else:
            uvi = ((uva_calc * self.UVA_RESP_100MS) + (uvb_calc * self.UVB_RESP_100MS)) / 2

        return [round(uva_calc, 2), round(uvb_calc, 2), round(uvi, 2)]

    def get_value_map(self) -> dict[str, float]:
        value = self.get_value()

        return {
            "uva": value[0],
            "uvb": value[1],
            "uvi": value[2],
        }


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

    sensor = VEML6075(bus_id=bus_id, dev_addr=dev_addr)

    ping = sensor.ping()
    logging.info("PING: %s", ping)
    if ping:
        logging.info("VALUE: %s", sensor.get_value_map())
