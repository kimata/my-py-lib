#!/usr/bin/env python3
"""Rakuten item models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Self


@dataclass(frozen=True)
class RakutenItem:
    """楽天市場商品情報."""

    name: str
    url: str
    price: int
    thumb_url: str | None = None
    review_rate: float | None = None
    review_count: int | None = None
    shop_name: str | None = None
    shop_code: str | None = None
    item_code: str | None = None

    @classmethod
    def parse(cls, data: dict[str, Any]) -> Self:
        """API レスポンスの Items 要素から RakutenItem を生成する."""
        thumb_url = None
        medium_urls = data.get("mediumImageUrls")
        if isinstance(medium_urls, list) and medium_urls:
            thumb_url = medium_urls[0]
        else:
            small_urls = data.get("smallImageUrls")
            if isinstance(small_urls, list) and small_urls:
                thumb_url = small_urls[0]

        return cls(
            name=str(data["itemName"]),
            url=str(data["itemUrl"]),
            price=int(data["itemPrice"]),
            thumb_url=thumb_url,
            review_rate=data.get("reviewAverage"),
            review_count=data.get("reviewCount"),
            shop_name=data.get("shopName"),
            shop_code=data.get("shopCode"),
            item_code=data.get("itemCode"),
        )
