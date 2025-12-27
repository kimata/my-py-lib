#!/usr/bin/env python3
# ruff: noqa: S101
"""
my_lib.thread_util モジュールのユニットテスト
"""
from __future__ import annotations

import concurrent.futures

import pytest


class TestSingleThreadExecutor:
    """SingleThreadExecutor クラスのテスト"""

    def test_is_executor(self):
        """Executor のサブクラスである"""
        from my_lib.thread_util import SingleThreadExecutor

        assert issubclass(SingleThreadExecutor, concurrent.futures.Executor)

    def test_submit_executes_function(self):
        """関数を実行する"""
        from my_lib.thread_util import SingleThreadExecutor

        executor = SingleThreadExecutor()

        def add(a, b):
            return a + b

        future = executor.submit(add, 1, 2)
        result = future.result()

        assert result == 3

    def test_submit_returns_future(self):
        """Future を返す"""
        from my_lib.thread_util import SingleThreadExecutor

        executor = SingleThreadExecutor()

        future = executor.submit(lambda: 42)

        assert isinstance(future, concurrent.futures.Future)

    def test_submit_handles_exception(self):
        """例外を処理する"""
        from my_lib.thread_util import SingleThreadExecutor

        executor = SingleThreadExecutor()

        def raise_error():
            raise ValueError("Test error")

        future = executor.submit(raise_error)

        with pytest.raises(ValueError, match="Test error"):
            future.result()

    def test_submit_with_kwargs(self):
        """キーワード引数を渡せる"""
        from my_lib.thread_util import SingleThreadExecutor

        executor = SingleThreadExecutor()

        def greet(name, greeting="Hello"):
            return f"{greeting}, {name}!"

        future = executor.submit(greet, "World", greeting="Hi")
        result = future.result()

        assert result == "Hi, World!"

    def test_future_done_immediately(self):
        """Future は即座に完了する"""
        from my_lib.thread_util import SingleThreadExecutor

        executor = SingleThreadExecutor()

        future = executor.submit(lambda: 42)

        assert future.done()

    def test_multiple_submits(self):
        """複数の submit を処理できる"""
        from my_lib.thread_util import SingleThreadExecutor

        executor = SingleThreadExecutor()
        results = []

        for i in range(5):
            future = executor.submit(lambda x: x * 2, i)
            results.append(future.result())

        assert results == [0, 2, 4, 6, 8]
