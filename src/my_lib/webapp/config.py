#!/usr/bin/env python3
from __future__ import annotations

import logging
import os
import pathlib
from dataclasses import dataclass
from typing import Any, Self

import flask


def _resolve_path(value: str | pathlib.Path) -> pathlib.Path:
    return pathlib.Path(value).resolve()


@dataclass(frozen=True)
class WebappDataConfig:
    """Runtime data paths for a web application."""

    schedule_file_path: pathlib.Path | None = None
    log_file_path: pathlib.Path | None = None
    stat_dir_path: pathlib.Path | None = None

    @classmethod
    def parse(cls, data: dict[str, Any]) -> Self:
        return cls(
            schedule_file_path=_resolve_path(data["schedule_file_path"])
            if "schedule_file_path" in data
            else None,
            log_file_path=_resolve_path(data["log_file_path"]) if "log_file_path" in data else None,
            stat_dir_path=_resolve_path(data["stat_dir_path"]) if "stat_dir_path" in data else None,
        )


@dataclass(frozen=True)
class WebappConfig:
    """Parsed webapp configuration."""

    static_dir_path: pathlib.Path
    data: WebappDataConfig | None = None
    external_url: str | None = None

    @classmethod
    def parse(cls, data: dict[str, Any]) -> Self:
        return cls(
            static_dir_path=_resolve_path(data["static_dir_path"]),
            data=WebappDataConfig.parse(data["data"]) if "data" in data else None,
            external_url=data.get("external_url"),
        )


@dataclass(frozen=True)
class WebappEnvironment:
    """Concrete runtime environment for a web application."""

    url_prefix: str | None
    static_dir_path: pathlib.Path
    schedule_file_path: pathlib.Path | None = None
    log_file_path: pathlib.Path | None = None
    stat_dir_path: pathlib.Path | None = None


def build_environment(config: WebappConfig, *, url_prefix: str | None = None) -> WebappEnvironment:
    data = config.data
    environment = WebappEnvironment(
        url_prefix=url_prefix,
        static_dir_path=config.static_dir_path,
        schedule_file_path=data.schedule_file_path if data is not None else None,
        log_file_path=data.log_file_path if data is not None else None,
        stat_dir_path=data.stat_dir_path if data is not None else None,
    )
    logging.info("static_dir_path = %s", environment.static_dir_path)
    logging.info("schedule_file_path = %s", environment.schedule_file_path)
    logging.info("log_file_path = %s", environment.log_file_path)
    logging.info("stat_dir_path = %s", environment.stat_dir_path)
    return environment


def show_handler_list(app: flask.Flask, is_force: bool = False) -> None:
    if (os.environ.get("WERKZEUG_RUN_MAIN") != "true") and not is_force:
        return

    with app.app_context():
        for rule in app.url_map.iter_rules():
            logging.info("path: %s %s → %s", rule.rule, rule.methods, rule.endpoint)
