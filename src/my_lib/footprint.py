#!/usr/bin/env python3
from __future__ import annotations

import logging
import math
import pathlib
import tempfile
import time

import my_lib.pytest_util


def exists(path_str: str | pathlib.Path) -> bool:
    return my_lib.pytest_util.get_path(path_str).exists()


def update(path_str: str | pathlib.Path, mtime: float | None = None) -> None:
    path = my_lib.pytest_util.get_path(path_str)

    if mtime is None:
        mtime = time.time()

    logging.debug("update: %s", path)

    path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.NamedTemporaryFile("w", delete=False, dir=pathlib.Path(path).parent) as tmp_file:
        tmp_file.write(str(mtime))
        temp_file_path = pathlib.Path(tmp_file.name)

    # NOTE: NamedTemporaryFile は 0600 で作られるため、healthz を別ユーザーで
    # 実行する構成でも読めるように 0644 にしてから rename する
    temp_file_path.chmod(0o644)
    temp_file_path.rename(path)


def mtime(path_str: str | pathlib.Path) -> float:
    path = my_lib.pytest_util.get_path(path_str)

    with pathlib.Path(path).open() as f:
        return float(f.read())


def elapsed(path_str: str | pathlib.Path) -> float | None:
    """
    フットプリントファイルの最終更新からの経過秒数を返す.

    Returns:
        正常時は経過秒数（time.time() - mtime）。
        ファイルが存在しない、または内容が破損している場合は None。

    """
    path = my_lib.pytest_util.get_path(path_str)

    if not path.exists():
        return None

    try:
        return time.time() - mtime(path_str)
    except (ValueError, OSError):
        logging.warning("Footprint ファイルの読み取りに失敗（空または破損）: %s", path)
        return None


def compare(path_str_a: str | pathlib.Path, path_str_b: str | pathlib.Path) -> bool:
    """
    2 つのフットプリントを比較し、a が b より新しい場合に True を返す.

    elapsed が None（不在・破損）の場合は無限大に古いとみなす。
    """
    elapsed_a = elapsed(path_str_a)
    elapsed_b = elapsed(path_str_b)

    a = math.inf if elapsed_a is None else elapsed_a
    b = math.inf if elapsed_b is None else elapsed_b
    return a < b


def clear(path_str: str | pathlib.Path) -> None:
    path = my_lib.pytest_util.get_path(path_str)

    logging.debug("clear: %s", path)
    path.unlink(missing_ok=True)
