#!/usr/bin/env python3
"""
LP PYRA03 を使って日射量を計測するライブラリです．

Usage:
  lp_pyra03.py [-b BUS] [-d DEV_ADDR]

Options:
  -b BUS        : I2C バス番号．[default: 0x01]
  -d DEV_ADDR   : デバイスアドレス(7bit)． [default: 0x48]
"""

# 日射計の電圧は，ADS1115 を使って取得することを想定しています．

import logging

import my_lib.sensor.ads1115 as ads1115


class LP_PYRA03:
    NAME = "LP_PYRA03"
    TYPE = "I2C"
    SENSITIVITY = 6.94  # mV/(kW/m^2)

    def __init__(self, bus_id=ads1115.I2CBUS.ARM, dev_addr=ads1115.ADS1115.DEV_ADDR):  # noqa: D107
        self.adc = ads1115.ADS1115(bus_id=bus_id, dev_addr=dev_addr)
        self.dev_addr = self.adc.dev_addr

    def ping(self):
        return self.adc.ping()

    def get_value(self):
        mvolt = self.adc.get_value()[0]

        return [round(1000 * mvolt / self.SENSITIVITY, 2)]

    def get_value_map(self):
        value = self.get_value()

        return {"solar_rad": value[0]}


if __name__ == "__main__":
    # TEST Code
    import docopt
    import my_lib.logger
    import my_lib.sensor.lp_pyra03

    args = docopt.docopt(__doc__)
    bus_id = int(args["-b"], 0)
    dev_addr = int(args["-d"], 0)

    my_lib.logger.init("test", level=logging.DEBUG)

    sensor = my_lib.sensor.lp_pyra03(bus_id=bus_id, dev_addr=dev_addr)

    ping = sensor.ping()
    logging.info("PING: %s", ping)
    if ping:
        logging.info("VALUE: %s", sensor.get_value_map())
