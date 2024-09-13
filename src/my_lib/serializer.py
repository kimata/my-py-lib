#!/usr/bin/env python3
import logging
import pathlib
import pickle
import shutil
import tempfile


def store(file_path_str, data):
    logging.debug("Store %s", file_path_str)

    file_path = pathlib.Path(file_path_str)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        f = tempfile.NamedTemporaryFile("wb", dir=str(file_path.parent), delete=False)
        pickle.dump(data, f)
        f.close()

        if file_path.exists():
            old_path = file_path.with_suffix(".old")
            shutil.copy(file_path, old_path)

        pathlib.Path(f.name).replace(file_path)
    except Exception:
        logging.exception("Failed to store data")


def load(file_path, init_value=None):
    logging.debug("Load %s", file_path)

    if not file_path.exists():
        return {} if init_value is None else init_value

    try:
        with pathlib.Path(file_path).open("rb") as f:
            data = init_value.copy()
            data.update(pickle.load(f))  # noqa: S301
            return data
    except Exception:
        logging.exception("Failed to load data")

        return {} if init_value is None else init_value
