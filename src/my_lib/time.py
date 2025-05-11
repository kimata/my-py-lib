#!/usr/bin/env python3
"""
タイムゾーンを考慮した時刻を取得します．

Usage:
  time.py [-D]

Options:
  -D                : デバッグモードで動作します．
"""

import datetime
import os

import zoneinfo

TIMEZONE_DEFAULT = "Asia/Tokyo"


def now():
    return datetime.datetime.now(zoneinfo.ZoneInfo(os.environ.get("TZ", TIMEZONE_DEFAULT)))


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
