#!/usr/bin/env python3
"""
SM9561 を使って照度を計測するライブラリです。

Usage:
  sm9561.py [-b BUS] [-d DEV_ADDR] [-D]

Options:
  -b BUS            : I2C バス番号。[default: 0x01]
  -d DEV_ADDR       : デバイスアドレス(7bit)。 [default: 0x4D]
  -D                : デバッグモードで動作します。
"""

# SM9561: http://www.sonbest.com/english/products/SM9561.html

# RS485 通信は、下記の基板を使って I2C 経由で行うことを想定しています。
# I2C-RS422/485変換基板
# https://www.switch-science.com/products/7395
# https://github.com/meerstern/I2C_RS422_RS485_Converter

from __future__ import annotations

import contextlib
import logging
import time

from my_lib.sensor import i2cbus
from my_lib.sensor.crc import crc16_modbus
from my_lib.sensor.exceptions import SensorCommunicationError, SensorCRCError


class SM9561:
    NAME: str = "SM9561"
    TYPE: str = "I2C"
    DEV_ADDR: int = 0x4D  # 7bit

    DEV_CRYSTCAL_FREQ: int = 7372800

    REG_RHR: int = 0x00 << 3
    REG_THR: int = 0x00 << 3
    REG_FCR: int = 0x02 << 3
    REG_LCR: int = 0x03 << 3
    REG_MCR: int = 0x04 << 3
    REG_LSR: int = 0x05 << 3
    REG_MSR: int = 0x06 << 3
    REG_SPR: int = 0x07 << 3
    REG_TXLVL: int = 0x08 << 3
    REG_RXLVL: int = 0x09 << 3
    REG_IOC: int = 0x0E << 3

    REG_DLL: int = 0x00 << 3
    REG_DLH: int = 0x01 << 3

    def __init__(self, bus_id: int = i2cbus.I2CBUS.ARM, dev_addr: int = DEV_ADDR) -> None:  # noqa: D107
        self.bus_id: int = bus_id
        self.dev_addr: int = dev_addr
        self.i2cbus: i2cbus.I2CBUS = i2cbus.I2CBUS(bus_id)

    def init(self) -> None:
        self.reset()
        self.set_link()
        self.set_baudrate(9600)

    def ping(self) -> bool:
        try:
            data = self.i2cbus.read_byte_data(self.dev_addr, self.REG_SPR)

            # NOTE: Scratchpad を読み書きしてみる
            write_data = data ^ 0xFF
            self.i2cbus.write_byte_data(self.dev_addr, self.REG_SPR, write_data)
            read_data = self.i2cbus.read_byte_data(self.dev_addr, self.REG_SPR)

            return read_data == write_data
        except Exception:
            return False

    def reset(self) -> None:
        data = self.i2cbus.read_byte_data(self.dev_addr, self.REG_IOC)
        data |= 0x08

        # NOTE: Software reset をしたときは NACK が帰ってくるので、エラーは無視する
        with contextlib.suppress(OSError):
            self.i2cbus.write_byte_data(self.dev_addr, self.REG_IOC, data)

        time.sleep(0.1)

    def set_baudrate(self, baudrate: int) -> None:
        data = self.i2cbus.read_byte_data(self.dev_addr, self.REG_MCR)

        prescaler = 1 if (data & 0x80) == 0 else 4
        divisor = int((self.DEV_CRYSTCAL_FREQ / prescaler) / (baudrate * 16))

        # NOTE: Divisor latch enable
        data = self.i2cbus.read_byte_data(self.dev_addr, self.REG_LCR)
        data |= 0x80
        logging.debug("set LCR = 0x%02X", data)
        self.i2cbus.write_byte_data(self.dev_addr, self.REG_LCR, data)

        logging.debug("set DLL = 0x%02X", divisor & 0xFF)
        self.i2cbus.write_byte_data(self.dev_addr, self.REG_DLL, divisor & 0xFF)
        logging.debug("set DLH = 0x%02X", divisor >> 8)
        self.i2cbus.write_byte_data(self.dev_addr, self.REG_DLH, divisor >> 8)

        # NOTE: Divisor latch disable
        data &= ~0x80
        logging.debug("set LCR = 0x%02X", data)
        self.i2cbus.write_byte_data(self.dev_addr, self.REG_LCR, data)

    def set_link(self) -> None:
        data = self.i2cbus.read_byte_data(self.dev_addr, self.REG_LCR)
        data &= 0xC0

        # NOTE: No parity
        data |= 0x00
        # NOTE: Stop is 1 bit
        data |= 0x00
        # NOTE: Word length is 8 bits
        data |= 0x03

        logging.debug("set LCR = 0x%02X", data)
        self.i2cbus.write_byte_data(self.dev_addr, self.REG_LCR, data)

    def clear_fifo(self, is_enable: bool = True) -> None:
        data = self.i2cbus.read_byte_data(self.dev_addr, self.REG_FCR)
        if is_enable:
            data |= 0x01
        else:
            data &= 0xFE

        # NOTE: clear FIFO
        data |= 0x06

        logging.debug("set FCR = 0x%02X", data)
        self.i2cbus.write_byte_data(self.dev_addr, self.REG_FCR, data)

    def set_rts(self, state: bool) -> None:
        data = self.i2cbus.read_byte_data(self.dev_addr, self.REG_MCR)

        if state:
            data |= 0x02
        else:
            data &= ~0x02

        logging.debug("set MCR = 0x%02X", data)
        self.i2cbus.write_byte_data(self.dev_addr, self.REG_MCR, data)

    def append_crc(self, data_list: list[int]) -> list[int]:
        return data_list + crc16_modbus(data_list)

    def write_bytes(self, data_list: list[int]) -> None:
        self.set_rts(True)

        for data in data_list:
            self.i2cbus.write_byte_data(self.dev_addr, self.REG_THR, data)

        while (self.i2cbus.read_byte_data(self.dev_addr, self.REG_LSR) & 0x20) != 0x20:
            logging.debug("Wait for TX FIFO empty")
            time.sleep(0.005)
        time.sleep(0.005)

        self.set_rts(False)

    def read_bytes(self, length: int) -> list[int]:
        data_list: list[int] = []
        for _ in range(length):
            while self.i2cbus.read_byte_data(self.dev_addr, self.REG_RXLVL) == 0:
                logging.debug("Wait for RX FIFO data available")
                time.sleep(0.01)

            data = self.i2cbus.read_byte_data(self.dev_addr, self.REG_RHR)
            logging.debug("Read 0x%02X", data)
            data_list.append(data)

        return data_list

    def modbus_rtu_func3(self, dev_addr: int, start_addr: int, length: int) -> int:
        self.clear_fifo()

        self.write_bytes(
            self.append_crc([dev_addr, 0x03, start_addr >> 8, start_addr & 0xFF, length >> 8, length & 0xFF])
        )
        data = self.read_bytes(3)
        if (data[0] != dev_addr) or (data[1] != 0x03):
            raise SensorCommunicationError("Invalid response")
        length = data[2]
        data = self.read_bytes(length + 2)

        crc = crc16_modbus([dev_addr, 0x03, length, *data[0:length]])

        if crc != list(data[length:]):
            raise SensorCRCError("CRC mismatch")

        return (data[0] << 8) + data[1]

    def get_value(self) -> list[int]:
        self.init()
        time.sleep(0.1)

        value = self.modbus_rtu_func3(0x01, 0x0000, 0x0001)
        value *= 10

        return [value]

    def get_value_map(self) -> dict[str, int]:
        value = self.get_value()

        return {"lux": value[0]}


if __name__ == "__main__":
    # TEST Code
    import docopt

    import my_lib.logger

    args = docopt.docopt(__doc__)
    bus_id = int(args["-b"], 0)
    dev_addr = int(args["-d"], 0)
    debug_mode = args["-D"]

    my_lib.logger.init("test", level=logging.DEBUG if debug_mode else logging.INFO)

    sensor = SM9561(bus_id=bus_id, dev_addr=dev_addr)

    ping = sensor.ping()
    logging.info("PING: %s", ping)
    if ping:
        logging.info("VALUE: %s", sensor.get_value_map())
