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

import logging
import time

from my_lib.sensor import i2cbus


class EZO_RTD:  # noqa: N801
    NAME: str = "EZO-RTD"
    TYPE: str = "I2C"
    DEV_ADDR: int = 0x66  # 7bit

    def __init__(self, bus_id: int = i2cbus.I2CBUS.ARM, dev_addr: int = DEV_ADDR) -> None:  # noqa: D107
        self.bus_id: int = bus_id
        self.dev_addr: int = dev_addr
        self.i2cbus: i2cbus.I2CBUS = i2cbus.I2CBUS(bus_id)

    def ping(self) -> bool:
        logging.debug("ping to dev:0x%02X, bus:0x%02X", self.dev_addr, self.bus_id)

        try:
            value = self.exec_command("i")

            return value[1:].decode().split(",")[1] == "RTD"
        except Exception:
            logging.debug("Failed to detect %s", self.NAME, exc_info=True)
            return False

    def get_value(self) -> float:
        value = self.exec_command("R")

        return float(value[1:].decode().rstrip("\x00"))

    def exec_command(self, cmd: str) -> bytes:
        command = list(cmd.encode())

        self.i2cbus.i2c_rdwr(self.i2cbus.msg.write(self.dev_addr, command))

        time.sleep(1)

        read = self.i2cbus.msg.read(self.dev_addr, 10)
        self.i2cbus.i2c_rdwr(read)

        return bytes(read)

    def get_value_map(self) -> dict[str, float]:
        value = self.get_value()

        return {"temp": value}


if __name__ == "__main__":
    # TEST Code
    import docopt

    import my_lib.logger

    args = docopt.docopt(__doc__)
    bus_id = int(args["-b"], 0)
    dev_addr = int(args["-d"], 0)
    debug_mode = args["-D"]

    my_lib.logger.init("test", level=logging.DEBUG if debug_mode else logging.INFO)

    sensor = my_lib.sensor.ezo_rtd(bus_id=bus_id, dev_addr=dev_addr)

    ping = sensor.ping()
    logging.info("PING: %s", ping)
    if ping:
        logging.info("VALUE: %s", sensor.get_value_map())
