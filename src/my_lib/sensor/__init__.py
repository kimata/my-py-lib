#!/usr/bin/env python3
from .i2cbus import I2CBUS as i2cbus

from .sht35 import SHT35 as sht35
from .scd4x import SCD4X as scd4x
from .apds9250 import APDS9250 as apds9250

import importlib
import logging
import my_lib.sensor

RASP_I2C_BUS = {
    "arm": 0x1,  # Raspberry Pi のデフォルトの I2C バス番号
    "vc": 0x0,  # dtparam=i2c_vc=on で有効化される I2C のバス番号
}

def load(sensor_cand_list):
    sensor_list = []
    for sensor in sensor_cand_list:
        logging.info("Load sensor {name}".format(name=sensor["name"]))

        if "i2c_bus" in sensor:
            bus = RASP_I2C_BUS[sensor["i2c_bus"]]

            i2c_dev_file = pathlib.Path("/dev/i2c-{bus}".format(bus=bus))
            if not i2c_dev_file.exists():
                logging.warning(
                    "I2C bus {bus} ({dev_file}) does NOT exist. skipping...".format(
                        bus=bus, dev_file=str(i2c_dev_file)
                    )
                )
                continue

            sensor = getattr(my_lib.sensor, sensor["name"])(bus=bus)
        else:
            sensor = getattr(my_lib.sensor, sensor["name"])()

        sensor_list.append(sensor)

    return sensor_list

def ping(sensor_list):
    logging.info("Check sensor existences...")

    active_sensor_list = []
    for sensor in sensor_list:
        if sensor.ping():
            logging.info("Sensor %s exists.", sensor.NAME)
            active_sensor_list.append(sensor)
        else:
            logging.warning("Sensor %s dost NOT exists. Ignored...", sensor.NAME)

    return active_sensor_list 


def sense(sensor_list):
    value_map = {}
    for sensor in sensor_list:
        try:
            logging.info("Measurement is taken using %s", sensor.NAME)
            val = sensor.get_value_map()
            logging.info(val)
            value_map.update(val)
        except Exception:
            logging.exception("Failed to measure using %s", sensor.NAME)

    logging.info("Measured results: %s", value_map)

    return value_map

