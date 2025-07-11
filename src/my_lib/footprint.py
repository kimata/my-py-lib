#!/usr/bin/env python3
import logging
import pathlib
import tempfile
import time

import my_lib.pytest_util


def exists(path_str):
    return my_lib.pytest_util.get_path(path_str).exists()


def update(path_str, mtime=None):
    path = my_lib.pytest_util.get_path(path_str)

    if mtime is None:
        mtime = time.time()

    logging.debug("update: %s", path)

    path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.NamedTemporaryFile("w", delete=False, dir=pathlib.Path(path).parent) as tmp_file:
        tmp_file.write(str(mtime))
        temp_file_path = pathlib.Path(tmp_file.name)

    temp_file_path.rename(path)


def mtime(path_str):
    path = my_lib.pytest_util.get_path(path_str)

    with pathlib.Path(path).open() as f:
        return float(f.read())


def elapsed(path_str):
    path = my_lib.pytest_util.get_path(path_str)

    diff_sec = time.time()
    if not path.exists():
        return diff_sec

    diff_sec -= mtime(path_str)

    return diff_sec


def compare(path_str_a, path_str_b):
    elapsed_a = elapsed(path_str_a)
    elapsed_b = elapsed(path_str_b)

    return elapsed_a < elapsed_b


def clear(path_str):
    path = my_lib.pytest_util.get_path(path_str)

    logging.debug("clear: %s", path)
    path.unlink(missing_ok=True)
