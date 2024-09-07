#!/usr/bin/env python3
"""
Groove 水質測定センサー を使って TDS を取得するライブラリです．

Usage:
  grove_tds.py [-b BUS] [-d DEV_ADDR]

Options:
  -b BUS        : I2C バス番号．[default: 0x01]
  -d DEV_ADDR   : デバイスアドレス(7bit)． [default: 0x4A]
"""

import logging

import my_lib.sensor.ads1015
from my_lib.sensor.i2cbus import I2CBUS


class GROVE_TDS:  # noqa: N801
    NAME = "GROVE-TDS"
    TYPE = "I2C"
    DEV_ADDR = 0x4A  # 7bit

    def __init__(self, bus_id=I2CBUS.ARM, dev_addr=DEV_ADDR):  # noqa: D107
        self.bus_id = bus_id
        self.dev_addr = dev_addr
        self.adc = my_lib.sensor.ads1015(bus_id, dev_addr)

        self.adc.set_mux(self.adc.REG_CONFIG_MUX_0G)
        self.adc.set_pga(self.adc.REG_CONFIG_FSR_2048)

    def ping(self):
        return self.adc.ping()

    def get_value(self, temp=26.0):
        volt = self.adc.get_value()[0] / 1000.0
        tds = (133.42 * volt * volt * volt - 255.86 * volt * volt + 857.39 * volt) * 0.5
        tds /= 1 + 0.018 * (temp - 25)  # 0.018 は実測データから算出

        return [round(tds, 3)]

    def get_value_map(self, temp=25.0):
        value = self.get_value(temp)

        return {"tds": value[0]}


if __name__ == "__main__":
    # TEST Code
    import docopt

    import my_lib.logger

    args = docopt.docopt(__doc__)
    bus_id = int(args["-b"], 0)
    dev_addr = int(args["-d"], 0)

    my_lib.logger.init("test", level=logging.DEBUG)

    sensor = my_lib.sensor.grove_tds(bus_id=bus_id, dev_addr=dev_addr)

    ping = sensor.ping()
    logging.info("PING: %s", ping)
    if ping:
        logging.info("VALUE: %s", sensor.get_value_map())