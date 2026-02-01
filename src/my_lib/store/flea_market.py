#!/usr/bin/env python3
"""
フリマ検索共通型定義

メルカリ・ラクマ・PayPayフリマで共通して使用する型を定義します。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Self


class SaleStatus(Enum):
    """販売状態"""

    ON_SALE = "on_sale"  # 販売中
    SOLD_OUT = "sold_out"  # 売り切れ


class ItemCondition(Enum):
    """商品の状態"""

    NEW = 1  # 新品・未使用
    LIKE_NEW = 2  # 未使用に近い
    GOOD = 3  # 目立った傷や汚れなし
    FAIR = 4  # やや傷や汚れあり
    POOR = 5  # 傷や汚れあり
    BAD = 6  # 全体的に状態が悪い


@dataclass(frozen=True)
class SearchCondition:
    """検索条件"""

    keyword: str
    exclude_keyword: str | None = None
    price_min: int | None = None
    price_max: int | None = None
    item_conditions: list[ItemCondition] | None = None
    sale_status: SaleStatus | None = SaleStatus.ON_SALE  # None は全て

    @classmethod
    def parse(cls, data: dict[str, Any]) -> Self:
        """辞書からインスタンスを生成"""
        conditions = data.get("item_conditions")
        item_conditions = None
        if conditions:
            item_conditions = [ItemCondition(c) for c in conditions]

        sale_status_str = data.get("sale_status")
        sale_status: SaleStatus | None = SaleStatus.ON_SALE
        if sale_status_str is None:
            sale_status = None
        elif sale_status_str:
            sale_status = SaleStatus(sale_status_str)

        return cls(
            keyword=data["keyword"],
            exclude_keyword=data.get("exclude_keyword"),
            price_min=data.get("price_min"),
            price_max=data.get("price_max"),
            item_conditions=item_conditions,
            sale_status=sale_status,
        )


@dataclass(frozen=True)
class SearchResult:
    """検索結果の商品情報"""

    title: str
    url: str
    price: int
