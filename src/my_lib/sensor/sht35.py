#!/usr/bin/env python3
"""
SHT-35 を使って温度や湿度を取得するライブラリです．

Usage:
  sht35.py [-b BUS] [-d DEV_ADDR]

Options:
  -b BUS        : I2C バス番号．[default: 0x01]
  -d DEV_ADDR   : デバイスアドレス(7bit)． [default: 0x44]
"""

# 作成時に使用したのは，Tindie の
# 「SHT35-D (Digital) Humidity & Temperature Sensor」．
# https://www.tindie.com/products/closedcube/sht35-d-digital-humidity-temperature-sensor/

import time
import logging
import my_lib.sensor.i2cbus

class SHT35:
    NAME = "SHT-35"
    DEV_ADDR = 0x44  # 7bit
    RASP_I2C_BUS = 0x1  # Raspberry Pi の I2C のバス番号

    def __init__(self, dev_addr=DEV_ADDR, bus_id=RASP_I2C_BUS):
        self.bus_id = bus_id
        self.dev_addr = dev_addr
        self.i2cbus = my_lib.sensor.i2cbus(bus_id)
        self.is_init = False

    def init(self):
        # periodic, 1mps, repeatability high
        self.i2cbus.write_byte_data(self.dev_addr, 0x21, 0x30)
        self.is_init = True
        time.sleep(0.01)

    def crc(self, data):
        crc = 0xFF
        for s in data:
            crc ^= s
            for i in range(8):
                if crc & 0x80:
                    crc <<= 1
                    crc ^= 0x131
                else:
                    crc <<= 1
        return crc

    def ping(self):
        try:
            logging.debug("ping to dev:0x%02X, bus:0x%02X", self.dev_addr, self.bus_id)
            self.i2cbus.write_byte_data(self.dev_addr, 0xF3, 0x2D)
            data = self.i2cbus.read_i2c_block_data(self.dev_addr, 0x00, 3)

            return self.crc(data[0:2]) == data[2]
        except Exception as e:
            logging.debug("Failed to detect %s", self.NAME, exc_info=True)
            return False

    def get_value(self):
        if not self.is_init:
            self.init()

        self.i2cbus.write_byte_data(self.dev_addr, 0xE0, 0x00)

        data = self.i2cbus.read_i2c_block_data(self.dev_addr, 0x00, 6)

        if (self.crc(data[0:2]) != data[2]) or (self.crc(data[3:5]) != data[5]):
            raise IOError("ERROR: CRC unmatch.")

        temp = -45 + (175 * int.from_bytes(data[0:2], byteorder="big")) / float(
            2 ** 16 - 1
        )
        humi = 100 * int.from_bytes(data[3:5], byteorder="big") / float(2 ** 16 - 1)

        return [round(temp, 2), round(humi, 2)]

    def get_value_map(self):
        value = self.get_value()

        return {"temp": value[0], "humi": value[1]}


if __name__ == "__main__":
    # TEST Code
    from docopt import docopt
    import pathlib

    import my_lib.logger
    import my_lib.sensor.sht35
    
    args = docopt(__doc__)
    bus_id = int(args["-b"], 0)
    dev_addr = int(args["-d"], 0)

    my_lib.logger.init("sensors.sht35", level=logging.DEBUG)

    sensor = my_lib.sensor.sht35(bus_id=bus_id, dev_addr=dev_addr)

    ping = sensor.ping()
    logging.info("PING: {ping}".format(ping=ping))
    if ping:
        logging.info("VALUE: {value}".format(value=sensor.get_value_map()))
