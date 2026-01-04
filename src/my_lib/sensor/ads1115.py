#!/usr/bin/env python3
"""
ADS-1015 を使って電圧を計測するライブラリです。

Usage:
  ads1115.py [-b BUS] [-d DEV_ADDR] [-D]

Options:
  -b BUS            : I2C バス番号。[default: 0x01]
  -d DEV_ADDR       : デバイスアドレス(7bit)。 [default: 0x48]
  -D                : デバッグモードで動作します。
"""

from __future__ import annotations

import logging
import time

from my_lib.sensor import i2cbus


class ADS1115:
    NAME: str = "ADS1115"
    TYPE: str = "I2C"
    DEV_ADDR: int = 0x48  # 7bit

    REG_CONFIG: int = 0x01
    REG_VALUE: int = 0x00

    REG_CONFIG_FSR_0256: int = 5
    REG_CONFIG_FSR_2048: int = 2

    REG_CONFIG_MUX_01: int = 0
    REG_CONFIG_MUX_0G: int = 4

    def __init__(self, bus_id: int = i2cbus.I2CBUS.ARM, dev_addr: int = DEV_ADDR) -> None:
        self.bus_id: int = bus_id
        self.dev_addr: int = dev_addr
        self.i2cbus: i2cbus.I2CBUS = i2cbus.I2CBUS(bus_id)

        self.mux: int = self.REG_CONFIG_MUX_01
        self.pga: int = self.REG_CONFIG_FSR_0256

    def init(self) -> None:
        os = 1
        self.i2cbus.i2c_rdwr(
            self.i2cbus.msg.write(
                self.dev_addr,
                [self.REG_CONFIG, (os << 7) | (self.mux << 4) | (self.pga << 1), 0x03],
            )
        )

    def set_mux(self, mux: int) -> None:
        self.mux = mux

    def set_pga(self, pga: int) -> None:
        self.pga = pga

    def ping(self) -> bool:
        try:
            read = self.i2cbus.msg.read(self.dev_addr, 2)
            self.i2cbus.i2c_rdwr(self.i2cbus.msg.write(self.dev_addr, [self.REG_CONFIG]), read)

            return bytes(read)[0] != 0
        except Exception:
            return False

    def get_value(self) -> list[float]:
        self.init()
        time.sleep(0.1)

        read = self.i2cbus.msg.read(self.dev_addr, 2)
        self.i2cbus.i2c_rdwr(self.i2cbus.msg.write(self.dev_addr, [self.REG_VALUE]), read)

        raw = int.from_bytes(bytes(read), byteorder="big", signed=True)
        if self.pga == self.REG_CONFIG_FSR_0256:
            mvolt = raw * 7.8125 / 1000
        elif self.pga == self.REG_CONFIG_FSR_2048:
            mvolt = raw * 62.5 / 1000
        else:
            raise ValueError(f"Unsupported PGA value: {self.pga}")

        return [round(mvolt, 3)]

    def get_value_map(self) -> dict[str, float]:
        value = self.get_value()

        return {"mvolt": value[0]}


if __name__ == "__main__":
    # TEST Code
    import docopt

    import my_lib.logger

    assert __doc__ is not None  # noqa: S101
    args = docopt.docopt(__doc__)
    bus_id = int(args["-b"], 0)
    dev_addr = int(args["-d"], 0)
    debug_mode = args["-D"]

    my_lib.logger.init("test", level=logging.DEBUG if debug_mode else logging.INFO)

    sensor = ADS1115(bus_id=bus_id, dev_addr=dev_addr)

    ping = sensor.ping()
    logging.info("PING: %s", ping)
    if ping:
        logging.info("VALUE: %s", sensor.get_value_map())
