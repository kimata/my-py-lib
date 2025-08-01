#!/usr/bin/env python3
"""
タイムゾーンを考慮した時刻を取得します。

Usage:
  time.py [-D]

Options:
  -D                : デバッグモードで動作します。
"""

import datetime
import os
import zoneinfo

import pytz

TIMEZONE_DEFAULT = "Asia/Tokyo"


def get_tz():
    return os.environ.get("TZ", TIMEZONE_DEFAULT)


def get_zoneinfo():
    return zoneinfo.ZoneInfo(get_tz())


def get_pytz():
    return pytz.timezone(get_tz())


def now():
    return datetime.datetime.now(get_zoneinfo())


if __name__ == "__main__":
    # TEST Code

    import logging

    import docopt

    import my_lib.config
    import my_lib.logger

    args = docopt.docopt(__doc__)

    debug_mode = args["-D"]

    my_lib.logger.init("test", level=logging.DEBUG if debug_mode else logging.INFO)

    logging.info(now())
