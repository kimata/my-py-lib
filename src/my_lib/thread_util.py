#!/usr/bin/env python3
import concurrent.futures


# NOTE: テスト用
class SingleThreadExecutor(concurrent.futures.Executor):
    def submit(self, fn, *args, **kwargs):
        future = concurrent.futures.Future()
        try:
            result = fn(*args, **kwargs)
            future.set_result(result)
        except Exception as e:
            future.set_exception(e)
        return future
