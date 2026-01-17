"""後方互換性のためのモジュール

新規コードでは my_lib.lifecycle.LifecycleManager を使用してください。
"""

from my_lib.lifecycle.manager import (
    LifecycleManager,
    get_default,
    reset_default,
)

__all__ = ["LifecycleManager", "get_default", "reset_default"]
