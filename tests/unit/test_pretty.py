#!/usr/bin/env python3
# ruff: noqa: S101
"""
my_lib.pretty モジュールのユニットテスト
"""
from __future__ import annotations

import pytest


class TestFormat:
    """format 関数のテスト"""

    def test_formats_string(self):
        """文字列をフォーマットする"""
        import my_lib.pretty

        result = my_lib.pretty.format("hello")
        assert "hello" in result

    def test_formats_integer(self):
        """整数をフォーマットする"""
        import my_lib.pretty

        result = my_lib.pretty.format(123)
        assert "123" in result

    def test_formats_dict(self):
        """辞書をフォーマットする"""
        import my_lib.pretty

        result = my_lib.pretty.format({"key": "value"})
        assert "key" in result
        assert "value" in result

    def test_formats_list(self):
        """リストをフォーマットする"""
        import my_lib.pretty

        result = my_lib.pretty.format([1, 2, 3])
        assert "1" in result
        assert "2" in result
        assert "3" in result

    def test_formats_nested_structure(self):
        """ネストした構造をフォーマットする"""
        import my_lib.pretty

        data = {"items": [{"name": "test", "value": 123}]}
        result = my_lib.pretty.format(data)
        assert "items" in result
        assert "name" in result
        assert "test" in result

    def test_returns_string_without_trailing_newline(self):
        """末尾に改行がない文字列を返す"""
        import my_lib.pretty

        result = my_lib.pretty.format("test")
        assert not result.endswith("\n")
        assert not result.endswith("\r")

    def test_formats_none(self):
        """None をフォーマットする"""
        import my_lib.pretty

        result = my_lib.pretty.format(None)
        assert "None" in result

    def test_formats_boolean(self):
        """真偽値をフォーマットする"""
        import my_lib.pretty

        result_true = my_lib.pretty.format(True)
        result_false = my_lib.pretty.format(False)
        assert "True" in result_true
        assert "False" in result_false
