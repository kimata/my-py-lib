#!/usr/bin/env python3
from __future__ import annotations

import os
import pathlib


def get_path(path_str: str | pathlib.Path) -> pathlib.Path:
    # NOTE: Pytest を並列実行できるようにする
    suffix = os.environ.get("PYTEST_XDIST_WORKER", None)
    path = pathlib.Path(path_str)

    if suffix is None:
        return path
    else:
        return path.with_name(path.name + "." + suffix)
