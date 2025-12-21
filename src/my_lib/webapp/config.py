#!/usr/bin/env python3
from __future__ import annotations

import logging
import os
import pathlib
from typing import Any

import flask

import my_lib.time

URL_PREFIX: str | None = None

ZONEINFO = my_lib.time.get_zoneinfo()
PYTZ = my_lib.time.get_pytz()

STATIC_DIR_PATH: pathlib.Path | None = None

SCHEDULE_FILE_PATH: pathlib.Path | None = None
LOG_DIR_PATH: pathlib.Path | None = None
STAT_DIR_PATH: pathlib.Path | None = None


def init(config: dict[str, Any]) -> None:
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


def show_handler_list(app: flask.Flask, is_force: bool = False) -> None:
    if (os.environ.get("WERKZEUG_RUN_MAIN") != "true") and not is_force:
        return

    with app.app_context():
        for rule in app.url_map.iter_rules():
            logging.info("path: %s %s → %s", rule.rule, rule.methods, rule.endpoint)
