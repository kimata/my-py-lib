#!/usr/bin/env python3
"""Rakuten API credential models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Self


@dataclass(frozen=True)
class RakutenApiConfig:
    """楽天市場 API 用の設定."""

    application_id: str
    affiliate_id: str | None = None

    @classmethod
    def parse(cls, rakuten_config: dict[str, Any]) -> Self:
        """dict から RakutenApiConfig を生成する."""
        return cls(
            application_id=rakuten_config["application_id"],
            affiliate_id=rakuten_config.get("affiliate_id"),
        )
