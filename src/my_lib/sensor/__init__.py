# noqa: D104
import importlib
import logging
import pathlib

import my_lib.sensor

from .ads1015 import ADS1015 as ads1015  # noqa: N811
from .apds9250 import APDS9250 as apds9250  # noqa: N811
from .bp35a1 import BP35A1 as bp35a1  # noqa: N811
from .echonetenergy import EchonetEnergy as echonetenergy  # noqa: N811
from .echonetlite import ECHONETLite as echonetlite  # noqa: N811
from .ezo_ph import EZO_PH as ezo_ph  # noqa: N811
from .ezo_rtd import EZO_RTD as ezo_rtd  # noqa: N811
from .fd_q10c import FD_Q10C as fd_q10c  # noqa: N811
from .grove_tds import GROVE_TDS as grove_tds  # noqa: N811
from .i2cbus import I2CBUS as i2cbus  # noqa: N811  # noqa: N811
from .lp_pyra03 import LP_PYRA03 as lp_pyra03  # noqa: N811
from .rg_15 import RG_15 as rg_15  # noqa: N811
from .scd4x import SCD4X as scd4x  # noqa: N811
from .sht35 import SHT35 as sht35  # noqa: N811

iolink = importlib.import_module(".io_link", __package__)

__all__ = [
    "ads1015",
    "apds9250",
    "bp35a10",
    "ezo_ph",
    "ezo_rtd",
    "grove_tds",
    "i2cbus",
    "scd4x",
    "lp_pyra03",
    "sht35",
    "sm9561",
    "fd_q10c",
    "rg_15",
    "iolink",
    "echonetlite",
    "echonetenergy",
]


def load(sensor_def_list):
    logging.info("Load drivers...")

    sensor_list = []
    for sensor_def in sensor_def_list:
        logging.info("Load %s driver", sensor_def["name"])

        param = {}
        if "i2c_bus" in sensor_def:
            param["bus_id"] = getattr(i2cbus, sensor_def["i2c_bus"])
            i2c_dev_file = pathlib.Path(f"/dev/i2c-{param['bus_id']}")
            if not i2c_dev_file.exists():
                logging.warning(
                    "I2C bus %d (%s) does NOT exist. skipping.", sensor_def["i2c_bus"], i2c_dev_file
                )
                continue

        if "dev_addr" in sensor_def:
            param["dev_addr"] = sensor_def["dev_addr"]

        sensor = getattr(my_lib.sensor, sensor_def["name"])(
            **{k: v for k, v in param.items() if k in ["bus_id", "dev_addr"]}
        )

        sensor_list.append(sensor)

    return sensor_list


def sensor_info(sensor):
    if sensor.TYPE == "I2C":
        return f"{sensor.NAME} (I2C: 0x{sensor.dev_addr:02X})"
    else:
        return f"{sensor.NAME} ({sensor.TYPE})"


def ping(sensor_list):
    logging.info("Check sensor existences...")

    active_sensor_list = []
    for sensor in sensor_list:
        if sensor.ping():
            logging.info("Sensor %s exists.", sensor.NAME)
            active_sensor_list.append(sensor)
        else:
            logging.warning("Sensor %s dost NOT exists. Ignored.", sensor.NAME)

    logging.info("Active sensor list: %s", ", ".join([sensor_info(sensor) for sensor in active_sensor_list]))
    return active_sensor_list


def sense(sensor_list):
    value_map = {}
    for sensor in sensor_list:
        try:
            logging.info("Measurement is taken using %s", sensor.NAME)
            val = sensor.get_value_map()
            logging.info(val)
            value_map.update(val)
        except Exception:  # noqa: PERF203
            logging.exception("Failed to measure using %s", sensor.NAME)

    logging.info("Measured results: %s", value_map)

    return value_map
