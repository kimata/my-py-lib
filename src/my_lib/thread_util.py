#!/usr/bin/env python3
from __future__ import annotations

import concurrent.futures
from collections.abc import Callable
from typing import Any, TypeVar

T = TypeVar("T")


# NOTE: テスト用
class SingleThreadExecutor(concurrent.futures.Executor):
    def submit(self, fn: Callable[..., T], /, *args: Any, **kwargs: Any) -> concurrent.futures.Future[T]:
        future: concurrent.futures.Future[T] = concurrent.futures.Future()
        try:
            result = fn(*args, **kwargs)
            future.set_result(result)
        except Exception as e:
            future.set_exception(e)
        return future
