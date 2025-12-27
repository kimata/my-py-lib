#!/usr/bin/env python3
from __future__ import annotations

import collections
import enum
import logging
import os
import pathlib
from typing import Any

# NOTE: time_machine を使ったテスト時に、別スレッドのものも含めて time.time() を mock で
# 置き換えたいので、別名にしておく。
from time import time as gpio_time


def is_rasberry_pi() -> bool:
    try:
        with pathlib.Path.open(pathlib.Path("/proc/cpuinfo")) as f:
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
    from RPi import GPIO as gpio  # type: ignore[assignment]  # noqa: N811
else:
    if os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        logging.warning("Using dummy GPIO")

    # NOTE: 本物の GPIO のように振る舞うダミーのライブラリ
    class gpio:  # type: ignore[no-redef]  # noqa: N801
        IS_DUMMY: bool = True
        BCM: int = 0
        OUT: int = 0

        # Valid GPIO pin numbers for Raspberry Pi (BCM mode)
        VALID_PINS: set[int] = set(range(28))

        state: dict[str, dict[str, Any]] = collections.defaultdict(
            lambda: {
                "state": collections.defaultdict(lambda: None),
                "time_start": collections.defaultdict(lambda: None),
                "time_stop": collections.defaultdict(lambda: None),
                "gpio_hist": [],
            }
        )

        @staticmethod
        def _validate_pin(pin_num: int) -> None:
            if pin_num not in gpio.VALID_PINS:
                raise ValueError(f"Pin {pin_num} is not a valid GPIO pin number")

        @staticmethod
        def get_state() -> dict[str, Any]:
            # NOTE: Pytest を並列実行できるようにする
            worker = os.environ.get("PYTEST_XDIST_WORKER", "")
            return gpio.state[worker]

        @staticmethod
        def setmode(mode: int) -> None:  # noqa: ARG004
            return

        @staticmethod
        def setup(pin_num: int, direction: int) -> None:  # noqa: ARG004
            gpio._validate_pin(pin_num)

        @staticmethod
        def hist_get() -> list[dict[str, Any]]:
            return gpio.get_state()["gpio_hist"]

        @staticmethod
        def hist_clear() -> None:
            gpio.get_state()["state"] = collections.defaultdict(lambda: None)
            gpio.get_state()["time_start"] = collections.defaultdict(lambda: None)
            gpio.get_state()["time_stop"] = collections.defaultdict(lambda: None)
            gpio.get_state()["gpio_hist"] = []

        @staticmethod
        def hist_add(hist: dict[str, Any]) -> None:
            gpio.get_state()["gpio_hist"].append(hist)

        @staticmethod
        def output(pin_num: int, value: int) -> None:
            gpio._validate_pin(pin_num)
            logging.debug("set gpio.output = %s", value)
            if value == 0:
                if gpio.get_state()["time_start"][pin_num] is not None:
                    gpio.hist_add(
                        {
                            "pin_num": pin_num,
                            "state": gpio.level.LOW.name,  # type: ignore[attr-defined]
                            "high_period": max(int(gpio_time() - gpio.get_state()["time_start"][pin_num]), 1),
                        }
                    )
                else:
                    gpio.hist_add({"pin_num": pin_num, "state": gpio.level.LOW.name})  # type: ignore[attr-defined]
                gpio.get_state()["time_start"][pin_num] = None
                gpio.get_state()["time_stop"][pin_num] = gpio_time()
            else:
                gpio.get_state()["time_start"][pin_num] = gpio_time()
                gpio.get_state()["time_stop"][pin_num] = None
                gpio.hist_add(
                    {
                        "pin_num": pin_num,
                        "state": gpio.level.HIGH.name,  # type: ignore[attr-defined]
                    }
                )

            gpio.get_state()["state"][pin_num] = value

        @staticmethod
        def input(pin_num: int) -> int | None:
            gpio._validate_pin(pin_num)
            return gpio.get_state()["state"][pin_num]

        @staticmethod
        def setwarnings(warnings: bool) -> None:  # noqa: ARG004
            return

        @staticmethod
        def cleanup(chanlist: list[int] | None = None) -> None:  # noqa: ARG004
            return


gpio.level = enum.Enum("level", {"HIGH": 1, "LOW": 0})  # type: ignore[misc]
