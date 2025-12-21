#!/usr/bin/env python3
from __future__ import annotations

import concurrent.futures
from typing import Any, TypeVar

T = TypeVar("T")


# NOTE: テスト用
class SingleThreadExecutor(concurrent.futures.Executor):
    def submit(  # type: ignore[override]
        self, fn: Any, *args: Any, **kwargs: Any
    ) -> concurrent.futures.Future[Any]:
        future: concurrent.futures.Future[Any] = concurrent.futures.Future()
        try:
            result = fn(*args, **kwargs)
            future.set_result(result)
        except Exception as e:
            future.set_exception(e)
        return future
