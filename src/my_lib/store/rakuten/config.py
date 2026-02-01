#!/usr/bin/env python3
"""楽天市場関連の設定を表す dataclass 定義."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Self


@dataclass(frozen=True)
class RakutenApiConfig:
    """楽天市場 API 用の設定."""

    application_id: str

    @classmethod
    def parse(cls, rakuten_config: dict[str, Any]) -> Self:
        """dict から RakutenApiConfig を生成する.

        Args:
            rakuten_config: config["store"]["rakuten"] の値
        """
        return cls(
            application_id=rakuten_config["application_id"],
        )


@dataclass(frozen=True)
class RakutenItem:
    """楽天市場商品情報."""

    name: str
    url: str
    price: int
    thumb_url: str | None = None
    review_average: float | None = None
    review_count: int | None = None
    shop_name: str | None = None
    shop_code: str | None = None
    item_code: str | None = None

    @classmethod
    def parse(cls, data: dict[str, Any]) -> Self:
        """API レスポンスの Items 要素から RakutenItem を生成する.

        Args:
            data: formatVersion=2 の場合の商品データ
        """
        # サムネイル画像 URL（中サイズを優先）
        thumb_url = None
        medium_urls = data.get("mediumImageUrls")
        if medium_urls and len(medium_urls) > 0:
            thumb_url = medium_urls[0]
        else:
            small_urls = data.get("smallImageUrls")
            if small_urls and len(small_urls) > 0:
                thumb_url = small_urls[0]

        return cls(
            name=data["itemName"],
            url=data["itemUrl"],
            price=int(data["itemPrice"]),
            thumb_url=thumb_url,
            review_average=data.get("reviewAverage"),
            review_count=data.get("reviewCount"),
            shop_name=data.get("shopName"),
            shop_code=data.get("shopCode"),
            item_code=data.get("itemCode"),
        )
