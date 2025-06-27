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

import logging
import time

from my_lib.sensor import i2cbus


class ADS1015:
    NAME = "ADS1015"
    TYPE = "I2C"
    DEV_ADDR = 0x4A  # 7bit

    REG_CONFIG = 0x01
    REG_VALUE = 0x00

    REG_CONFIG_FSR_0256 = 5
    REG_CONFIG_FSR_2048 = 2

    REG_CONFIG_MUX_01 = 0
    REG_CONFIG_MUX_0G = 4

    def __init__(self, bus_id=i2cbus.I2CBUS.ARM, dev_addr=DEV_ADDR):  # noqa: D107
        self.bus_id = bus_id
        self.dev_addr = dev_addr
        self.i2cbus = i2cbus(bus_id)

        self.mux = self.REG_CONFIG_MUX_01
        self.pga = self.REG_CONFIG_FSR_0256

    def init(self):
        os = 1
        self.i2cbus.i2c_rdwr(
            self.i2cbus.msg.write(
                self.dev_addr,
                [self.REG_CONFIG, (os << 7) | (self.mux << 4) | (self.pga << 1), 0x03],
            )
        )

    def set_mux(self, mux):
        self.mux = mux

    def set_pga(self, pga):
        self.pga = pga

    def ping(self):
        try:
            read = self.i2cbus.msg.read(self.dev_addr, 2)
            self.i2cbus.i2c_rdwr(self.i2cbus.msg.write(self.dev_addr, [self.REG_CONFIG]), read)

            return bytes(read)[0] != 0
        except Exception:
            return False

    def get_value(self):
        self.init()
        time.sleep(0.1)

        read = self.i2cbus.msg.read(self.dev_addr, 2)
        self.i2cbus.i2c_rdwr(self.i2cbus.msg.write(self.dev_addr, [self.REG_VALUE]), read)

        raw = int.from_bytes(bytes(read), byteorder="big", signed=True)
        if self.pga == self.REG_CONFIG_FSR_0256:
            mvolt = raw * 7.8125 / 1000
        elif self.pga == self.REG_CONFIG_FSR_2048:
            mvolt = raw * 62.5 / 1000

        return [round(mvolt, 3)]

    def get_value_map(self):
        value = self.get_value()

        return {"mvolt": value[0]}


if __name__ == "__main__":
    # TEST Code
    import docopt

    import my_lib.logger
    import my_lib.sensor.ads1015

    args = docopt.docopt(__doc__)
    bus_id = int(args["-b"], 0)
    dev_addr = int(args["-d"], 0)
    debug_mode = args["-D"]

    my_lib.logger.init("test", level=logging.DEBUG if debug_mode else logging.INFO)

    sensor = my_lib.sensor.ads1015(bus_id=bus_id, dev_addr=dev_addr)

    ping = sensor.ping()
    logging.info("PING: %s", ping)
    if ping:
        logging.info("VALUE: %s", sensor.get_value_map())
