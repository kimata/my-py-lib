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
import struct
import time

import my_lib.sensor.i2cbus
from my_lib.sensor.i2cbus import I2CBUS as I2CBUS


class EZO_PH:
    NAME = "EZO-pH"
    TYPE = "I2C"
    DEV_ADDR = 0x64  # 7bit

    RAM_CO2 = 0x08
    RAM_FIRM = 0x62

    WRITE_RAM = 0x1 << 4
    READ_RAM = 0x2 << 4
    WRITE_EE = 0x3 << 4
    READ_EE = 0x4 << 4

    RETRY_COUNT = 5

    def __init__(self, bus_id=I2CBUS.ARM, dev_addr=DEV_ADDR):  # noqa: D107
        self.bus_id = bus_id
        self.dev_addr = dev_addr
        self.i2cbus = my_lib.sensor.i2cbus(bus_id)

    def ping(self):
        try:
            logging.info("DEV:%02x", self.dev_addr)
            value = self.exec_command("i")

            return value[1:].decode().split(",")[1] == "pH"
        except Exception:
            logging.exeception("Failed to detect %s", self.NAME)
            return False

    def get_value(self):
        value = self.exec_command("R")

        return round(float(value[1:].decode().rstrip("\x00")), 3)

    #     def exec_cal(self, point, value):
    #         value = self.__exec_command(b'R')
    #
    #         return float(value[1:].decode().rstrip('\x00'))

    def exec_command(self, cmd):
        command = self.__compose_command(cmd.encode())

        logging.info(command)

        self.i2cbus.i2c_rdwr(self.i2cbus.msg.write(self.dev_addr, command))

        time.sleep(1)

        read = self.i2cbus.msg.read(self.dev_addr, 10)
        self.i2cbus.i2c_rdwr(read)

        return bytes(read)

    def __compose_command(self, text):
        return list(struct.unpack("B" * len(text), text))

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
