#!/usr/bin/env python3
import datetime
import pathlib

import pytz

URL_PREFIX = None

TIMEZONE_OFFSET = "+9"
TIMEZONE = datetime.timezone(datetime.timedelta(hours=int(TIMEZONE_OFFSET)), "JST")
TIMEZONE_PYTZ = pytz.timezone("Asia/Tokyo")

STATIC_DIR_PATH = None

SCHEDULE_FILE_PATH = None
LOG_DIR_PATH = None
STAT_FILE_PATH = None


def init(config):  # noqa: C901
    global URL_PREFIX  # noqa: PLW0603
    global TIMEZONE_OFFSET  # noqa: PLW0603
    global TIMEZONE  # noqa: PLW0603
    global TIMEZONE_PYTZ  # noqa: PLW0603
    global STATIC_DIR_PATH  # noqa: PLW0603
    global SCHEDULE_FILE_PATH  # noqa: PLW0603
    global LOG_DIR_PATH  # noqa: PLW0603
    global STAT_FILE_PATH  # noqa: PLW0603

    if "url_prefix" in config["webapp"]:
        URL_PREFIX = config["webapp"]["url_prefix"]

    if "timezone" in config["webapp"]:
        if "offset" in config["webapp"]["timezone"]:
            TIMEZONE_OFFSET = config["webapp"]["timezone"]["offset"]
            if "name" in config["webapp"]["timezone"]:
                TIMEZONE = datetime.timezone(
                    datetime.timedelta(hours=int(TIMEZONE_OFFSET)), config["webapp"]["timezone"]["name"]
                )
            else:
                TIMEZONE = datetime.timezone(datetime.timedelta(hours=int(TIMEZONE_OFFSET)), "UNKOWN")
        if "zone" in config["webapp"]["timezone"]:
            TIMEZONE_PYTZ = pytz.timezone(config["webapp"]["timezone"]["zone"])

    if "static_dir_path" in config["webapp"]:
        STATIC_DIR_PATH = pathlib.Path(config["webapp"]["static_dir_path"]).resolve()

    if "data" in config["webapp"]:
        if "schedule_file_path" in config["webapp"]["data"]:
            SCHEDULE_FILE_PATH = pathlib.Path(config["webapp"]["data"]["schedule_file_path"]).resolve()
        if "log_file_path" in config["webapp"]["data"]:
            LOG_DIR_PATH = pathlib.Path(config["webapp"]["data"]["log_file_path"]).resolve()

    if "healthz" in config["webapp"]:  # noqa: SIM102
        if "file_path" in config["webapp"]["healthz"]:
            STAT_FILE_PATH = config["webapp"]["healthz"]["file_path"]