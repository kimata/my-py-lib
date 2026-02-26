#!/usr/bin/env python3
"""Amazon 関連の設定を表す dataclass 定義."""

from __future__ import annotations

import dataclasses
import pathlib
from dataclasses import dataclass
from typing import Any, Self


@dataclass(frozen=True)
class AmazonApiConfig:
    """PA-API 5.0 用の設定."""

    access_key: str
    secret_key: str
    host: str
    region: str
    associate: str

    @classmethod
    def parse(cls, amazon_config: dict[str, Any]) -> Self:
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


@dataclass(frozen=True)
class AmazonLoginConfig:
    """Amazon ログイン用の設定."""

    user: str
    password: str
    dump_path: pathlib.Path

    @classmethod
    def parse(cls, amazon_config: dict[str, Any], dump_path: pathlib.Path) -> Self:
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


@dataclass(frozen=True)
class SearchResultItem:
    """キーワード検索結果の商品情報."""

    name: str
    asin: str
    price: int | None
    thumb_url: str | None


@dataclass  # NOTE: scrape.py で price/category を更新するため frozen=False
class AmazonItem:
    """Amazon 商品情報.

    Note:
        outlet_price は buybox が Amazonアウトレットの場合のみ取得される。
        buybox が新品で、Amazonアウトレットが「その他の出品者」にある場合は取得されない。
    """

    asin: str
    url: str
    price: int | None = None
    thumb_url: str | None = None
    category: str | None = None
    stock: int | None = None
    outlet_price: int | None = None

    @classmethod
    def from_asin(cls, asin: str) -> AmazonItem:
        """ASIN から AmazonItem を生成する."""
        from my_lib.store.amazon.util import get_item_url

        return cls(asin=asin, url=get_item_url(asin))

    @classmethod
    def parse(cls, data: dict[str, Any]) -> AmazonItem:
        """dict から AmazonItem を生成する."""
        from my_lib.store.amazon.util import get_item_url

        asin = data["asin"]
        return cls(
            asin=asin,
            url=data.get("url", get_item_url(asin)),
            price=data.get("price"),
            thumb_url=data.get("thumb_url"),
            category=data.get("category"),
            stock=data.get("stock"),
        )

    def to_dict(self) -> dict[str, Any]:
        """dict に変換する（None 値は除外）"""
        return {k: v for k, v in dataclasses.asdict(self).items() if v is not None}


# NOTE: 下記の関数を Mock してテストをする際、返り値として以下の DUMMY_AMAZON_ITEM を使ってください。
# my_lib.store.amazon.api.fetch_price
# my_lib.store.amazon.api.fetch_price_new
# my_lib.store.amazon.scrape.fetch_price
DUMMY_AMAZON_ITEM: AmazonItem = AmazonItem(
    asin="B0G3SXHCLJ",
    url="https://www.amazon.co.jp/dp/B0G3SXHCLJ",
    price=69980,
    category="ゲーム",
)
