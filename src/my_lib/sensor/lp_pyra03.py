#!/usr/bin/env python3
"""
LP PYRA03 を使って日射量を計測するライブラリです。

Usage:
  lp_pyra03.py [-b BUS] [-d DEV_ADDR] [-D]

Options:
  -b BUS            : I2C バス番号。[default: 0x01]
  -d DEV_ADDR       : デバイスアドレス(7bit)。 [default: 0x48]
  -D                : デバッグモードで動作します。
"""

# 日射計の電圧は、ADS1115 を使って取得することを想定しています。

from __future__ import annotations

import logging

from my_lib.sensor import i2cbus
from my_lib.sensor.ads1115 import ADS1115


class LP_PYRA03:
    NAME: str = "LP_PYRA03"
    TYPE: str = "I2C"
    SENSITIVITY: float = 6.94  # mV/(kW/m^2)

    def __init__(self, bus_id: int = i2cbus.I2CBUS.ARM, dev_addr: int = ADS1115.DEV_ADDR) -> None:
        self.adc: ADS1115 = ADS1115(bus_id=bus_id, dev_addr=dev_addr)
        self.dev_addr: int = self.adc.dev_addr

    def ping(self) -> bool:
        return self.adc.ping()

    def get_value(self) -> list[float]:
        mvolt = abs(max(self.adc.get_value()[0], 0))

        return [round(1000 * mvolt / self.SENSITIVITY, 2)]

    def get_value_map(self) -> dict[str, float]:
        value = self.get_value()

        return {"solar_rad": value[0]}


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

    sensor = LP_PYRA03(bus_id=bus_id, dev_addr=dev_addr)

    ping = sensor.ping()
    logging.info("PING: %s", ping)
    if ping:
        logging.info("VALUE: %s", sensor.get_value_map())
