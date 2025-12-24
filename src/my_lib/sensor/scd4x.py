#!/usr/bin/env python3
"""
SCD4x を使って CO2 濃度を取得するライブラリです。

Usage:
  scd4x.py [-b BUS] [-d DEV_ADDR] [-D]

Options:
  -b BUS            : I2C バス番号。[default: 0x01]
  -d DEV_ADDR       : デバイスアドレス(7bit)。 [default: 0x62]
  -D                : デバッグモードで動作します。
"""

# 作成時に使用したのは、Sensirion の SEK SCD41。
# https://www.sensirion.com/en/environmental-sensors/evaluation-kit-sek-environmental-sensing/evaluation-kit-sek-scd41/
# 明示的に start_periodic_measurement を呼ばなくても済むように少し工夫しています。

from __future__ import annotations

import time

from my_lib.sensor import i2cbus
from my_lib.sensor.base import I2CSensorBase
from my_lib.sensor.exceptions import SensorCRCError


class SCD4X(I2CSensorBase):
    NAME: str = "SCD4X"
    DEV_ADDR: int = 0x62  # 7bit

    def __init__(self, bus_id: int = i2cbus.I2CBUS.ARM, dev_addr: int | None = None) -> None:
        super().__init__(bus_id, dev_addr)
        self.is_init: bool = False

    def _ping_impl(self) -> bool:
        self.__get_data_ready()
        return True

    def __reset(self) -> None:
        # sto_periodic_measurement
        self.i2cbus.write_byte_data(self.dev_addr, 0x3F, 0x86)
        time.sleep(0.5)
        # reinit
        self.i2cbus.write_byte_data(self.dev_addr, 0x36, 0x46)
        time.sleep(0.02)

    def __crc(self, msg: bytes | list[int]) -> int:
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

    def __decode_response(self, data: bytes) -> list[int]:
        resp: list[int] = []
        for word in zip(*[iter(data)] * 3, strict=False):
            if self.__crc(list(word[0:2])) != word[2]:
                raise SensorCRCError("CRC unmatch")
            resp.extend(word[0:2])
        return resp

    def __get_data_ready(self) -> bool:
        # get_data_ready_status

        read = self.i2cbus.msg.read(self.dev_addr, 3)
        self.i2cbus.i2c_rdwr(self.i2cbus.msg.write(self.dev_addr, [0xE4, 0xB8]), read)
        resp = self.__decode_response(bytes(read))

        return (int.from_bytes(resp[0:2], byteorder="big") & 0x7F) != 0

    def __start_measurement(self) -> None:
        # NOTE: まず待ってみて、それでもデータが準備できないようだったら
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

    def get_value(self) -> list[int | float]:
        self.__start_measurement()

        read = self.i2cbus.msg.read(self.dev_addr, 9)
        self.i2cbus.i2c_rdwr(self.i2cbus.msg.write(self.dev_addr, [0xEC, 0x05]), read)
        resp = self.__decode_response(bytes(read))

        co2 = int.from_bytes(resp[0:2], byteorder="big")
        temp = -45 + (175 * int.from_bytes(resp[2:4], byteorder="big")) / float(2**16 - 1)
        humi = 100 * int.from_bytes(resp[4:6], byteorder="big") / float(2**16 - 1)

        return [co2, round(temp, 4), round(humi, 1)]

    def get_value_map(self) -> dict[str, int | float]:
        value = self.get_value()

        return {"co2": value[0], "temp": value[1], "humi": value[2]}


if __name__ == "__main__":
    # TEST Code
    import docopt

    import my_lib.logger

    args = docopt.docopt(__doc__)
    bus_id = int(args["-b"], 0)
    dev_addr = int(args["-d"], 0)
    debug_mode = args["-D"]

    my_lib.logger.init("test", level=logging.DEBUG if debug_mode else logging.INFO)

    sensor = SCD4X(bus_id=bus_id, dev_addr=dev_addr)

    ping = sensor.ping()
    logging.info("PING: %s", ping)
    if ping:
        logging.info("VALUE: %s", sensor.get_value_map())
