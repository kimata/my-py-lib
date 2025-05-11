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

import logging

import my_lib.sensor.i2cbus
from my_lib.sensor.i2cbus import I2CBUS


class APDS9250:
    NAME = "APDS9250"
    TYPE = "I2C"
    DEV_ADDR = 0x52  # 7bit

    def __init__(self, bus_id=I2CBUS.ARM, dev_addr=DEV_ADDR):  # noqa: D107
        self.bus_id = bus_id
        self.dev_addr = dev_addr
        self.i2cbus = my_lib.sensor.i2cbus(bus_id)
        self.is_init = False

    def ping(self):
        logging.debug("ping to dev:0x%02X, bus:0x%02X", self.dev_addr, self.bus_id)

        try:
            data = self.i2cbus.read_byte_data(self.dev_addr, 0x06)
            return (data & 0xF0) == 0xB0
        except Exception:
            logging.debug("Failed to detect %s", self.NAME, exc_info=True)
            return False

    def get_value(self):
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

    def get_value_map(self):
        value = self.get_value()

        return {"lux": value}


if __name__ == "__main__":
    # TEST Code
    import docopt
    import my_lib.logger
    import my_lib.sensor.scd4x

    args = docopt.docopt(__doc__)
    bus_id = int(args["-b"], 0)
    dev_addr = int(args["-d"], 0)
    debug_mode = args["-D"]

    my_lib.logger.init("test", level=logging.DEBUG if debug_mode else logging.INFO)

    sensor = my_lib.sensor.apds9250(bus_id=bus_id, dev_addr=dev_addr)

    ping = sensor.ping()
    logging.info("PING: %s", ping)
    if ping:
        logging.info("VALUE: %s", sensor.get_value_map())
