#!/usr/bin/env python3
import logging
import pathlib
import tempfile
import time


def exists(path):
    return path.exists()


def update(path):
    logging.debug("update: %s", path)

    path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.NamedTemporaryFile("w", delete=False, dir=pathlib.Path(path).parent) as tmp_file:
        tmp_file.write(str(time.time()))
        temp_file_path = pathlib.Path(tmp_file.name)

    temp_file_path.rename(path)


def elapsed(path):
    diff_sec = time.time()
    if not path.exists():
        return diff_sec

    with pathlib.Path(path).open() as f:
        diff_sec -= float(f.read())

    return diff_sec


def clear(path):
    logging.debug("clear: %s", path)
    path.unlink(missing_ok=True)
