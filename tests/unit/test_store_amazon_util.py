#!/usr/bin/env python3
# ruff: noqa: S101
"""
my_lib.store.amazon.util モジュールのユニットテスト
"""

from __future__ import annotations


class TestGetItemUrl:
    """get_item_url 関数のテスト"""

    def test_returns_correct_url_format(self):
        """正しい URL フォーマットを返す"""
        from my_lib.store.amazon.util import get_item_url

        result = get_item_url("B0G3SXHCLJ")

        assert result == "https://www.amazon.co.jp/dp/B0G3SXHCLJ"

    def test_uses_amazon_jp_base_url(self):
        """Amazon JP のベース URL を使用する"""
        from my_lib.store.amazon.util import AMAZON_JP_BASE_URL, get_item_url

        result = get_item_url("B0G3SXHCLJ")

        assert result.startswith(AMAZON_JP_BASE_URL)

    def test_includes_asin_in_path(self):
        """パスに ASIN を含む"""
        from my_lib.store.amazon.util import get_item_url

        asin = "B01MUZOWBH"
        result = get_item_url(asin)

        assert f"/dp/{asin}" in result

    def test_handles_various_asin_formats(self):
        """様々な ASIN フォーマットを処理できる"""
        from my_lib.store.amazon.util import get_item_url

        # 10文字の標準的な ASIN
        assert get_item_url("B0G3SXHCLJ").endswith("/dp/B0G3SXHCLJ")

        # 数字で始まる ASIN
        assert get_item_url("1234567890").endswith("/dp/1234567890")

        # 大文字小文字混在
        assert get_item_url("AbCdEfGhIj").endswith("/dp/AbCdEfGhIj")


class TestAmazonJpBaseUrl:
    """AMAZON_JP_BASE_URL 定数のテスト"""

    def test_is_https(self):
        """HTTPS を使用している"""
        from my_lib.store.amazon.util import AMAZON_JP_BASE_URL

        assert AMAZON_JP_BASE_URL.startswith("https://")

    def test_is_amazon_co_jp(self):
        """amazon.co.jp ドメインを使用している"""
        from my_lib.store.amazon.util import AMAZON_JP_BASE_URL

        assert "amazon.co.jp" in AMAZON_JP_BASE_URL
