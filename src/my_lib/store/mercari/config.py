#!/usr/bin/env python3
"""メルカリ関連の設定クラス"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Self


@dataclass(frozen=True)
class MercariItem:
    """メルカリ出品アイテム情報"""

    id: str
    url: str
    name: str
    price: int
    view: int
    favorite: int
    is_stop: int


@dataclass(frozen=True)
class MercariLoginConfig:
    """メルカリ ログイン情報"""

    user: str
    password: str

    @classmethod
    def parse(cls, data: dict[str, Any]) -> Self:
        """辞書からインスタンスを生成"""
        return cls(
            user=data["user"],
            password=data["pass"],
        )


@dataclass(frozen=True)
class LineLoginConfig:
    """LINE ログイン情報"""

    user: str
    password: str

    @classmethod
    def parse(cls, data: dict[str, Any]) -> Self:
        """辞書からインスタンスを生成"""
        return cls(
            user=data["user"],
            password=data["pass"],
        )
