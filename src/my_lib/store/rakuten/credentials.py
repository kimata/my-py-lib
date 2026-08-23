#!/usr/bin/env python3
"""Rakuten API credential models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, Self


class SupportsRakutenApiConfig(Protocol):
    """Minimal shape required by the Rakuten API helpers."""

    @property
    def application_id(self) -> str: ...

    @property
    def access_key(self) -> str | None: ...

    @property
    def affiliate_id(self) -> str | None: ...


@dataclass(frozen=True)
class RakutenApiConfig:
    """楽天市場 API 用の設定.

    access_key は 2026 年の新仕様（openapi.rakuten.co.jp）で必須になったアクセスキー。
    楽天ウェブサービスのアプリ情報ページ（https://webservice.rakuten.co.jp/app/list）で発行する。
    """

    application_id: str
    access_key: str | None = None
    affiliate_id: str | None = None

    @classmethod
    def parse(cls, rakuten_config: dict[str, Any]) -> Self:
        """dict から RakutenApiConfig を生成する."""
        return cls(
            application_id=rakuten_config["application_id"],
            access_key=rakuten_config.get("access_key"),
            affiliate_id=rakuten_config.get("affiliate_id"),
        )
