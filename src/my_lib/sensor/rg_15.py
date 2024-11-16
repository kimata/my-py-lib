#!/usr/bin/env python3
"""
RG-15 を使って電圧を計測するライブラリです．

Usage:
  rg_15.py [-d DEV]

Options:
  -d DEV        : シリアルポート． [default: /dev/ttyAMA0]
"""

import logging
import re
import time

import serial


class RG_15:  # noqa: N801
    NAME = "RG_15"
    TYPE = "UART"
    DEV = "/dev/ttyAMA0"
    BAUDRATE = 9600

    RAIN_START_INTERVAL_SEC = 30
    RAIN_START_ACC_SUM = 0.04
    RAIN_STOP_INTERVAL_SEC = 120

    def __init__(self, dev=DEV):  # noqa: D107
        self.dev = dev
        self.ser = serial.Serial(self.dev, self.BAUDRATE, timeout=2)
        self.sum_by_minute = {}
        self.event = {
            "fall_sum": 0,
            "fall_time_last": None,
            "fall_time_start": None,
            "fall_stop": True,
            "fall_start": False,
        }

    def update_stat(self, data):
        minute = int(time.time() / 60)

        if data["acc"] == 0:
            if (not self.event["fall_stop"]) and (
                (time.time() - self.event["fall_time_last"]) > self.RAIN_STOP_INTERVAL_SEC
            ):
                self.ser.write("O\r\n".encode(encoding="utf-8"))
                self.ser.flush()

                self.event["fall_stop"] = True
                self.event["fall_start"] = False
                self.event["fall_time_start"] = None
                self.event["fall_sum"] = 0
        else:
            self.event["fall_time_last"] = time.time()
            self.event["fall_sum"] += data["acc"]

            if minute in self.sum_by_minute:
                self.sum_by_minute[minute] += data["acc"]
            else:
                self.sum_by_minute[minute] = data["acc"]

            if self.event["fall_time_start"] is None:
                self.event["fall_time_start"] = time.time()

            if (
                (not self.event["fall_start"])
                and ((time.time() - self.event["fall_time_start"]) > self.RAIN_START_INTERVAL_SEC)
                and (self.event["fall_sum"] >= self.RAIN_START_ACC_SUM)
            ):
                self.event["fall_start"] = True
                self.event["fall_stop"] = False
                self.event["fall_time_stop"] = None

        # NOTE: 直前の1分間降水量を返す
        rain = self.sum_by_minute.get(minute - 1, 0.0)

        return [rain, self.event["fall_start"]]

    def ping(self):
        try:
            self.ser.write("P\r\n".encode(encoding="utf-8"))
            self.ser.flush()

            res = self.ser.read(1).decode(encoding="utf-8")

            return res == "p"
        except Exception:
            return False

    def get_value(self):
        self.ser.write("R\r\n".encode(encoding="utf-8"))
        self.ser.flush()

        res = self.ser.read(100).decode(encoding="utf-8").strip()

        logging.debug(res)

        data = {
            label.lower(): float(value)
            for label, value in re.findall(r"(Acc|EventAcc|TotalAcc|RInt)\s+(\d+\.\d+)", res)
        }

        logging.info(data)

        return self.update_stat(data)

    def get_value_map(self):
        value = self.get_value()

        return {"rain": value[0], "raining": value[1]}


if __name__ == "__main__":
    # TEST Code
    import docopt
    import my_lib.logger
    import my_lib.sensor.rg_15

    args = docopt.docopt(__doc__)
    dev = args["-d"]

    my_lib.logger.init("test", level=logging.DEBUG)

    sensor = my_lib.sensor.rg_15(dev=dev)

    ping = sensor.ping()
    logging.info("PING: %s", ping)
    if ping:
        while True:
            logging.info("VALUE: %s", sensor.get_value_map())
            time.sleep(5)
