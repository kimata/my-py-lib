#!/usr/bin/env python3
"""
オブジェクトをシリアライズします。

Usage:
  serializer.py [-D]

Options:
  -D                : デバッグモードで動作します。
"""

from __future__ import annotations

import logging
import os
import pathlib
import pickle
import shutil
import tempfile
from typing import Any, TypeVar, overload

import my_lib.pytest_util

T = TypeVar("T")


def store(path_str: str | pathlib.Path, data: Any) -> None:
    logging.debug("Store %s", path_str)

    path = my_lib.pytest_util.get_path(path_str)
    path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.NamedTemporaryFile("wb", dir=str(path.parent), delete=False) as f:
        pickle.dump(data, f, protocol=pickle.HIGHEST_PROTOCOL)
        f.flush()
        os.fsync(f.fileno())
        temp_name = f.name

    if path.exists():
        old_path = path.with_suffix(".old")

        shutil.copy(path, old_path)

    pathlib.Path(temp_name).replace(path)


@overload
def load(path_str: str | pathlib.Path, init_value: None = None) -> dict[str, Any]: ...


@overload
def load(path_str: str | pathlib.Path, init_value: T) -> T: ...


def load(path_str: str | pathlib.Path, init_value: T | None = None) -> T | dict[str, Any]:
    """シリアライズされたデータを読み込む。

    Args:
        path_str: 読み込むファイルのパス
        init_value: ファイルが存在しない場合に返すデフォルト値。
                    None の場合は空の dict を返す。
                    dict の場合は、保存されたデータをマージして返す。

    Returns:
        init_value が None の場合: dict[str, Any]
        init_value が指定された場合: init_value と同じ型
    """
    logging.debug("Load %s", path_str)

    path = my_lib.pytest_util.get_path(path_str)
    if not path.exists():
        return {} if init_value is None else init_value

    with path.open("rb") as f:
        if isinstance(init_value, dict):
            # NOTE: dict の場合は、プログラムの更新でキーが追加された場合にも自動的に追従させる
            data: dict[str, Any] = init_value.copy()
            data.update(pickle.load(f))  # noqa: S301
            return data
        else:
            return pickle.load(f)  # noqa: S301


def get_size_str(path_str: str | pathlib.Path) -> str:
    path = my_lib.pytest_util.get_path(path_str)
    size: float = path.stat().st_size

    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size < 1024:
            return f"{size:.2f} {unit}"
        size /= 1024

    # NOTE: ここには来ない
    return "?"


if __name__ == "__main__":
    # TEST Code
    import docopt

    import my_lib.logger

    args = docopt.docopt(__doc__)

    debug_mode = args["-D"]

    my_lib.logger.init("test", level=logging.DEBUG if debug_mode else logging.INFO)

    data = {"a": 1.0}

    with tempfile.NamedTemporaryFile() as f:
        file_path = pathlib.Path(f.name)
        store(file_path, data)
        f.flush()

    assert load(file_path) == data  # noqa: S101

    logging.info("OK")
