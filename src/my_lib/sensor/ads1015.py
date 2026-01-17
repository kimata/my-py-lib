#!/usr/bin/env python3
"""
ADS-1015 を使って電圧を計測するライブラリです。

Usage:
  ads1015.py [-b BUS] [-d DEV_ADDR] [-D]

Options:
  -b BUS            : I2C バス番号。[default: 0x01]
  -d DEV_ADDR       : デバイスアドレス(7bit)。 [default: 0x4A]
  -D                : デバッグモードで動作します。
"""

from __future__ import annotations

import logging

from my_lib.sensor import i2cbus
from my_lib.sensor.ads_base import ADSBase


class ADS1015(ADSBase):
    """ADS1015 12bit ADC センサー"""

    NAME: str = "ADS1015"
    DEV_ADDR: int = 0x4A  # 7bit

    def __init__(self, bus_id: int = i2cbus.I2CBUS.ARM, dev_addr: int = 0x4A) -> None:
        super().__init__(bus_id, dev_addr)


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

    sensor = ADS1015(bus_id=bus_id, dev_addr=dev_addr)

    ping = sensor.ping()
    logging.info("PING: %s", ping)
    if ping:
        logging.info("VALUE: %s", sensor.get_value_map())
