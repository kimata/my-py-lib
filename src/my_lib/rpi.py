#!/usr/bin/env python3
from __future__ import annotations

import collections
import enum
import logging
import os
import pathlib

# NOTE: time_machine を使ったテスト時に、別スレッドのものも含めて time.time() を mock で
# 置き換えたいので、別名にしておく。
from time import time as gpio_time
from typing import Any, ClassVar

# NOTE: gpio は実行環境によって RPi.GPIO モジュールまたはダミークラスになる
# Protocol で型定義が困難なため（クラス自体/モジュールとして使用）、Any で扱う
gpio: Any


def is_rasberry_pi() -> bool:
    try:
        with pathlib.Path("/proc/cpuinfo").open() as f:
            cpuinfo = f.read()

            if "Raspberry Pi" in cpuinfo:
                return True
            else:
                logging.warning(
                    "Since it is not running on a Raspberry Pi, "
                    "the GPIO library is replaced with dummy functions."
                )
                return False
    except Exception:
        logging.exception("Failed to judge running on Raspberry Pi")
        return False


if (
    is_rasberry_pi()
    and (os.environ.get("DUMMY_MODE", "false") != "true")
    and (os.environ.get("TEST", "false") != "true")
):  # pragma: no cover
    from RPi import GPIO

    gpio = GPIO
else:
    if os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        logging.warning("Using dummy GPIO")

    # NOTE: 本物の GPIO のように振る舞うダミーのライブラリ
    class _DummyGPIO:
        IS_DUMMY: bool = True
        BCM: int = 0
        OUT: int = 0

        # Valid GPIO pin numbers for Raspberry Pi (BCM mode)
        VALID_PINS: ClassVar[set[int]] = set(range(28))

        state: ClassVar[dict[str, dict[str, Any]]] = collections.defaultdict(
            lambda: {
                "state": collections.defaultdict(lambda: None),
                "time_start": collections.defaultdict(lambda: None),
                "time_stop": collections.defaultdict(lambda: None),
                "gpio_hist": [],
            }
        )

        @classmethod
        def _validate_pin(cls, pin_num: int) -> None:
            if pin_num not in cls.VALID_PINS:
                raise ValueError(f"Pin {pin_num} is not a valid GPIO pin number")

        @classmethod
        def get_state(cls) -> dict[str, Any]:
            # NOTE: Pytest を並列実行できるようにする
            worker = os.environ.get("PYTEST_XDIST_WORKER", "")
            return cls.state[worker]

        @staticmethod
        def setmode(mode: int) -> None:
            return

        @classmethod
        def setup(cls, pin_num: int, direction: int) -> None:
            cls._validate_pin(pin_num)

        @classmethod
        def hist_get(cls) -> list[dict[str, Any]]:
            return cls.get_state()["gpio_hist"]

        @classmethod
        def hist_clear(cls) -> None:
            cls.get_state()["state"] = collections.defaultdict(lambda: None)
            cls.get_state()["time_start"] = collections.defaultdict(lambda: None)
            cls.get_state()["time_stop"] = collections.defaultdict(lambda: None)
            cls.get_state()["gpio_hist"] = []

        @classmethod
        def hist_add(cls, hist: dict[str, Any]) -> None:
            cls.get_state()["gpio_hist"].append(hist)

        @classmethod
        def output(cls, pin_num: int, value: int) -> None:
            cls._validate_pin(pin_num)
            logging.debug("set gpio.output = %s", value)
            if value == 0:
                if cls.get_state()["time_start"][pin_num] is not None:
                    cls.hist_add(
                        {
                            "pin_num": pin_num,
                            "state": cls.level.LOW.name,  # type: ignore[attr-defined]
                            "high_period": max(int(gpio_time() - cls.get_state()["time_start"][pin_num]), 1),
                        }
                    )
                else:
                    cls.hist_add({"pin_num": pin_num, "state": cls.level.LOW.name})  # type: ignore[attr-defined]
                cls.get_state()["time_start"][pin_num] = None
                cls.get_state()["time_stop"][pin_num] = gpio_time()
            else:
                cls.get_state()["time_start"][pin_num] = gpio_time()
                cls.get_state()["time_stop"][pin_num] = None
                cls.hist_add(
                    {
                        "pin_num": pin_num,
                        "state": cls.level.HIGH.name,  # type: ignore[attr-defined]
                    }
                )

            cls.get_state()["state"][pin_num] = value

        @classmethod
        def input(cls, pin_num: int) -> int | None:
            cls._validate_pin(pin_num)
            return cls.get_state()["state"][pin_num]

        @staticmethod
        def setwarnings(warnings: bool) -> None:
            return

        @staticmethod
        def cleanup(chanlist: list[int] | None = None) -> None:
            return

    gpio = _DummyGPIO


gpio.level = enum.Enum("level", {"HIGH": 1, "LOW": 0})  # type: ignore[misc]
