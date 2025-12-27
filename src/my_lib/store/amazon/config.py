#!/usr/bin/env python3
"""Amazon 関連の設定を表す dataclass 定義."""

from __future__ import annotations

import pathlib
from dataclasses import dataclass
from typing import Any


@dataclass
class AmazonApiConfig:
    """PA-API 5.0 用の設定."""

    access_key: str
    secret_key: str
    host: str
    region: str
    associate: str

    @classmethod
    def from_dict(cls, amazon_config: dict[str, Any]) -> AmazonApiConfig:
        """dict から AmazonApiConfig を生成する.

        Args:
            amazon_config: config["store"]["amazon"] の値
        """
        return cls(
            access_key=amazon_config["access_key"],
            secret_key=amazon_config["secret_key"],
            host=amazon_config["host"],
            region=amazon_config["region"],
            associate=amazon_config["associate"],
        )


@dataclass
class AmazonLoginConfig:
    """Amazon ログイン用の設定."""

    user: str
    password: str
    dump_path: pathlib.Path

    @classmethod
    def from_dict(cls, amazon_config: dict[str, Any], dump_path: pathlib.Path) -> AmazonLoginConfig:
        """dict から AmazonLoginConfig を生成する.

        Args:
            amazon_config: config["store"]["amazon"] の値
            dump_path: ダンプファイルの保存先パス
        """
        return cls(
            user=amazon_config["user"],
            password=amazon_config["pass"],
            dump_path=dump_path,
        )


@dataclass
class AmazonItem:
    """Amazon 商品情報."""

    asin: str
    url: str | None = None
    price: int | None = None
    thumb_url: str | None = None
    category: str | None = None
    stock: int | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AmazonItem:
        """dict から AmazonItem を生成する."""
        return cls(
            asin=data["asin"],
            url=data.get("url"),
            price=data.get("price"),
            thumb_url=data.get("thumb_url"),
            category=data.get("category"),
            stock=data.get("stock"),
        )

    def to_dict(self) -> dict[str, Any]:
        """dict に変換する."""
        result: dict[str, Any] = {"asin": self.asin}
        if self.url is not None:
            result["url"] = self.url
        if self.price is not None:
            result["price"] = self.price
        if self.thumb_url is not None:
            result["thumb_url"] = self.thumb_url
        if self.category is not None:
            result["category"] = self.category
        if self.stock is not None:
            result["stock"] = self.stock
        return result


@dataclass
class AmazonItemResult:
    """Amazon から取得した商品価格情報（API/スクレイピング共通）."""

    price: int
    category: str | None = None
    thumb_url: str | None = None
