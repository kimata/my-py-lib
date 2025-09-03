# noqa: D104
import importlib
import logging
import pathlib

import my_lib.sensor
import my_lib.sensor.i2cbus

from .ads1015 import ADS1015 as ads1015  # noqa: N811
from .apds9250 import APDS9250 as apds9250  # noqa: N811
from .bp35a1 import BP35A1 as bp35a1  # noqa: N811
from .echonetenergy import EchonetEnergy as echonetenergy  # noqa: N813
from .echonetlite import ECHONETLite as echonetlite  # noqa: N813
from .ezo_ph import EZO_PH as ezo_ph  # noqa: N811
from .ezo_rtd import EZO_RTD as ezo_rtd  # noqa: N811
from .fd_q10c import FD_Q10C as fd_q10c  # noqa: N811
from .grove_tds import GROVE_TDS as grove_tds  # noqa: N811
from .lp_pyra03 import LP_PYRA03 as lp_pyra03  # noqa: N811
from .rg_15 import RG_15 as rg_15  # noqa: N811
from .scd4x import SCD4X as scd4x  # noqa: N811
from .sht35 import SHT35 as sht35  # noqa: N811
from .sm9561 import SM9561 as sm9561  # noqa: N811

iolink = importlib.import_module(".io_link", __package__)

__all__ = [
    "ads1015",
    "apds9250",
    "bp35a1",
    "echonetenergy",
    "echonetlite",
    "ezo_ph",
    "ezo_rtd",
    "fd_q10c",
    "grove_tds",
    "i2cbus",
    "iolink",
    "lp_pyra03",
    "rg_15",
    "scd4x",
    "sht35",
    "sm9561",
]


def load(sensor_def_list):
    logging.info("Load drivers...")

    sensor_list = []
    for sensor_def in sensor_def_list:
        logging.info("Load %s driver", sensor_def["name"])

        param = {}
        if "uart_dev" in sensor_def:
            dev_file = sensor_def["uart_dev"]

            sensor = getattr(my_lib.sensor, sensor_def["name"])(dev_file, sensor_def["param"])
        else:
            # NOTE: デフォルトは I2C デバイスと見なす
            if "i2c_bus" in sensor_def:
                param["bus_id"] = getattr(my_lib.sensor.i2cbus.I2CBUS, sensor_def["i2c_bus"])
                dev_file = pathlib.Path(f"/dev/i2c-{param['bus_id']}")
                if not dev_file.exists():
                    logging.warning(
                        "I2C bus %d (%s) does NOT exist. skipping.", sensor_def["i2c_bus"], dev_file
                    )
                    continue

            if "dev_addr" in sensor_def:
                param["dev_addr"] = sensor_def["dev_addr"]

            sensor = getattr(my_lib.sensor, sensor_def["name"])(
                **{k: v for k, v in param.items() if k in ["bus_id", "dev_addr"]}
            )

        sensor.required = sensor_def.get("required", False)
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
            if sensor.required:
                logging.error("Sensor %s dost NOT exists. Ignored.", sensor.NAME)
                raise "The required sensor could not be found."
            else:
                logging.warning("Sensor %s dost NOT exists. Ignored.", sensor.NAME)

    logging.info("Active sensor list: %s", ", ".join([sensor_info(sensor) for sensor in active_sensor_list]))
    return active_sensor_list


def sense(sensor_list):
    value_map = {}
    is_success = True
    for sensor in sensor_list:
        try:
            logging.info("Measurement is taken using %s", sensor.NAME)
            val = sensor.get_value_map()
            logging.info(val)
            value_map.update(val)
        except Exception:  # noqa: PERF203
            logging.exception("Failed to measure using %s", sensor.NAME)
            is_success = False

    logging.info("Measured results: %s", value_map)

    return (value_map, is_success)
