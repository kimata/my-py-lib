#!/usr/bin/env python3
"""
SCD4x を使って CO2 濃度を取得するライブラリです．

Usage:
  scd4x.py [-b BUS] [-d DEV_ADDR]

Options:
  -b BUS        : I2C バス番号．[default: 0x01]
  -d DEV_ADDR   : デバイスアドレス(7bit)． [default: 0x62]
"""

# 作成時に使用したのは，Sensirion の SEK SCD41．
# https://www.sensirion.com/en/environmental-sensors/evaluation-kit-sek-environmental-sensing/evaluation-kit-sek-scd41/
# 明示的に start_periodic_measurement を呼ばなくても済むように少し工夫しています．

import logging
import time

import my_lib.sensor.i2cbus
from my_lib.sensor.i2cbus import I2CBUS


class SCD4X:
    NAME = "SCD4X"
    TYPE = "I2C"
    DEV_ADDR = 0x62  # 7bit

    def __init__(self, bus_id=I2CBUS.ARM, dev_addr=DEV_ADDR):  # noqa: D107
        self.bus_id = bus_id
        self.dev_addr = dev_addr
        self.i2cbus = my_lib.sensor.i2cbus(bus_id)
        self.is_init = False

    def ping(self):
        logging.debug("ping to dev:0x%02X, bus:0x%02X", self.dev_addr, self.bus_id)
        try:
            self.__get_data_ready()

            return True
        except Exception:
            logging.debug("Failed to detect %s", self.NAME, exc_info=True)
            return False

    def __reset(self):
        # sto_periodic_measurement
        self.i2cbus.write_byte_data(self.dev_addr, 0x3F, 0x86)
        time.sleep(0.5)
        # reinit
        self.i2cbus.write_byte_data(self.dev_addr, 0x36, 0x46)
        time.sleep(0.02)

    def __crc(self, msg):
        poly = 0x31
        crc = 0xFF

        for data in bytearray(msg):
            crc ^= data
            for _ in range(8):
                if crc & 0x80:
                    crc = (crc << 1) ^ poly
                else:
                    crc <<= 1
            crc &= 0xFF

        return crc

    def __decode_response(self, data):
        resp = []
        for word in zip(*[iter(data)] * 3):
            if self.__crc(word[0:2]) != word[2]:
                raise ValueError("CRC unmatch")  # noqa: EM101, TRY003
            resp.extend(word[0:2])
        return resp

    def __get_data_ready(self):
        # get_data_ready_status

        read = self.i2cbus.msg.read(self.dev_addr, 3)
        self.i2cbus.i2c_rdwr(self.i2cbus.msg.write(self.dev_addr, [0xE4, 0xB8]), read)
        resp = self.__decode_response(bytes(read))

        return (int.from_bytes(resp[0:2], byteorder="big") & 0x7F) != 0

    def __start_measurement(self):
        # NOTE: まず待ってみて，それでもデータが準備できないようだったら
        # 計測が始まっていないと判断する
        for _ in range(10):
            if self.__get_data_ready():
                return
            time.sleep(0.5)

        # start_periodic_measurement
        self.i2cbus.i2c_rdwr(self.i2cbus.msg.write(self.dev_addr, [0x21, 0xB1]))

        for _ in range(10):
            if self.__get_data_ready():
                return
            time.sleep(0.5)

    def get_value(self):
        self.__start_measurement()

        read = self.i2cbus.msg.read(self.dev_addr, 9)
        self.i2cbus.i2c_rdwr(self.i2cbus.msg.write(self.dev_addr, [0xEC, 0x05]), read)
        resp = self.__decode_response(bytes(read))

        co2 = int.from_bytes(resp[0:2], byteorder="big")
        temp = -45 + (175 * int.from_bytes(resp[2:4], byteorder="big")) / float(2**16 - 1)
        humi = 100 * int.from_bytes(resp[4:6], byteorder="big") / float(2**16 - 1)

        return [co2, round(temp, 4), round(humi, 1)]

    def get_value_map(self):
        value = self.get_value()

        return {"co2": value[0], "temp": value[1], "humi": value[2]}


if __name__ == "__main__":
    # TEST Code
    import docopt

    import my_lib.logger

    args = docopt.docopt(__doc__)
    bus_id = int(args["-b"], 0)
    dev_addr = int(args["-d"], 0)

    my_lib.logger.init("sensors.scd4x", level=logging.DEBUG)

    sensor = my_lib.sensor.scd4x(bus_id=bus_id, dev_addr=dev_addr)

    ping = sensor.ping()
    logging.info("PING: %s", ping)
    if ping:
        logging.info("VALUE: %s", sensor.get_value_map())
