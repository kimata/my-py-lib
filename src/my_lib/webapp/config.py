#!/usr/bin/env python3
from __future__ import annotations

import logging
import os
import pathlib
from dataclasses import dataclass
from typing import Any, Self

import flask

import my_lib.time

URL_PREFIX: str | None = None

ZONEINFO = my_lib.time.get_zoneinfo()
PYTZ = my_lib.time.get_pytz()

STATIC_DIR_PATH: pathlib.Path | None = None

SCHEDULE_FILE_PATH: pathlib.Path | None = None
LOG_DIR_PATH: pathlib.Path | None = None
STAT_DIR_PATH: pathlib.Path | None = None


@dataclass(frozen=True)
class WebappDataConfig:
    """webapp.data セクションの設定"""

    schedule_file_path: pathlib.Path | None = None
    log_file_path: pathlib.Path | None = None
    stat_dir_path: pathlib.Path | None = None

    @classmethod
    def parse(cls, data: dict[str, Any]) -> Self:
        return cls(
            schedule_file_path=pathlib.Path(data["schedule_file_path"]).resolve()
            if "schedule_file_path" in data
            else None,
            log_file_path=pathlib.Path(data["log_file_path"]).resolve() if "log_file_path" in data else None,
            stat_dir_path=pathlib.Path(data["stat_dir_path"]).resolve() if "stat_dir_path" in data else None,
        )


@dataclass(frozen=True)
class WebappConfig:
    """webapp セクションの設定"""

    static_dir_path: pathlib.Path | None = None
    data: WebappDataConfig | None = None

    @classmethod
    def parse(cls, data: dict[str, Any]) -> Self:
        return cls(
            static_dir_path=(
                pathlib.Path(data["static_dir_path"]).resolve() if "static_dir_path" in data else None
            ),
            data=WebappDataConfig.parse(data["data"]) if "data" in data else None,
        )


def init(config: WebappConfig) -> None:
    global STATIC_DIR_PATH
    global SCHEDULE_FILE_PATH
    global LOG_DIR_PATH
    global STAT_DIR_PATH

    STATIC_DIR_PATH = config.static_dir_path

    if config.data is not None:
        SCHEDULE_FILE_PATH = config.data.schedule_file_path
        LOG_DIR_PATH = config.data.log_file_path
        STAT_DIR_PATH = config.data.stat_dir_path

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
