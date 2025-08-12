import ctypes
import logging

import smbus2


# NOTE: デバッグ時にログ出力するために smbus2 をラッピング
class I2CBUS:
    ARM = 0x1  # Raspberry Pi のデフォルトの I2C バス番号
    VC = 0x0  # dtparam=i2c_vc=on で有効化される I2C のバス番号

    def __init__(self, bus_id):  # noqa: D107
        self.bus_id = bus_id
        self.smbus = smbus2.SMBus(bus_id)

    def write_byte_data(self, dev_addr, register, data):
        logging.debug("i2c write - dev:0x%02X reg:0x%02X data:0x%02X", dev_addr, register, data)
        self.smbus.write_byte_data(dev_addr, register, data)

    def read_i2c_block_data(self, dev_addr, register, length):
        logging.debug("i2c read - dev:0x%02X reg:0x%02X length:%d", dev_addr, register, length)

        data = self.smbus.read_i2c_block_data(dev_addr, register, length)

        logging.debug("data: [%s]", ", ".join([f"0x{byte:02X}" for byte in data]))

        return data

    def read_byte_data(self, dev_addr, register):
        logging.debug("i2c read - dev:0x%02X reg:0x%02X length:1", dev_addr, register)

        data = self.smbus.read_byte_data(dev_addr, register)

        logging.debug("data: [%s]", f"0x{data:02X}")

        return data

    def i2c_rdwr(self, *i2c_msgs):
        msg_desc = []
        for msg in i2c_msgs:
            if msg.flags == 0:  # NOTE: Write
                p = ctypes.cast(msg.buf, ctypes.POINTER(ctypes.c_char))
                data = ",".join([f"0x{p[i].hex().upper()}" for i in range(msg.len)])

                msg_desc.append(f"[write dev:0x{msg.addr:02x}, data:{data}]")
            elif msg.flags == smbus2.smbus2.I2C_M_RD:  # NOTE: Read
                msg_desc.append(f"[read dev:0x{msg.addr:02x}, length:{msg.len}]")
            else:
                logging.error("Unknown I2C message flag: 0x%04X for device 0x%02X", msg.flags, msg.addr)
                raise ValueError(f"Unsupported I2C message flag: 0x{msg.flags:04X}")

        logging.debug("i2c read/write - %s", ", ".join(msg_desc))

        return self.smbus.i2c_rdwr(*i2c_msgs)

    class msg:  # noqa: D106, N801
        @staticmethod
        def read(address, length):
            return smbus2.i2c_msg.read(address, length)

        @staticmethod
        def write(address, buf):
            return smbus2.i2c_msg.write(address, buf)
