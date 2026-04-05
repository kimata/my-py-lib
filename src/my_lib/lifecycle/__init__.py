"""ライフサイクル管理モジュール。"""

from my_lib.lifecycle.manager import (
    LifecycleManager,
    get_default,
    reset_default,
)
from my_lib.lifecycle.shutdown import ShutdownController
from my_lib.lifecycle.signals import (
    install_double_tap_shutdown_handlers,
    install_interactive_shutdown_handler,
)

__all__ = [
    "LifecycleManager",
    "ShutdownController",
    "get_default",
    "install_double_tap_shutdown_handlers",
    "install_interactive_shutdown_handler",
    "reset_default",
]
