#!/usr/bin/env python3
"""
Groove 水質測定センサー を使って TDS を取得するライブラリです。

Usage:
  grove_tds.py [-b BUS] [-d DEV_ADDR] [-D]

Options:
  -b BUS            : I2C バス番号。[default: 0x01]
  -d DEV_ADDR       : デバイスアドレス(7bit)。 [default: 0x4A]
  -D                : デバッグモードで動作します。
"""

from __future__ import annotations

import logging

from my_lib.sensor import i2cbus
from my_lib.sensor.ads1115 import ADS1115


class GROVE_TDS:
    NAME: str = "GROVE-TDS"
    TYPE: str = "I2C"

    def __init__(self, bus_id: int = i2cbus.I2CBUS.ARM, dev_addr: int = ADS1115.DEV_ADDR) -> None:
        self.bus_id: int = bus_id
        self.dev_addr: int = dev_addr
        self.adc: ADS1115 = ADS1115(bus_id=bus_id, dev_addr=dev_addr)

        self.adc.set_mux(self.adc.REG_CONFIG_MUX_0G)
        self.adc.set_pga(self.adc.REG_CONFIG_FSR_2048)

    def ping(self) -> bool:
        return self.adc.ping()

    def get_value(self, temp: float = 26.0) -> list[float]:
        volt = self.adc.get_value()[0] / 1000.0
        tds = (133.42 * volt * volt * volt - 255.86 * volt * volt + 857.39 * volt) * 0.5
        tds /= 1 + 0.018 * (temp - 25)  # 0.018 は実測データから算出

        return [round(tds, 3)]

    def get_value_map(self, temp: float = 25.0) -> dict[str, float]:
        value = self.get_value(temp)

        return {"tds": value[0]}


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

    sensor = GROVE_TDS(bus_id=bus_id, dev_addr=dev_addr)

    ping = sensor.ping()
    logging.info("PING: %s", ping)
    if ping:
        logging.info("VALUE: %s", sensor.get_value_map())
