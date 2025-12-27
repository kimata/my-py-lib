#!/usr/bin/env python3
# ruff: noqa: S101
"""
my_lib.store.amazon.config モジュールのユニットテスト
"""
from __future__ import annotations

import pathlib

import pytest


class TestAmazonApiConfig:
    """AmazonApiConfig データクラスのテスト"""

    def test_creates_instance(self):
        """インスタンスを作成できる"""
        from my_lib.store.amazon.config import AmazonApiConfig

        config = AmazonApiConfig(
            access_key="access_key",
            secret_key="secret_key",
            host="webservices.amazon.co.jp",
            region="us-west-2",
            associate="associate_id",
        )

        assert config.access_key == "access_key"
        assert config.secret_key == "secret_key"
        assert config.host == "webservices.amazon.co.jp"
        assert config.region == "us-west-2"
        assert config.associate == "associate_id"

    def test_from_dict(self):
        """dict から生成できる"""
        from my_lib.store.amazon.config import AmazonApiConfig

        data = {
            "access_key": "access_key",
            "secret_key": "secret_key",
            "host": "webservices.amazon.co.jp",
            "region": "us-west-2",
            "associate": "associate_id",
        }

        config = AmazonApiConfig.from_dict(data)

        assert config.access_key == "access_key"
        assert config.secret_key == "secret_key"


class TestAmazonLoginConfig:
    """AmazonLoginConfig データクラスのテスト"""

    def test_creates_instance(self, temp_dir):
        """インスタンスを作成できる"""
        from my_lib.store.amazon.config import AmazonLoginConfig

        config = AmazonLoginConfig(
            user="user@example.com",
            password="password123",
            dump_path=temp_dir,
        )

        assert config.user == "user@example.com"
        assert config.password == "password123"
        assert config.dump_path == temp_dir

    def test_from_dict(self, temp_dir):
        """dict から生成できる"""
        from my_lib.store.amazon.config import AmazonLoginConfig

        data = {
            "user": "user@example.com",
            "pass": "password123",
        }

        config = AmazonLoginConfig.from_dict(data, temp_dir)

        assert config.user == "user@example.com"
        assert config.password == "password123"
        assert config.dump_path == temp_dir


class TestAmazonItem:
    """AmazonItem データクラスのテスト"""

    def test_creates_instance(self):
        """インスタンスを作成できる"""
        from my_lib.store.amazon.config import AmazonItem

        item = AmazonItem(
            asin="B0G3SXHCLJ",
            url="https://www.amazon.co.jp/dp/B0G3SXHCLJ",
        )

        assert item.asin == "B0G3SXHCLJ"
        assert item.url == "https://www.amazon.co.jp/dp/B0G3SXHCLJ"
        assert item.price is None
        assert item.thumb_url is None
        assert item.category is None
        assert item.stock is None

    def test_creates_instance_with_optional_fields(self):
        """オプションフィールド付きでインスタンスを作成できる"""
        from my_lib.store.amazon.config import AmazonItem

        item = AmazonItem(
            asin="B0G3SXHCLJ",
            url="https://www.amazon.co.jp/dp/B0G3SXHCLJ",
            price=69980,
            thumb_url="https://example.com/thumb.jpg",
            category="ゲーム",
            stock=5,
        )

        assert item.price == 69980
        assert item.thumb_url == "https://example.com/thumb.jpg"
        assert item.category == "ゲーム"
        assert item.stock == 5

    def test_from_asin(self):
        """ASIN から生成できる"""
        from my_lib.store.amazon.config import AmazonItem

        item = AmazonItem.from_asin("B0G3SXHCLJ")

        assert item.asin == "B0G3SXHCLJ"
        assert item.url == "https://www.amazon.co.jp/dp/B0G3SXHCLJ"

    def test_from_dict(self):
        """dict から生成できる"""
        from my_lib.store.amazon.config import AmazonItem

        data = {
            "asin": "B0G3SXHCLJ",
            "price": 69980,
            "category": "ゲーム",
        }

        item = AmazonItem.from_dict(data)

        assert item.asin == "B0G3SXHCLJ"
        assert item.url == "https://www.amazon.co.jp/dp/B0G3SXHCLJ"
        assert item.price == 69980
        assert item.category == "ゲーム"

    def test_from_dict_with_custom_url(self):
        """カスタム URL 付きの dict から生成できる"""
        from my_lib.store.amazon.config import AmazonItem

        data = {
            "asin": "B0G3SXHCLJ",
            "url": "https://custom.url/product",
        }

        item = AmazonItem.from_dict(data)

        assert item.url == "https://custom.url/product"

    def test_to_dict(self):
        """dict に変換できる"""
        from my_lib.store.amazon.config import AmazonItem

        item = AmazonItem(
            asin="B0G3SXHCLJ",
            url="https://www.amazon.co.jp/dp/B0G3SXHCLJ",
            price=69980,
            category="ゲーム",
        )

        result = item.to_dict()

        assert result["asin"] == "B0G3SXHCLJ"
        assert result["url"] == "https://www.amazon.co.jp/dp/B0G3SXHCLJ"
        assert result["price"] == 69980
        assert result["category"] == "ゲーム"
        assert "thumb_url" not in result  # None の場合は含まれない
        assert "stock" not in result  # None の場合は含まれない

    def test_to_dict_excludes_none_values(self):
        """None の値は dict に含まれない"""
        from my_lib.store.amazon.config import AmazonItem

        item = AmazonItem(
            asin="B0G3SXHCLJ",
            url="https://www.amazon.co.jp/dp/B0G3SXHCLJ",
        )

        result = item.to_dict()

        assert "price" not in result
        assert "thumb_url" not in result
        assert "category" not in result
        assert "stock" not in result


class TestDummyAmazonItem:
    """DUMMY_AMAZON_ITEM 定数のテスト"""

    def test_exists(self):
        """存在する"""
        from my_lib.store.amazon.config import DUMMY_AMAZON_ITEM

        assert DUMMY_AMAZON_ITEM is not None

    def test_has_correct_asin(self):
        """正しい ASIN を持つ"""
        from my_lib.store.amazon.config import DUMMY_AMAZON_ITEM

        assert DUMMY_AMAZON_ITEM.asin == "B0G3SXHCLJ"

    def test_has_correct_url(self):
        """正しい URL を持つ"""
        from my_lib.store.amazon.config import DUMMY_AMAZON_ITEM

        assert DUMMY_AMAZON_ITEM.url == "https://www.amazon.co.jp/dp/B0G3SXHCLJ"

    def test_has_price(self):
        """価格を持つ"""
        from my_lib.store.amazon.config import DUMMY_AMAZON_ITEM

        assert DUMMY_AMAZON_ITEM.price is not None
        assert DUMMY_AMAZON_ITEM.price > 0

    def test_has_category(self):
        """カテゴリを持つ"""
        from my_lib.store.amazon.config import DUMMY_AMAZON_ITEM

        assert DUMMY_AMAZON_ITEM.category is not None
