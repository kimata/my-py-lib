#!/usr/bin/env python3

import io

import rich.console


def format(obj):  # noqa: A001
    str_buf = io.StringIO()
    console = rich.console.Console(file=str_buf, force_terminal=True)
    console.print(obj)

    return str_buf.getvalue().rstrip("\r\n")
