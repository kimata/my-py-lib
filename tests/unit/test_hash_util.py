#!/usr/bin/env python3
# ruff: noqa: S101
"""
my_lib.hash_util モジュールのユニットテスト
"""

from __future__ import annotations


class TestCalculateDictHash:
    """calculate_dict_hash 関数のテスト"""

    def test_returns_md5_hash_string(self):
        """MD5 ハッシュ文字列を返す"""
        import my_lib.hash_util

        result = my_lib.hash_util.calculate_dict_hash({"key": "value"})

        # MD5 ハッシュは32文字の16進数文字列
        assert isinstance(result, str)
        assert len(result) == 32
        assert all(c in "0123456789abcdef" for c in result)

    def test_same_dict_produces_same_hash(self):
        """同じ辞書は同じハッシュを生成する"""
        import my_lib.hash_util

        data = {"name": "test", "value": 123}
        hash1 = my_lib.hash_util.calculate_dict_hash(data)
        hash2 = my_lib.hash_util.calculate_dict_hash(data)

        assert hash1 == hash2

    def test_different_dict_produces_different_hash(self):
        """異なる辞書は異なるハッシュを生成する"""
        import my_lib.hash_util

        data1 = {"name": "test1"}
        data2 = {"name": "test2"}

        hash1 = my_lib.hash_util.calculate_dict_hash(data1)
        hash2 = my_lib.hash_util.calculate_dict_hash(data2)

        assert hash1 != hash2

    def test_key_order_does_not_affect_hash(self):
        """キーの順序はハッシュに影響しない"""
        import my_lib.hash_util

        data1 = {"a": 1, "b": 2, "c": 3}
        data2 = {"c": 3, "a": 1, "b": 2}

        hash1 = my_lib.hash_util.calculate_dict_hash(data1)
        hash2 = my_lib.hash_util.calculate_dict_hash(data2)

        assert hash1 == hash2

    def test_handles_nested_dict(self):
        """ネストした辞書を処理できる"""
        import my_lib.hash_util

        data = {"outer": {"inner": {"value": 123}}}
        result = my_lib.hash_util.calculate_dict_hash(data)

        assert isinstance(result, str)
        assert len(result) == 32

    def test_handles_unicode(self):
        """Unicode 文字を処理できる"""
        import my_lib.hash_util

        data = {"日本語": "テスト", "emoji": "🎉"}
        result = my_lib.hash_util.calculate_dict_hash(data)

        assert isinstance(result, str)
        assert len(result) == 32

    def test_handles_empty_dict(self):
        """空の辞書を処理できる"""
        import my_lib.hash_util

        result = my_lib.hash_util.calculate_dict_hash({})
        assert isinstance(result, str)
        assert len(result) == 32

    def test_handles_various_types(self):
        """様々な型を含む辞書を処理できる"""
        import my_lib.hash_util

        data = {
            "string": "test",
            "int": 123,
            "float": 1.23,
            "bool": True,
            "none": None,
            "list": [1, 2, 3],
        }
        result = my_lib.hash_util.calculate_dict_hash(data)

        assert isinstance(result, str)
        assert len(result) == 32
