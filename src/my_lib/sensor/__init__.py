from __future__ import annotations

import importlib
import logging
import pathlib
from typing import TYPE_CHECKING, Any

import my_lib.sensor
import my_lib.sensor.i2cbus

from .ads1015 import ADS1015 as ads1015
from .ads1115 import ADS1115 as ads1115
from .ads_base import ADSBase
from .apds9250 import APDS9250 as apds9250
from .base import SensorBase, SensorValue
from .bp35a1 import BP35A1 as bp35a1
from .echonetenergy import EchonetEnergy as echonetenergy
from .echonetlite import ECHONETLite as echonetlite
from .ezo_ph import EZO_PH as ezo_ph
from .ezo_rtd import EZO_RTD as ezo_rtd
from .fd_q10c import FD_Q10C as fd_q10c
from .grove_tds import GROVE_TDS as grove_tds
from .lp_pyra03 import LP_PYRA03 as lp_pyra03
from .rg_15 import RG_15 as rg_15
from .scd4x import SCD4X as scd4x
from .sht35 import SHT35 as sht35
from .sm9561 import SM9561 as sm9561

if TYPE_CHECKING:
    from typing import Protocol

    class SensorProtocol(Protocol):
        NAME: str
        TYPE: str
        required: bool
        dev_addr: int  # I2C デバイスアドレス（I2C センサーの場合）

        def ping(self) -> bool: ...
        def get_value_map(self) -> dict[str, SensorValue]: ...


iolink = importlib.import_module(".io_link", __package__)

__all__ = [
    "ADSBase",
    "SensorBase",
    "SensorValue",
    "ads1015",
    "ads1115",
    "apds9250",
    "bp35a1",
    "echonetenergy",
    "echonetlite",
    "ezo_ph",
    "ezo_rtd",
    "fd_q10c",
    "grove_tds",
    "iolink",
    "lp_pyra03",
    "rg_15",
    "scd4x",
    "sht35",
    "sm9561",
]


def load(sensor_def_list: list[dict[str, Any]]) -> list[SensorProtocol]:
    logging.info("Load drivers...")

    sensor_list: list[SensorProtocol] = []
    for sensor_def in sensor_def_list:
        logging.info("Load %s driver", sensor_def["name"])

        param: dict[str, Any] = {}
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


def sensor_info(sensor: SensorProtocol) -> str:
    if sensor.TYPE == "I2C":
        return f"{sensor.NAME} (I2C: 0x{sensor.dev_addr:02X})"
    else:
        return f"{sensor.NAME} ({sensor.TYPE})"


def ping(sensor_list: list[SensorProtocol]) -> list[SensorProtocol]:
    logging.info("Check sensor existences...")

    active_sensor_list: list[SensorProtocol] = []
    for sensor in sensor_list:
        if sensor.ping():
            logging.info("Sensor %s exists.", sensor.NAME)
            active_sensor_list.append(sensor)
        else:
            if sensor.required:
                logging.error("Sensor %s dost NOT exists. Ignored.", sensor.NAME)
                raise RuntimeError("The required sensor could not be found.")
            else:
                logging.warning("Sensor %s dost NOT exists. Ignored.", sensor.NAME)

    logging.info("Active sensor list: %s", ", ".join([sensor_info(sensor) for sensor in active_sensor_list]))
    return active_sensor_list


def sense(sensor_list: list[SensorProtocol]) -> tuple[dict[str, SensorValue], bool]:
    value_map: dict[str, SensorValue] = {}
    is_success = True
    for sensor in sensor_list:
        try:
            logging.info("Measurement is taken using %s", sensor.NAME)
            val = sensor.get_value_map()
            logging.info(val)
            value_map.update(val)
        except Exception:
            logging.exception("Failed to measure using %s", sensor.NAME)
            is_success = False

    logging.info("Measured results: %s", value_map)

    return (value_map, is_success)
