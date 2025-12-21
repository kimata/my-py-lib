#!/usr/bin/env python3
from __future__ import annotations

import logging
from typing import Any

import fluent.sender


def get_handle(tag: str, host: str) -> fluent.sender.FluentSender:
    return fluent.sender.FluentSender(tag, host)


def send(handle: fluent.sender.FluentSender, label: str, data: dict[str, Any]) -> bool:
    if not handle.emit(label, data):
        logging.error(handle.last_error)
        return False

    return True
