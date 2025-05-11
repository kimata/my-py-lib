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

import contextlib
import logging
import time

import my_lib.sensor.i2cbus


class SM9561:
    NAME = "SM9561"
    TYPE = "I2C"
    DEV_ADDR = 0x4D  # 7bit

    DEV_CRYSTCAL_FREQ = 7372800

    REG_RHR = 0x00 << 3
    REG_THR = 0x00 << 3
    REG_FCR = 0x02 << 3
    REG_LCR = 0x03 << 3
    REG_MCR = 0x04 << 3
    REG_LSR = 0x05 << 3
    REG_MSR = 0x06 << 3
    REG_SPR = 0x07 << 3
    REG_TXLVL = 0x08 << 3
    REG_RXLVL = 0x09 << 3
    REG_IOC = 0x0E << 3

    REG_DLL = 0x00 << 3
    REG_DLH = 0x01 << 3

    def __init__(self, bus_id=my_lib.sensor.i2cbus.I2CBUS.ARM, dev_addr=DEV_ADDR):  # noqa: D107
        self.bus_id = bus_id
        self.dev_addr = dev_addr
        self.i2cbus = my_lib.sensor.i2cbus(bus_id)

    def init(self):
        self.reset()
        self.set_link()
        self.set_baudrate(9600)

    def ping(self):
        try:
            data = self.i2cbus.read_byte_data(self.dev_addr, self.REG_SPR)

            # NOTE: Scratchpad を読み書きしてみる
            write_data = data ^ 0xFF
            self.i2cbus.write_byte_data(self.dev_addr, self.REG_SPR, write_data)
            read_data = self.i2cbus.read_byte_data(self.dev_addr, self.REG_SPR)

            return read_data == write_data
        except Exception:
            return False

    def reset(self):
        data = self.i2cbus.read_byte_data(self.dev_addr, self.REG_IOC)
        data |= 0x08

        # NOTE: Software reset をしたときは NACK が帰ってくるので、エラーは無視する
        with contextlib.suppress(OSError):
            self.i2cbus.write_byte_data(self.dev_addr, self.REG_IOC, data)

        time.sleep(0.1)

    def set_baudrate(self, baudrate):
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

    def set_link(self):
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

    def clear_fifo(self, is_enable=True):
        data = self.i2cbus.read_byte_data(self.dev_addr, self.REG_FCR)
        if is_enable:
            data |= 0x01
        else:
            data &= 0xFE

        # NOTE: clear FIFO
        data |= 0x06

        logging.debug("set FCR = 0x%02X", data)
        self.i2cbus.write_byte_data(self.dev_addr, self.REG_FCR, data)

    def set_rts(self, state):
        data = self.i2cbus.read_byte_data(self.dev_addr, self.REG_MCR)

        if state:
            data |= 0x02
        else:
            data &= ~0x02

        logging.debug("set MCR = 0x%02X", data)
        self.i2cbus.write_byte_data(self.dev_addr, self.REG_MCR, data)

    def calc_crc(self, data_list):
        POLY = 0xA001

        crc = 0xFFFF
        for data in data_list:
            crc ^= data

            for _ in range(8):
                if crc & 0x0001:
                    crc = (crc >> 1) ^ POLY
                else:
                    crc >>= 1

        return [crc & 0xFF, crc >> 8]

    def append_crc(self, data_list):
        return data_list + self.calc_crc(data_list)

    def write_bytes(self, data_list):
        self.set_rts(True)

        for data in data_list:
            self.i2cbus.write_byte_data(self.dev_addr, self.REG_THR, data)

        while (self.i2cbus.read_byte_data(self.dev_addr, self.REG_LSR) & 0x20) != 0x20:
            logging.debug("Wait for TX FIFO empty")
            time.sleep(0.005)
        time.sleep(0.005)

        self.set_rts(False)

    def read_bytes(self, length):
        data_list = []
        for _ in range(length):
            while self.i2cbus.read_byte_data(self.dev_addr, self.REG_RXLVL) == 0:
                logging.debug("Wait for RX FIFO data available")
                time.sleep(0.01)

            data = self.i2cbus.read_byte_data(self.dev_addr, self.REG_RHR)
            logging.debug("Read 0x%02X", data)
            data_list.append(data)

        return data_list

    def modbus_rtu_func3(self, dev_addr, start_addr, length):
        self.clear_fifo()

        self.write_bytes(
            self.append_crc([dev_addr, 0x03, start_addr >> 8, start_addr & 0xFF, length >> 8, length & 0xFF])
        )
        data = self.read_bytes(3)
        if (data[0] != dev_addr) or (data[1] != 0x03):
            raise OSError("Invalid response")  # noqa: EM101, TRY003
        length = data[2]
        data = self.read_bytes(length + 2)

        crc = self.calc_crc([dev_addr, 0x03, length] + data[0:length])

        if crc != data[length:]:
            raise OSError("CRC mismatch")  # noqa: EM101, TRY003

        return (data[0] << 8) + data[1]

    def get_value(self):
        self.init()
        time.sleep(0.1)

        value = self.modbus_rtu_func3(0x01, 0x0000, 0x0001)
        value *= 10

        return [value]

    def get_value_map(self):
        value = self.get_value()

        return {"lux": value[0]}


if __name__ == "__main__":
    # TEST Code
    import docopt
    import my_lib.logger
    import my_lib.sensor.sm9561

    args = docopt.docopt(__doc__)
    bus_id = int(args["-b"], 0)
    dev_addr = int(args["-d"], 0)
    debug_mode = args["-D"]

    my_lib.logger.init("test", level=logging.DEBUG if debug_mode else logging.INFO)

    sensor = my_lib.sensor.sm9561(bus_id=bus_id, dev_addr=dev_addr)

    ping = sensor.ping()
    logging.info("PING: %s", ping)
    if ping:
        logging.info("VALUE: %s", sensor.get_value_map())
