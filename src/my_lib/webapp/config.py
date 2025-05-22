#!/usr/bin/env python3
import logging
import pathlib

import my_lib.time

URL_PREFIX = None

ZONEINFO = my_lib.time.get_zoneinfo()
PYTZ = my_lib.time.get_pytz()

STATIC_DIR_PATH = None

SCHEDULE_FILE_PATH = None
LOG_DIR_PATH = None
STAT_DIR_PATH = None


def init(config):
    global STATIC_DIR_PATH  # noqa: PLW0603
    global SCHEDULE_FILE_PATH  # noqa: PLW0603
    global LOG_DIR_PATH  # noqa: PLW0603
    global STAT_DIR_PATH  # noqa: PLW0603

    if "static_dir_path" in config["webapp"]:
        STATIC_DIR_PATH = pathlib.Path(config["webapp"]["static_dir_path"]).resolve()

    if "data" in config["webapp"]:
        if "schedule_file_path" in config["webapp"]["data"]:
            SCHEDULE_FILE_PATH = pathlib.Path(config["webapp"]["data"]["schedule_file_path"]).resolve()
        if "log_file_path" in config["webapp"]["data"]:
            LOG_DIR_PATH = pathlib.Path(config["webapp"]["data"]["log_file_path"]).resolve()
        if "stat_dir_path" in config["webapp"]["data"]:
            STAT_DIR_PATH = pathlib.Path(config["webapp"]["data"]["stat_dir_path"]).resolve()

    logging.info("STATIC_DIR_PATH = %s", STATIC_DIR_PATH)
    logging.info("SCHEDULE_FILE_PATH = %s", SCHEDULE_FILE_PATH)
    logging.info("LOG_DIR_PATH = %s", LOG_DIR_PATH)
    logging.info("STAT_DIR_PATH = %s", STAT_DIR_PATH)
