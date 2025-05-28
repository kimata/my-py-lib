#!/usr/bin/env python3
"""
KEYENCE のクランプオン式流量センサ FD-Q10C と IO-LINK で通信を行なって流量を取得するスクリプトです。

Usage:
  fd_q10c.py [-l LOCK] [-t TIMEOUT] [-D]

Options:
  -l LOCK           : ロックファイル。 [default: /dev/shm/fd_q10c.lock]
  -t TIMEOUT        : タイムアウト時間。 [default: 5]
  -D                : デバッグモードで動作します。
"""

import fcntl
import logging
import os
import time
import traceback

import my_lib.sensor.ltc2874 as driver


class FD_Q10C:  # noqa: N801
    NAME = "FD_Q10C"
    TYPE = "IO_LINK"
    LOCK_FILE = "/dev/shm/fd_q10c.lock"  # noqa: S108
    TIMEOUT = 5

    def __init__(self, lock_file=LOCK_FILE, timeout=TIMEOUT):  # noqa:D107
        self.dev_addr = None
        self.lock_file = lock_file
        self.lock_fd = None
        self.timeout = timeout

    def ping(self):
        try:
            return self.read_param(0x12, driver.DATA_TYPE_STRING)[0:4] == "FD-Q"
        except Exception:
            return False

    def get_value(self, force_power_on=True):
        try:
            raw = self.read_param(0x94, driver.DATA_TYPE_UINT16, force_power_on)

            if raw is None:
                return None
            else:
                return round(raw * 0.01, 2)
        except Exception:
            try:
                self.stop()
            except Exception:
                logging.debug("Failed to stop")

            logging.warning(traceback.format_exc())
            return None

    def get_state(self):
        if not self._acquire():
            raise RuntimeError("Unable to acquire the lock.")  # noqa: EM101, TRY003

        try:
            spi = driver.com_open()
            # NOTE: 電源 ON なら True
            return driver.com_status(spi)
        except Exception:
            logging.exception("Failed to get power status")
            return False
        finally:
            driver.com_close(spi)
            self._release()

    def read_param(self, index, data_type, force_power_on=True):
        if not self._acquire():
            raise RuntimeError("Unable to acquire the lock.")  # noqa: EM101, TRY003

        try:
            spi = driver.com_open()

            if force_power_on or driver.com_status(spi):
                ser = driver.com_start(spi)

                value = driver.isdu_read(spi, ser, index, data_type)

                driver.com_stop(spi, ser)
            else:
                logging.info("Sensor is powered OFF.")
                value = None
            return value
        finally:
            driver.com_close(spi)
            self._release()

    def stop(self):
        if not self._acquire():
            raise RuntimeError("Unable to acquire the lock.")  # noqa: EM101, TRY003

        spi = None
        try:
            spi = driver.com_open()

            driver.com_stop(spi, is_power_off=True)
            driver.com_close(spi, is_reset=True)
        except Exception:
            if spi is not None:
                driver.com_close(spi, is_reset=True)
                raise
        finally:
            self._release()

    def _acquire(self):
        self.lock_fd = os.open(self.lock_file, os.O_RDWR | os.O_CREAT | os.O_TRUNC)

        time_start = time.time()
        while time.time() < time_start + self.timeout:
            try:
                fcntl.flock(self.lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                pass
            else:
                return True
            time.sleep(0.5)

        os.close(self.lock_fd)
        self.lock_fd = None

        return False

    def _release(self):
        if self.lock_fd is None:
            raise RuntimeError("Not Locked")  # noqa: EM101, TRY003

        fcntl.flock(self.lock_fd, fcntl.LOCK_UN)
        os.close(self.lock_fd)

        self.lock_fd = None

    def get_value_map(self, force_power_on=True):
        value = self.get_value(force_power_on)

        return {"flow": value}


if __name__ == "__main__":
    # TEST Code
    import docopt
    import my_lib.logger

    args = docopt.docopt(__doc__)
    lock_file = args["-l"]
    timeout = int(args["-t"], 0)
    debug_mode = args["-D"]

    my_lib.logger.init("test", level=logging.DEBUG if debug_mode else logging.INFO)

    sensor = my_lib.sensor.fd_q10c(lock_file, timeout)

    ping = sensor.ping()
    logging.info("PING: %s", ping)
    if ping:
        logging.info("VALUE: %s", sensor.get_value_map())
