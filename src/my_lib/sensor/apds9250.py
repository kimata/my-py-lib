#!/usr/bin/env python3
"""
APDS-9250 を使って照度を取得するライブラリです。

Usage:
  apds9250.py [-b BUS] [-d DEV_ADDR] [-D]

Options:
  -b BUS            : I2C バス番号。[default: 0x01]
  -d DEV_ADDR       : デバイスアドレス(7bit)。 [default: 0x52]
  -D                : デバッグモードで動作します。
"""

from __future__ import annotations

from my_lib.sensor.base import I2CSensorBase


class APDS9250(I2CSensorBase):
    NAME: str = "APDS9250"
    DEV_ADDR: int = 0x52  # 7bit

    def __init__(self, bus_id: int | None = None, dev_addr: int | None = None) -> None:  # noqa: D107
        from my_lib.sensor import i2cbus

        super().__init__(
            bus_id=bus_id if bus_id is not None else i2cbus.I2CBUS.ARM,
            dev_addr=dev_addr if dev_addr is not None else self.DEV_ADDR,
        )
        self.is_init: bool = False

    def _ping_impl(self) -> bool:
        data = self.i2cbus.read_byte_data(self.dev_addr, 0x06)
        return (data & 0xF0) == 0xB0

    def get_value(self) -> float:
        # Resolution = 20bit/400ms, Rate = 1000ms
        self.i2cbus.write_byte_data(self.dev_addr, 0x04, 0x05)
        # Gain = 1
        self.i2cbus.write_byte_data(self.dev_addr, 0x05, 0x01)
        # Sensor = active
        self.i2cbus.write_byte_data(self.dev_addr, 0x00, 0x02)

        data = self.i2cbus.read_i2c_block_data(self.dev_addr, 0x0A, 6)

        ir = int.from_bytes(bytes(data[0:3]) + b"\x00", byteorder="little")
        als = int.from_bytes(bytes(data[3:6]) + b"\x00", byteorder="little")

        if als > ir:
            return als * 46.0 / 400
        else:
            return als * 35.0 / 400

    def get_value_map(self) -> dict[str, float]:
        value = self.get_value()

        return {"lux": value}


if __name__ == "__main__":
    # TEST Code
    import logging

    import docopt

    import my_lib.logger

    assert __doc__ is not None
    args = docopt.docopt(__doc__)
    bus_id = int(args["-b"], 0)
    dev_addr = int(args["-d"], 0)
    debug_mode = args["-D"]

    my_lib.logger.init("test", level=logging.DEBUG if debug_mode else logging.INFO)

    sensor = APDS9250(bus_id=bus_id, dev_addr=dev_addr)

    ping = sensor.ping()
    logging.info("PING: %s", ping)
    if ping:
        logging.info("VALUE: %s", sensor.get_value_map())
