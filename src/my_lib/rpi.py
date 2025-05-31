#!/usr/bin/env python3
import collections
import enum
import logging
import os
import pathlib

# NOTE: time_machine を使ったテスト時に、別スレッドのものも含めて time.time() を mock で
# 置き換えたいので、別名にしておく。
from time import time as gpio_time


def is_rasberry_pi():
    try:
        with pathlib.Path.open("/proc/cpuinfo") as f:
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


if (
    is_rasberry_pi()
    and (os.environ.get("DUMMY_MODE", "false") != "true")
    and (os.environ.get("TEST", "false") != "true")
):  # pragma: no cover
    from RPi import GPIO as gpio  # noqa: N811
else:
    if os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        logging.warning("Using dummy GPIO")

    # NOTE: 本物の GPIO のように振る舞うダミーのライブラリ
    class gpio:  # noqa: N801
        IS_DUMMY = True
        BCM = 0
        OUT = 0

        state = collections.defaultdict(
            lambda: {
                "state": collections.defaultdict(lambda: None),
                "time_start": collections.defaultdict(lambda: None),
                "time_stop": collections.defaultdict(lambda: None),
                "gpio_hist": [],
            }
        )

        def get_state():
            # NOTE: Pytest を並列実行できるようにする
            worker = os.environ.get("PYTEST_XDIST_WORKER", "")
            return gpio.state[worker]

        @staticmethod
        def setmode(mode):  # noqa: ARG004
            return

        @staticmethod
        def setup(pin_num, direction):  # noqa: ARG004
            return

        @staticmethod
        def hist_get():
            return gpio.get_state()["gpio_hist"]

        @staticmethod
        def hist_clear():
            gpio.get_state()["state"] = collections.defaultdict(lambda: None)
            gpio.get_state()["time_start"] = collections.defaultdict(lambda: None)
            gpio.get_state()["time_stop"] = collections.defaultdict(lambda: None)
            gpio.get_state()["gpio_hist"] = []

        @staticmethod
        def hist_add(hist):
            gpio.get_state()["gpio_hist"].append(hist)

        @staticmethod
        def output(pin_num, value):
            logging.debug("set gpio.output = %s", value)
            if value == 0:
                if gpio.get_state()["time_start"][pin_num] is not None:
                    gpio.hist_add(
                        {
                            "pin_num": pin_num,
                            "state": gpio.level.LOW.name,
                            "high_period": max(int(gpio_time() - gpio.get_state()["time_start"][pin_num]), 1),
                        }
                    )
                else:
                    gpio.hist_add({"pin_num": pin_num, "state": gpio.level.LOW.name})
                gpio.get_state()["time_start"][pin_num] = None
                gpio.get_state()["time_stop"][pin_num] = gpio_time()
            else:
                gpio.get_state()["time_start"][pin_num] = gpio_time()
                gpio.get_state()["time_stop"][pin_num] = None
                gpio.hist_add(
                    {
                        "pin_num": pin_num,
                        "state": gpio.level.HIGH.name,
                    }
                )

            gpio.get_state()["state"][pin_num] = value

        @staticmethod
        def input(pin_num):
            return gpio.get_state()["state"][pin_num]

        @staticmethod
        def setwarnings(warnings):  # noqa: ARG004
            return

        @staticmethod
        def cleanup(chanlist=None):  # noqa: ARG004
            return


gpio.level = enum.Enum("gpio.level", {"HIGH": 1, "LOW": 0})
