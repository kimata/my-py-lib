#!/usr/bin/env python3
from __future__ import annotations

import io
import warnings
from typing import Any

import rich.console


def format(obj: Any) -> str:
    str_buf = io.StringIO()
    # Suppress DeprecationWarning from rich library's internal use of datetime.utcfromtimestamp()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        console = rich.console.Console(file=str_buf, force_terminal=True)
        console.print(obj)

    return str_buf.getvalue().rstrip("\r\n")
