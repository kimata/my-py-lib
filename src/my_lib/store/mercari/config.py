#!/usr/bin/env python3
"""メルカリ関連の設定クラス"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class MercariLoginConfig:
    """メルカリ ログイン情報"""

    user: str
    password: str


@dataclass(frozen=True)
class LineLoginConfig:
    """LINE ログイン情報"""

    user: str
    password: str


def parse_mercari_login(data: dict[str, Any]) -> MercariLoginConfig:
    """メルカリログイン設定をパースする"""
    return MercariLoginConfig(
        user=data["user"],
        password=data["pass"],
    )


def parse_line_login(data: dict[str, Any]) -> LineLoginConfig:
    """LINEログイン設定をパースする"""
    return LineLoginConfig(
        user=data["user"],
        password=data["pass"],
    )
