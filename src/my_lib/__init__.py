"""Personal utility library for IoT, automation, and data collection applications."""

from __future__ import annotations

from importlib import import_module
from typing import Any

_LEGACY_EXPORTS = {
    "container_util": "my_lib.container_util",
}


def __getattr__(name: str) -> Any:
    if name in _LEGACY_EXPORTS:
        module = import_module(_LEGACY_EXPORTS[name])
        globals()[name] = module
        return module
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["container_util", "platform", "store_clients", "webapp"]
