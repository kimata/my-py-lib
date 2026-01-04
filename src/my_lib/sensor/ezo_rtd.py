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

import time

from my_lib.sensor.base import I2CSensorBase


class EZO_RTD(I2CSensorBase):
    NAME: str = "EZO-RTD"
    DEV_ADDR: int = 0x66  # 7bit

    def __init__(self, bus_id: int | None = None, dev_addr: int | None = None) -> None:
        from my_lib.sensor import i2cbus

        super().__init__(
            bus_id=bus_id if bus_id is not None else i2cbus.I2CBUS.ARM,
            dev_addr=dev_addr if dev_addr is not None else self.DEV_ADDR,
        )

    def _ping_impl(self) -> bool:
        value = self.exec_command("i")
        return value[1:].decode().split(",")[1] == "RTD"

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
