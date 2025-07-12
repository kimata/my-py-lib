#!/usr/bin/env python3

import io
import warnings

import rich.console


def format(obj):  # noqa: A001
    str_buf = io.StringIO()
    # Suppress DeprecationWarning from rich library's internal use of datetime.utcfromtimestamp()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        console = rich.console.Console(file=str_buf, force_terminal=True)
        console.print(obj)

    return str_buf.getvalue().rstrip("\r\n")
