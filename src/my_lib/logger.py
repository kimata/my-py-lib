#!/usr/bin/env python3
from __future__ import annotations

import bz2
import io
import logging
import logging.handlers
import os
import pathlib
from typing import TYPE_CHECKING

import coloredlogs

if TYPE_CHECKING:
    import queue

MAX_SIZE: int = 10 * 1024 * 1024
ROTATE_COUNT: int = 10

LOG_FORMAT: str = "{name} %(asctime)s %(levelname)s [%(filename)s:%(lineno)s %(funcName)s] %(message)s"
SIMPLE_FORMAT: str = "%(asctime)s %(levelname)s %(message)s"


def _log_formatter(name: str) -> logging.Formatter:
    return logging.Formatter(fmt=LOG_FORMAT.format(name=name), datefmt="%Y-%m-%d %H:%M:%S")


class _GZipRotator:
    @staticmethod
    def namer(name: str) -> str:
        return name + ".bz2"

    @staticmethod
    def rotator(source: str, dest: str) -> None:
        with pathlib.Path(source).open(mode="rb") as fs, bz2.open(dest, "wb") as fd:
            fd.writelines(fs)
        pathlib.Path.unlink(pathlib.Path(source))


def init(
    name: str,
    level: int = logging.WARNING,
    log_dir_path: str | pathlib.Path | None = None,
    log_queue: queue.Queue[logging.LogRecord] | None = None,
    is_str_log: bool = False,
    log_format: str | None = None,
) -> io.StringIO | None:
    # ルートロガーを取得
    root_logger = logging.getLogger()

    # ログフォーマットを決定
    actual_format = log_format if log_format is not None else LOG_FORMAT.format(name=name)

    if os.environ.get("NO_COLORED_LOGS", "false") != "true":
        # docker compose の TTY 環境での二重出力を防ぐため、
        # 既存の StreamHandler を明示的に削除してから coloredlogs をインストール
        root_logger.handlers = [h for h in root_logger.handlers if not isinstance(h, logging.StreamHandler)]
        # isatty=None で自動検出を有効にしつつ、reconfigure で既存のハンドラーを適切に処理
        coloredlogs.install(
            fmt=actual_format,
            level=level,
            reconfigure=True,
            isatty=None,  # 自動検出
        )

    if log_dir_path is not None:
        log_dir_path = pathlib.Path(log_dir_path)
        log_dir_path.mkdir(exist_ok=True, parents=True)

        log_file_path = str(log_dir_path / f"{name}.log")

        logging.info("Log to %s", log_file_path)

        logger = logging.getLogger()
        log_handler = logging.handlers.RotatingFileHandler(
            log_file_path,
            encoding="utf8",
            maxBytes=MAX_SIZE,
            backupCount=ROTATE_COUNT,
        )
        log_handler.formatter = _log_formatter(name)
        log_handler.namer = _GZipRotator.namer
        log_handler.rotator = _GZipRotator.rotator  # type: ignore[assignment]

        logger.addHandler(log_handler)

    if log_queue is not None:
        queue_handler = logging.handlers.QueueHandler(log_queue)
        logging.getLogger().addHandler(queue_handler)

    if is_str_log:
        str_io = io.StringIO()
        stream_handler = logging.StreamHandler(str_io)
        stream_handler.formatter = _log_formatter(name)
        logging.getLogger().addHandler(stream_handler)

        return str_io

    return None


if __name__ == "__main__":
    # TEST Code
    init("test")
    logging.info("Test")
