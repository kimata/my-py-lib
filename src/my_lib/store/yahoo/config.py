#!/usr/bin/env python3
"""Yahoo!ショッピング関連の設定を表す dataclass 定義."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Self


@dataclass(frozen=True)
class YahooApiConfig:
    """Yahoo!ショッピング API 用の設定."""

    client_id: str
    secret: str

    @classmethod
    def parse(cls, yahoo_config: dict[str, Any]) -> Self:
        """dict から YahooApiConfig を生成する.

        Args:
            yahoo_config: config["store"]["yahoo"] の値
        """
        return cls(
            client_id=yahoo_config["client_id"],
            secret=yahoo_config["secret"],
        )


@dataclass(frozen=True)
class YahooItem:
    """Yahoo!ショッピング商品情報."""

    name: str
    url: str
    price: int
    image_url: str | None = None
    review_rate: float | None = None
    review_count: int | None = None
    in_stock: bool | None = None
    seller_name: str | None = None

    @classmethod
    def parse(cls, data: dict[str, Any]) -> Self:
        """API レスポンスの hits 要素から YahooItem を生成する."""
        image_url = None
        if data.get("image"):
            image_url = data["image"].get("medium") or data["image"].get("small")

        review_rate = None
        review_count = None
        if data.get("review"):
            review_rate = data["review"].get("rate")
            review_count = data["review"].get("count")

        seller_name = None
        if data.get("seller"):
            seller_name = data["seller"].get("name")

        return cls(
            name=data["name"],
            url=data["url"],
            price=int(data["price"]),
            image_url=image_url,
            review_rate=review_rate,
            review_count=review_count,
            in_stock=data.get("inStock"),
            seller_name=seller_name,
        )
