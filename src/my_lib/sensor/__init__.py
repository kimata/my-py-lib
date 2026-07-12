from __future__ import annotations

import difflib
import importlib
import logging
import pathlib
import traceback
from typing import Any, NamedTuple

import my_lib.sensor
import my_lib.sensor.i2cbus

from .ads1015 import ADS1015 as ads1015
from .ads1115 import ADS1115 as ads1115
from .ads_base import ADSBase
from .apds9250 import APDS9250 as apds9250
from .base import I2CSensorBase, SensorBase, SensorValue, UARTSensorBase
from .bp35a1 import BP35A1 as bp35a1
from .echonetenergy import EchonetEnergy as echonetenergy
from .echonetlite import ECHONETLite as echonetlite
from .ezo_do import EZO_DO as ezo_do
from .ezo_ph import EZO_PH as ezo_ph
from .ezo_rtd import EZO_RTD as ezo_rtd
from .fd_q10c import FD_Q10C as fd_q10c
from .grove_tds import GROVE_TDS as grove_tds
from .lp_pyra03 import LP_PYRA03 as lp_pyra03
from .max31856 import MAX31856 as max31856
from .rg_15 import RG_15 as rg_15
from .scd4x import SCD4X as scd4x
from .sht35 import SHT35 as sht35
from .sm9561 import SM9561 as sm9561
from .veml6075 import VEML6075 as veml6075
from .veml7700 import VEML7700 as veml7700


class FailedSensor(NamedTuple):
    """sense() 中で連続失敗の閾値に達したセンサーと、その時点のトレースバック。"""

    sensor: Any
    traceback: str


iolink = importlib.import_module(".io_link", __package__)

__all__ = [
    "ADSBase",
    "I2CSensorBase",
    "SensorBase",
    "SensorValue",
    "UARTSensorBase",
    "ads1015",
    "ads1115",
    "apds9250",
    "bp35a1",
    "echonetenergy",
    "echonetlite",
    "ezo_do",
    "ezo_ph",
    "ezo_rtd",
    "fd_q10c",
    "grove_tds",
    "iolink",
    "lp_pyra03",
    "max31856",
    "rg_15",
    "scd4x",
    "sht35",
    "sm9561",
    "veml6075",
    "veml7700",
]

# NOTE: config の name で指定できるドライバのホワイトリスト。
# bp35a1 (通信モジュール) や echonetlite (プロトコル実装) のような
# SensorBase 非準拠のクラスや、ADSBase のような基底クラス (大文字表記の re-export)
# を誤って指定できないようにする。
DRIVER_NAME_LIST: list[str] = sorted(
    name
    for name in __all__
    if name.islower() and isinstance(globals().get(name), type) and issubclass(globals()[name], SensorBase)
)


def resolve_driver(name: str) -> type[SensorBase]:
    """config の name からドライバクラスを解決する。未知の名前は候補提示付きで raise。"""
    if name in DRIVER_NAME_LIST:
        return getattr(my_lib.sensor, name)

    suggest = difflib.get_close_matches(name, DRIVER_NAME_LIST, n=3)
    hint = f" もしかして: {', '.join(suggest)}?" if suggest else ""
    raise ValueError(f"未知のセンサー名: {name!r}。{hint} 指定可能な名前: {', '.join(DRIVER_NAME_LIST)}")


def _resolve_i2c_bus(sensor_def: dict[str, Any]) -> int | None:
    """config の i2c_bus (または旧キー bus) から I2C バス番号を解決する。"""
    bus_name = sensor_def.get("i2c_bus", sensor_def.get("bus"))
    if bus_name is None:
        return None

    bus_id = getattr(my_lib.sensor.i2cbus.I2CBUS, str(bus_name).upper(), None)
    if not isinstance(bus_id, int):
        raise ValueError(f"未知の I2C バス名: {bus_name!r} (指定可能: ARM, VC)")
    return bus_id


def load(sensor_def_list: list[dict[str, Any]]) -> list[SensorBase]:
    logging.info("ドライバをロード中...")

    sensor_list: list[SensorBase] = []
    for sensor_def in sensor_def_list:
        logging.info("%s ドライバをロード", sensor_def["name"])

        sensor_class = resolve_driver(sensor_def["name"])

        if "uart_dev" in sensor_def:
            dev_file = sensor_def["uart_dev"]
            # NOTE: I2C バスと同様、デバイスファイルがなければ warning してスキップする
            if not pathlib.Path(dev_file).exists():
                logging.warning("UART デバイス %s が存在しないためスキップ", dev_file)
                continue

            sensor = sensor_class(dev_file, sensor_def.get("param"))  # type: ignore[call-arg]
        else:
            # NOTE: デフォルトは I2C デバイスと見なす
            param: dict[str, Any] = {}
            bus_id = _resolve_i2c_bus(sensor_def)
            if bus_id is not None:
                dev_file = pathlib.Path(f"/dev/i2c-{bus_id}")
                if not dev_file.exists():
                    logging.warning(
                        "I2C bus %s (%s) が存在しないためスキップ",
                        sensor_def.get("i2c_bus", sensor_def.get("bus")),
                        dev_file,
                    )
                    continue
                param["bus_id"] = bus_id

            if "dev_addr" in sensor_def:
                param["dev_addr"] = sensor_def["dev_addr"]

            sensor = sensor_class(**param)  # type: ignore[call-arg]

        sensor.required = sensor_def.get("required", False)
        # NOTE: 同種キーの衝突回避用 (sense() が get_value_map のキーへ適用する)
        sensor.field_prefix = sensor_def.get("field_prefix", "")
        sensor.field_rename = sensor_def.get("rename", {})
        sensor_list.append(sensor)

    return sensor_list


def sensor_info(sensor: SensorBase) -> str:
    if sensor.TYPE == "I2C":
        # NOTE: I2C センサーは dev_addr を持つ。SensorBase の型では明示されないので
        # getattr で取り出す (テスト Mock が I2CSensorBase を継承していない場合にも対応)。
        dev_addr = getattr(sensor, "dev_addr", None)
        if isinstance(dev_addr, int):
            return f"{sensor.NAME} (I2C: 0x{dev_addr:02X})"
    return f"{sensor.NAME} ({sensor.TYPE})"


def _safe_ping(sensor: SensorBase) -> bool:
    """ping を実行する。例外は「応答なし」として扱い、呼び出し元アプリを落とさない。"""
    try:
        return sensor.ping()
    except Exception:
        logging.exception("センサー %s の ping で例外が発生 (応答なしとして扱う)", sensor.NAME)
        return False


def ping(
    sensor_list: list[SensorBase],
) -> tuple[list[SensorBase], list[SensorBase]]:
    logging.info("センサーの存在確認中...")

    active_sensor_list: list[SensorBase] = []
    inactive_sensor_list: list[SensorBase] = []
    for sensor in sensor_list:
        if _safe_ping(sensor):
            logging.info("センサー %s は応答あり", sensor.NAME)
            active_sensor_list.append(sensor)
        else:
            if sensor.required:
                logging.error("必須センサー %s が見つかりません", sensor.NAME)
                raise RuntimeError("必須センサーが見つかりませんでした")
            else:
                logging.warning("センサー %s が応答しないため無効化", sensor.NAME)
                inactive_sensor_list.append(sensor)

    logging.info("有効なセンサー: %s", ", ".join([sensor_info(sensor) for sensor in active_sensor_list]))
    return active_sensor_list, inactive_sensor_list


def retry_inactive(
    active_sensor_list: list[SensorBase],
    inactive_sensor_list: list[SensorBase],
    index: int,
) -> tuple[int, SensorBase | None]:
    """inactive なセンサーをラウンドロビンで 1 つだけ ping し、復帰していれば active に移す。

    戻り値は (次回呼び出し時に使う index, 復帰したセンサー (なければ None))。
    """
    if not inactive_sensor_list:
        return (0, None)

    index %= len(inactive_sensor_list)
    sensor = inactive_sensor_list[index]
    logging.debug("無効化されたセンサー %s を ping で再試行", sensor.NAME)

    if _safe_ping(sensor):
        logging.info("センサー %s が復帰", sensor.NAME)
        inactive_sensor_list.pop(index)
        active_sensor_list.append(sensor)
        sensor.consecutive_fails = 0
        # NOTE: リストが縮むので、次回は同じ index から始める
        return (index, sensor)

    return (index + 1, None)


def _apply_field_naming(sensor: SensorBase, value_map: dict[str, SensorValue]) -> dict[str, SensorValue]:
    """config の rename / field_prefix を get_value_map のキーへ適用する。"""
    if not sensor.field_prefix and not sensor.field_rename:
        return value_map

    return {
        f"{sensor.field_prefix}{sensor.field_rename.get(key, key)}": value for key, value in value_map.items()
    }


def sense(
    active_sensor_list: list[SensorBase],
    fail_threshold: int = 2,
) -> tuple[dict[str, SensorValue], bool, list[FailedSensor], list[SensorBase]]:
    """active なセンサーを計測する。

    各センサーの連続失敗回数を sensor.consecutive_fails で保持する。
    連続失敗回数が fail_threshold にちょうど達したセンサーを
    newly_failed として返す (同じ連続失敗ストリーク内で 1 回だけ)。
    fail_threshold 以上失敗していたセンサーが成功に転じた場合は
    newly_recovered として返す (復帰通知用)。
    センサーは降格しない。呼び出し側が is_success=False を見て
    liveness 更新をスキップするなどの判断を行う。
    """
    value_map: dict[str, SensorValue] = {}
    key_owner: dict[str, str] = {}
    is_success = True
    newly_failed: list[FailedSensor] = []
    newly_recovered: list[SensorBase] = []
    for sensor in active_sensor_list:
        try:
            logging.info("センサー %s で計測", sensor.NAME)
            val = _apply_field_naming(sensor, sensor.get_value_map())
            logging.info(val)

            for key in val:
                if key in key_owner:
                    logging.warning(
                        "フィールド %s が %s と %s で重複しており、%s の値で上書きされます。"
                        "(sensor 設定の field_prefix / rename で回避できます)",
                        key,
                        key_owner[key],
                        sensor.NAME,
                        sensor.NAME,
                    )
                key_owner[key] = sensor.NAME

            value_map.update(val)
            if sensor.consecutive_fails >= fail_threshold:
                newly_recovered.append(sensor)
            sensor.consecutive_fails = 0
        except Exception:
            logging.exception("センサー %s の計測に失敗", sensor.NAME)
            is_success = False
            sensor.consecutive_fails += 1
            # NOTE: ちょうど閾値に達した瞬間のみ返す (以降の連続失敗では再通知させない)
            if sensor.consecutive_fails == fail_threshold:
                newly_failed.append(FailedSensor(sensor=sensor, traceback=traceback.format_exc()))

    logging.info("計測結果: %s", value_map)

    return (value_map, is_success, newly_failed, newly_recovered)


def close(sensor_list: list[SensorBase]) -> None:
    """全センサーの通信ハンドルを解放する。"""
    for sensor in sensor_list:
        try:
            sensor.close()
        except Exception:
            logging.warning("センサー %s の close に失敗", sensor.NAME, exc_info=True)
