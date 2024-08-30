#!/usr/bin/env python3
"""
EZO-pH を使って pH を取得するライブラリです．

Usage:
  ezo_ph.py [-b BUS] [-d DEV_ADDR]

Options:
  -b BUS        : I2C バス番号．[default: 0x01]
  -d DEV_ADDR   : デバイスアドレス(7bit)． [default: 0x64]
"""

import logging
import time

import my_lib.sensor.i2cbus
from my_lib.sensor.i2cbus import I2CBUS


class EZO_PH:
    NAME = "EZO-pH"
    TYPE = "I2C"
    DEV_ADDR = 0x64  # 7bit

    def __init__(self, bus_id=I2CBUS.ARM, dev_addr=DEV_ADDR):  # noqa: D107
        self.bus_id = bus_id
        self.dev_addr = dev_addr
        self.i2cbus = my_lib.sensor.i2cbus(bus_id)

    def ping(self):
        logging.debug("ping to dev:0x%02X, bus:0x%02X", self.dev_addr, self.bus_id)

        try:
            value = self.exec_command("i")

            return value[1:].decode().split(",")[1] == "pH"
        except Exception:
            logging.debug("Failed to detect %s", self.NAME, exc_info=True)
            return False

    def get_value(self):
        value = self.exec_command("R")

        return round(float(value[1:].decode().rstrip("\x00")), 3)

    #     def exec_cal(self, point, value):
    #         value = self.__exec_command(b'R')
    #
    #         return float(value[1:].decode().rstrip('\x00'))

    def exec_command(self, cmd):
        command = list(cmd.encode())

        self.i2cbus.i2c_rdwr(self.i2cbus.msg.write(self.dev_addr, command))

        time.sleep(1)

        read = self.i2cbus.msg.read(self.dev_addr, 10)
        self.i2cbus.i2c_rdwr(read)

        return bytes(read)

    def get_value_map(self):
        value = self.get_value()

        return {"ph": value}


if __name__ == "__main__":
    # TEST Code
    import docopt

    import my_lib.logger
    import my_lib.sensor.ezo_ph

    args = docopt.docopt(__doc__)
    bus_id = int(args["-b"], 0)
    dev_addr = int(args["-d"], 0)

    my_lib.logger.init("sensors.scd4x", level=logging.DEBUG)

    sensor = my_lib.sensor.ezo_ph(bus_id=bus_id, dev_addr=dev_addr)

    ping = sensor.ping()
    logging.info("PING: %s", ping)
    if ping:
        logging.info("VALUE: %s", sensor.get_value_map())
