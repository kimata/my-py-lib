#!/usr/bin/env python3
"""
タイムゾーンを考慮した時刻を取得します。

Usage:
  time.py [-D]

Options:
  -D                : デバッグモードで動作します。
"""

from __future__ import annotations

import datetime
import os
import zoneinfo

import pytz

TIMEZONE_DEFAULT: str = "Asia/Tokyo"


def get_tz() -> str:
    return os.environ.get("TZ", TIMEZONE_DEFAULT)


def get_zoneinfo() -> zoneinfo.ZoneInfo:
    return zoneinfo.ZoneInfo(get_tz())


def get_pytz() -> pytz.BaseTzInfo:
    return pytz.timezone(get_tz())


def now() -> datetime.datetime:
    return datetime.datetime.now(get_zoneinfo())


if __name__ == "__main__":
    # TEST Code

    import logging

    import docopt

    import my_lib.config
    import my_lib.logger

    assert __doc__ is not None  # noqa: S101
    args = docopt.docopt(__doc__)

    debug_mode = args["-D"]

    my_lib.logger.init("test", level=logging.DEBUG if debug_mode else logging.INFO)

    logging.info(now())
