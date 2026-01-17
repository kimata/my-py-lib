#!/usr/bin/env python3
"""
属性への安全なアクセスを提供するユーティリティ.

型スタブがないライブラリ（pyVmomi 等）のオブジェクトに対して、
hasattr チェックを簡潔に記述できるようにする。
"""

from typing import Any, TypeVar

T = TypeVar("T")


class _NullObject:
    """None を表すセンチネルオブジェクト.

    チェーン呼び出しで None が出現した場合に、
    AttributeError を発生させずに安全に処理を続行するための sentinel。
    """

    _instance: "_NullObject | None" = None

    def __new__(cls) -> "_NullObject":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __getattr__(self, name: str) -> "_NullObject":
        return self

    def __bool__(self) -> bool:
        return False

    def __repr__(self) -> str:
        return "NULL"


NULL = _NullObject()


class SafeAccess:
    """属性への安全なアクセスを提供するラッパー.

    属性チェーンで None や存在しない属性に遭遇しても
    エラーを発生させず、最終的に None (デフォルト値) を返す。

    Example:
        # 変更前: hasattr チェックが必要
        cpu_threads = None
        if hasattr(host, "hardware") and host.hardware:
            if hasattr(host.hardware, "cpuInfo") and host.hardware.cpuInfo:
                cpu_threads = host.hardware.cpuInfo.numCpuThreads

        # 変更後: SafeAccess で簡潔に
        cpu_threads = safe(host).hardware.cpuInfo.numCpuThreads.value()
    """

    def __init__(self, obj: Any) -> None:
        self._obj = obj

    def __getattr__(self, name: str) -> "SafeAccess":
        """属性アクセスをラップして SafeAccess を返す."""
        if self._obj is None or self._obj is NULL:
            return SafeAccess(NULL)
        if not hasattr(self._obj, name):
            return SafeAccess(NULL)
        attr = getattr(self._obj, name, NULL)
        return SafeAccess(NULL if attr is None else attr)

    def value(self, default: T | None = None) -> Any | T | None:
        """最終的な値を取得.

        Args:
            default: 値が NULL/None の場合に返すデフォルト値

        Returns:
            ラップしている値、または default
        """
        if self._obj is NULL or self._obj is None:
            return default
        return self._obj

    def __bool__(self) -> bool:
        """値が存在するかどうかを判定."""
        return self._obj is not NULL and self._obj is not None


def safe(obj: Any) -> SafeAccess:
    """SafeAccess を作成するファクトリ関数.

    Args:
        obj: ラップするオブジェクト

    Returns:
        SafeAccess インスタンス

    Example:
        from my_lib.safe_access import safe

        # pyVmomi オブジェクトの安全なアクセス
        cpu_threads = safe(host).hardware.cpuInfo.numCpuThreads.value()
        os_version = safe(host).config.product.fullName.value()
    """
    return SafeAccess(obj)
