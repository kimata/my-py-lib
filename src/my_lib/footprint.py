#!/usr/bin/env python3
import logging
import os
import pathlib
import tempfile
import time


def get_path(path_str):
    # NOTE: Pytest を並列実行できるようにする
    suffix = os.environ.get("PYTEST_XDIST_WORKER", "")

    path = pathlib.Path(path_str)

    return path.with_name(path.name + "." + suffix)


def exists(path_str):
    return get_path(path_str).exists()


def update(path_str):
    path = get_path(path_str)

    logging.debug("update: %s", path)

    path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.NamedTemporaryFile("w", delete=False, dir=pathlib.Path(path).parent) as tmp_file:
        tmp_file.write(str(time.time()))
        temp_file_path = pathlib.Path(tmp_file.name)

    temp_file_path.rename(path)


def elapsed(path_str):
    path = get_path(path_str)

    diff_sec = time.time()
    if not path.exists():
        return diff_sec

    with pathlib.Path(path).open() as f:
        last_update = f.read()

        if last_update != "":
            diff_sec -= float(last_update)

    return diff_sec


def clear(path_str):
    path = get_path(path_str)

    logging.debug("clear: %s", path)
    path.unlink(missing_ok=True)
