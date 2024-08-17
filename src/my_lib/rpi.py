#!/usr/bin/env python3
import logging
import os
import pathlib

# NOTE: freezegun を使ったテスト時に，別スレッドのものも含めて time.time() を mock で
# 置き換えたいので，別名にしておく．
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
    (os.environ.get("DUMMY_MODE", "false") != "true")
    and (os.environ.get("TEST", "false") != "true")
    and is_rasberry_pi()
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
        state = 0
        time_start = None
        time_stop = None
        # NOTE: テスト用
        gpio_hist = []

        @staticmethod
        def setmode(mode):  # noqa: ARG004
            return

        @staticmethod
        def setup(pin_num, direction):  # noqa: ARG004
            return

        @staticmethod
        def hist_get():
            return gpio.gpio_hist

        @staticmethod
        def hist_clear():
            gpio.gpio_hist = []

        @staticmethod
        def hist_add(hist):
            gpio.gpio_hist.append(hist)

        @staticmethod
        def output(pin_num, value):  # noqa: ARG004
            logging.debug("set gpio.output = %s", value)
            if value == 0:
                if gpio.time_start is not None:
                    gpio.hist_add(
                        {
                            "state": "close",
                            "period": int(gpio_time() - gpio.time_start),
                        }
                    )
                else:
                    gpio.hist_add({"state": "close"})
                gpio.time_start = None
                gpio.time_stop = gpio_time()
            else:
                gpio.time_start = gpio_time()
                gpio.time_stop = None
                gpio.hist_add(
                    {
                        "state": "open",
                    }
                )

            gpio.state = value

        @staticmethod
        def input(pin_num):  # noqa: ARG004
            return gpio.state

        @staticmethod
        def setwarnings(warnings):  # noqa: ARG004
            return
