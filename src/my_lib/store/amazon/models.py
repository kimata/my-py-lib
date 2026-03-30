#!/usr/bin/env python3
"""Amazon item models."""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SearchResultItem:
    """キーワード検索結果の商品情報."""

    name: str
    asin: str
    price: int | None
    thumb_url: str | None


@dataclass  # NOTE: scrape.py で price/category を更新するため frozen=False
class AmazonItem:
    """Amazon 商品情報."""

    asin: str
    url: str
    name: str | None = None
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
            name=data.get("name"),
            price=data.get("price"),
            thumb_url=data.get("thumb_url"),
            category=data.get("category"),
            stock=data.get("stock"),
        )

    def to_dict(self) -> dict[str, Any]:
        """dict に変換する（None 値は除外）"""
        return {k: v for k, v in dataclasses.asdict(self).items() if v is not None}


DUMMY_AMAZON_ITEM: AmazonItem = AmazonItem(
    asin="B0G3SXHCLJ",
    url="https://www.amazon.co.jp/dp/B0G3SXHCLJ",
    price=69980,
    category="ゲーム",
)
