import smbus2
import logging

class I2CBUS:
    def __init__(self, bus_id):
        self.bus_id = bus_id
        self.smbus = smbus2.SMBus(bus_id)

    def write_byte_data(self, dev_addr, register, data):
        logging.debug("i2c write - dev:0x%02X reg:0x%02X data:0x%02X", dev_addr, register, data)
        self.smbus.write_byte_data(dev_addr, register, data)

    def read_i2c_block_data(self, dev_addr, register, length):
        logging.debug("i2c read - dev:0x%02X reg:0x%02X length:%d", dev_addr, register, length)

        data = self.smbus.read_i2c_block_data(dev_addr, register, length)

        logging.debug("data: [%s]", ", ".join([f"{byte:02X}" for byte in data]))
        
        return data

        
        
        
