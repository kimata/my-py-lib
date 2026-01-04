#!/usr/bin/env python3
# ruff: noqa: S101
"""
my_lib.git_util モジュールのユニットテスト
"""

from __future__ import annotations

import datetime


class TestGetRevisionInfo:
    """get_revision_info 関数のテスト"""

    def test_returns_revision_info_dict(self):
        """RevisionInfo 辞書を返す"""
        import my_lib.git_util

        result = my_lib.git_util.get_revision_info()

        assert isinstance(result, dict)
        assert "hash" in result
        assert "date" in result
        assert "is_dirty" in result

    def test_hash_is_valid_sha(self):
        """ハッシュが有効な SHA である"""
        import my_lib.git_util

        result = my_lib.git_util.get_revision_info()

        # SHA-1 ハッシュは40文字の16進数
        assert isinstance(result["hash"], str)
        assert len(result["hash"]) == 40
        assert all(c in "0123456789abcdef" for c in result["hash"])

    def test_date_is_datetime(self):
        """日付が datetime オブジェクトである"""
        import my_lib.git_util

        result = my_lib.git_util.get_revision_info()

        assert isinstance(result["date"], datetime.datetime)
        assert result["date"].tzinfo is not None

    def test_is_dirty_is_boolean(self):
        """is_dirty が真偽値である"""
        import my_lib.git_util

        result = my_lib.git_util.get_revision_info()

        assert isinstance(result["is_dirty"], bool)


class TestGetRevisionStr:
    """get_revision_str 関数のテスト"""

    def test_returns_string(self):
        """文字列を返す"""
        import my_lib.git_util

        result = my_lib.git_util.get_revision_str()

        assert isinstance(result, str)

    def test_contains_git_hash_label(self):
        """Git hash ラベルを含む"""
        import my_lib.git_util

        result = my_lib.git_util.get_revision_str()

        assert "Git hash:" in result

    def test_contains_git_date_label(self):
        """Git date ラベルを含む"""
        import my_lib.git_util

        result = my_lib.git_util.get_revision_str()

        assert "Git date:" in result

    def test_contains_actual_hash(self):
        """実際のハッシュ値を含む"""
        import my_lib.git_util

        result = my_lib.git_util.get_revision_str()
        info = my_lib.git_util.get_revision_info()

        assert info["hash"] in result
