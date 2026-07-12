#!/usr/bin/env python3
"""
EZO-RTD を使って水温を取得するライブラリです。

Usage:
  ezo_rtd.py [-b BUS] [-d DEV_ADDR] [-D]

Options:
  -b BUS        : I2C バス番号。[default: 0x01]
  -d DEV_ADDR   : デバイスアドレス(7bit)。 [default: 0x66]
  -D                : デバッグモードで動作します。
"""

from __future__ import annotations

from my_lib.sensor.ezo_base import EZOBase


class EZO_RTD(EZOBase):
    NAME: str = "EZO-RTD"
    DEV_ADDR: int = 0x66  # 7bit
    DEVICE_ID: str = "RTD"

    def get_value(self) -> float:
        return round(float(self.exec_command("R")), 3)

    def get_value_map(self) -> dict[str, float]:
        value = self.get_value()

        return {"temp": value}


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

    sensor = EZO_RTD(bus_id=bus_id, dev_addr=dev_addr)

    ping = sensor.ping()
    logging.info("PING: %s", ping)
    if ping:
        logging.info("VALUE: %s", sensor.get_value_map())
