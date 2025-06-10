#!/usr/bin/env python3
"""
オブジェクトをシリアライズします。

Usage:
  serializer.py [-D]

Options:
  -D                : デバッグモードで動作します。
"""

import logging
import pathlib
import pickle
import shutil
import tempfile

import my_lib.pytest_util


def store(path_str, data):
    logging.debug("Store %s", path_str)

    path = my_lib.pytest_util.get_path(path_str)
    path.parent.mkdir(parents=True, exist_ok=True)

    f = tempfile.NamedTemporaryFile("wb", dir=str(path.parent), delete=False)
    pickle.dump(data, f, protocol=pickle.HIGHEST_PROTOCOL)
    f.close()

    if file_path.exists():
        old_path = file_path.with_suffix(".old")

        shutil.copy(file_path, old_path)

    pathlib.Path(f.name).replace(file_path)


def load(path_str, init_value=None):
    logging.debug("Load %s", file_path)

    path = my_lib.pytest_util.get_path(path_str)
    if not path.exists():
        return {} if init_value is None else init_value

    with path.open("rb") as f:
        if isinstance(init_value, dict):
            # NOTE: dict の場合は、プログラムの更新でキーが追加された場合にも自動的に追従させる
            data = init_value.copy()
            data.update(pickle.load(f))  # noqa: S301
            return data
        else:
            return pickle.load(f)  # noqa: S301


def get_size_str(path_str):
    path = my_lib.pytest_util.get_path(path_str)
    size = path.stat().st_size

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

    f = tempfile.NamedTemporaryFile()
    file_path = pathlib.Path(f.name)
    store(file_path, data)
    f.flush()

    assert load(file_path) == data  # noqa: S101

    logging.info("OK")
