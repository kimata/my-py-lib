#!/usr/bin/env python3
"""Yahoo!ショッピング item models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Self


@dataclass(frozen=True)
class YahooItem:
    """Yahoo!ショッピング商品情報."""

    name: str
    url: str
    price: int
    thumb_url: str | None = None
    review_rate: float | None = None
    review_count: int | None = None
    in_stock: bool | None = None
    shop_name: str | None = None

    @classmethod
    def parse(cls, data: dict[str, Any]) -> Self:
        """API レスポンスの hits 要素から YahooItem を生成する."""
        price_data = data.get("priceLabel", {})
        prices: list[int] = []
        if isinstance(price_data, dict):
            if price_data.get("premiumPrice") is not None:
                prices.append(int(price_data["premiumPrice"]))
            if price_data.get("discountedPrice") is not None:
                prices.append(int(price_data["discountedPrice"]))
            if price_data.get("defaultPrice") is not None:
                prices.append(int(price_data["defaultPrice"]))
        if data.get("price") is not None:
            prices.append(int(data["price"]))
        price = min(prices) if prices else int(data["price"])

        thumb_url = None
        image = data.get("image")
        if isinstance(image, dict):
            thumb_url = image.get("medium") or image.get("small")

        review_rate = None
        review_count = None
        review = data.get("review")
        if isinstance(review, dict):
            review_rate = review.get("rate")
            review_count = review.get("count")

        shop_name = None
        seller = data.get("seller")
        if isinstance(seller, dict):
            shop_name = seller.get("name")

        return cls(
            name=str(data["name"]),
            url=str(data["url"]),
            price=price,
            thumb_url=thumb_url,
            review_rate=review_rate,
            review_count=review_count,
            in_stock=data.get("inStock"),
            shop_name=shop_name,
        )
