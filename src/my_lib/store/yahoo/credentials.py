#!/usr/bin/env python3
"""Yahoo!ショッピング API credential models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, Self


class SupportsYahooApiConfig(Protocol):
    """Minimal shape required by the Yahoo Shopping API helpers."""

    @property
    def client_id(self) -> str: ...

    @property
    def secret(self) -> str: ...

    @property
    def affiliate_type(self) -> str | None: ...

    @property
    def affiliate_id(self) -> str | None: ...


@dataclass(frozen=True)
class YahooApiConfig:
    """Yahoo!ショッピング API 用の設定."""

    client_id: str
    secret: str
    affiliate_type: str | None = None
    affiliate_id: str | None = None

    @classmethod
    def parse(cls, yahoo_config: dict[str, Any]) -> Self:
        """dict から YahooApiConfig を生成する."""
        return cls(
            client_id=yahoo_config["client_id"],
            secret=yahoo_config["secret"],
            affiliate_type=yahoo_config.get("affiliate_type"),
            affiliate_id=yahoo_config.get("affiliate_id"),
        )
