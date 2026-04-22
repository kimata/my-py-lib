#!/usr/bin/env python3
"""
KEYENCE のクランプオン式流量センサ FD-Q10C と IO-LINK で通信を行なって流量を取得するスクリプトです。

Usage:
  fd_q10c.py [-l LOCK] [-D]

Options:
  -l LOCK           : ロックファイル。 [default: /dev/shm/fd_q10c.lock]
  -D                : デバッグモードで動作します。
"""

from __future__ import annotations

import fcntl
import logging
import os
import pathlib
import time
from types import TracebackType
from typing import Any

import my_lib.sensor.ltc2874 as driver


class Lock:
    LOCK_FILE: str = "/dev/shm/fd_q10c.lock"  # noqa: S108
    TIMEOUT: int = 5

    def __init__(self) -> None:
        self.lock_file: str = str(Lock.get_file_path())
        self.lock_fd: int | None = None

    def __enter__(self) -> bool:
        self.lock_fd = os.open(self.lock_file, os.O_RDWR | os.O_CREAT | os.O_TRUNC)

        time_start = time.time()
        while time.time() < time_start + Lock.TIMEOUT:
            try:
                fcntl.flock(self.lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                logging.exception("ロック取得に失敗")
            else:
                return True
            time.sleep(0.5)

        os.close(self.lock_fd)
        self.lock_fd = None

        raise RuntimeError(f"ロック取得がタイムアウト: {self.lock_file}")

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self.lock_fd is None:
            raise RuntimeError("Not Locked")

        fcntl.flock(self.lock_fd, fcntl.LOCK_UN)
        os.close(self.lock_fd)

        self.lock_fd = None

    # NOTE: Pytest の並列実行ができるようにする
    @staticmethod
    def get_file_path() -> pathlib.Path:
        suffix = os.environ.get("PYTEST_XDIST_WORKER", None)
        path = pathlib.Path(Lock.LOCK_FILE)

        if suffix is None:
            return path
        else:
            return path.with_name(path.name + "." + suffix)


class FD_Q10C:
    NAME: str = "FD_Q10C"
    TYPE: str = "IO_LINK"

    def __init__(self) -> None:
        self.dev_addr: int | None = None

    def ping(self) -> bool:
        try:
            return self.read_param(0x12, driver.DATA_TYPE_STRING)[0:4] == "FD-Q"
        except Exception:
            logging.warning("FD_Q10C の ping が失敗。LTC2874 をリセットして再試行")

        # NOTE: 通信が wedge した状態から復旧させるため、チップを hard reset してから再試行
        self._reset()

        try:
            return self.read_param(0x12, driver.DATA_TYPE_STRING)[0:4] == "FD-Q"
        except Exception:
            return False

    def get_value(self, force_power_on: bool = True) -> float:
        raw = self.read_param(0x94, driver.DATA_TYPE_UINT16, force_power_on)

        if raw is None:
            raise RuntimeError("センサーが電源 OFF 状態かつ force_power_on=False")

        return round(raw * 0.01, 2)

    def get_state(self) -> bool:
        with Lock():
            spi = None
            try:
                spi = driver.com_open()
                # NOTE: 電源 ON なら True
                return driver.com_status(spi)
            except Exception:
                logging.exception("電源状態の取得に失敗")
                return False
            finally:
                if spi is not None:
                    driver.com_close(spi)

    def read_param(self, index: int, data_type: int, force_power_on: bool = True) -> Any:
        with Lock():
            spi = None
            ser = None
            try:
                spi = driver.com_open()

                if force_power_on or driver.com_status(spi):
                    ser = driver.com_start(spi)
                    value = driver.isdu_read(spi, ser, index, data_type)
                else:
                    logging.info("センサーが電源 OFF 状態のためスキップ")
                    value = None
                return value
            finally:
                # NOTE: 例外時も drive disable と serial close を確実に行うため finally で後始末
                if spi is not None:
                    try:
                        driver.com_stop(spi, ser)
                    except Exception:
                        logging.exception("com_stop で例外 (cleanup 続行)")
                    driver.com_close(spi)

    def _reset(self) -> None:
        """LTC2874 をチップリセットし IO-Link 電源も OFF する。通信が wedge した際の復旧用。"""
        with Lock():
            spi = None
            try:
                spi = driver.com_open()
            except Exception:
                logging.exception("SPI オープンに失敗")
                return
            try:
                driver.com_stop(spi, is_power_off=True)
            except Exception:
                logging.exception("com_stop で例外 (リセット処理続行)")
            finally:
                driver.com_close(spi, is_reset=True)

    def stop(self) -> None:
        self._reset()

    def get_value_map(self, force_power_on: bool = True) -> dict[str, float]:
        value = self.get_value(force_power_on)

        return {"flow": value}


if __name__ == "__main__":
    # TEST Code
    import docopt

    import my_lib.logger

    assert __doc__ is not None  # noqa: S101
    args = docopt.docopt(__doc__)
    lock_file = args["-l"]
    debug_mode = args["-D"]

    my_lib.logger.init("test", level=logging.DEBUG if debug_mode else logging.INFO)

    sensor = FD_Q10C()

    ping = sensor.ping()
    logging.info("PING: %s", ping)
    if ping:
        logging.info("VALUE: %s", sensor.get_value_map())
