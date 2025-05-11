#!/usr/bin/env python3
"""
SHT-35 を使って温度や湿度を取得するライブラリです。

Usage:
  sht35.py [-b BUS] [-d DEV_ADDR] [-D]

Options:
  -b BUS            : I2C バス番号。[default: 0x01]
  -d DEV_ADDR       : デバイスアドレス(7bit)。 [default: 0x44]
  -D                : デバッグモードで動作します。
"""

# 作成時に使用したのは，Tindie の
# 「SHT35-D (Digital) Humidity & Temperature Sensor」。
# https://www.tindie.com/products/closedcube/sht35-d-digital-humidity-temperature-sensor/

import logging
import time

import my_lib.sensor.i2cbus
from my_lib.sensor.i2cbus import I2CBUS


class SHT35:
    NAME = "SHT-35"
    TYPE = "I2C"
    DEV_ADDR = 0x44  # 7bit

    def __init__(self, bus_id=I2CBUS.ARM, dev_addr=DEV_ADDR):  # noqa: D107
        self.bus_id = bus_id
        self.dev_addr = dev_addr
        self.i2cbus = my_lib.sensor.i2cbus(bus_id)

    def crc(self, data):
        crc = 0xFF
        for s in data:
            crc ^= s
            for _ in range(8):
                if crc & 0x80:
                    crc <<= 1
                    crc ^= 0x131
                else:
                    crc <<= 1
        return crc

    def ping(self):
        logging.debug("ping to dev:0x%02X, bus:0x%02X", self.dev_addr, self.bus_id)

        try:
            self.i2cbus.write_byte_data(self.dev_addr, 0xF3, 0x2D)
            data = self.i2cbus.read_i2c_block_data(self.dev_addr, 0x00, 3)

            return self.crc(data[0:2]) == data[2]
        except Exception:
            logging.debug("Failed to detect %s", self.NAME, exc_info=True)
            return False

    def get_value(self):
        self.i2cbus.write_byte_data(self.dev_addr, 0x24, 0x16)

        time.sleep(0.1)

        read = self.i2cbus.msg.read(self.dev_addr, 6)
        self.i2cbus.i2c_rdwr(read)

        data = bytes(read)

        if (self.crc(data[0:2]) != data[2]) or (self.crc(data[3:5]) != data[5]):
            raise OSError("ERROR: CRC unmatch.")  # noqa: EM101, TRY003,

        temp = -45 + (175 * int.from_bytes(data[0:2], byteorder="big")) / float(2**16 - 1)
        humi = 100 * int.from_bytes(data[3:5], byteorder="big") / float(2**16 - 1)

        return [round(temp, 2), round(humi, 2)]

    def get_value_map(self):
        value = self.get_value()

        return {"temp": value[0], "humi": value[1]}


if __name__ == "__main__":
    # TEST Code
    import docopt
    import my_lib.logger

    args = docopt.docopt(__doc__)
    bus_id = int(args["-b"], 0)
    dev_addr = int(args["-d"], 0)
    debug_mode = args["-D"]

    my_lib.logger.init("test", level=logging.DEBUG if debug_mode else logging.INFO)

    sensor = my_lib.sensor.sht35(bus_id=bus_id, dev_addr=dev_addr)

    ping = sensor.ping()
    logging.info("PING: %s", ping)
    if ping:
        logging.info("VALUE: %s", sensor.get_value_map())
