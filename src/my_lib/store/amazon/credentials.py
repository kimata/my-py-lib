#!/usr/bin/env python3
"""Amazon API / login credential models."""

from __future__ import annotations

import pathlib
from dataclasses import dataclass
from typing import Any, Protocol, Self


class SupportsAmazonApiConfig(Protocol):
    """Minimal shape required by the Amazon Creators API helpers."""

    @property
    def credential_id(self) -> str: ...
    @property
    def credential_secret(self) -> str: ...
    @property
    def associate(self) -> str: ...
    @property
    def version(self) -> str: ...


@dataclass(frozen=True)
class AmazonApiConfig:
    """Creators API 用の設定."""

    credential_id: str
    credential_secret: str
    associate: str
    version: str = "3.3"

    @classmethod
    def parse(cls, amazon_config: dict[str, Any]) -> Self:
        """dict から AmazonApiConfig を生成する."""
        return cls(
            credential_id=amazon_config["credential_id"],
            credential_secret=amazon_config["credential_secret"],
            associate=amazon_config["associate"],
            version=amazon_config.get("version", "3.3"),
        )


@dataclass(frozen=True)
class AmazonLoginConfig:
    """Amazon ログイン用の設定."""

    user: str
    password: str
    dump_path: pathlib.Path

    @classmethod
    def parse(cls, amazon_config: dict[str, Any], dump_path: pathlib.Path) -> Self:
        """dict から AmazonLoginConfig を生成する."""
        return cls(
            user=amazon_config["user"],
            password=amazon_config["pass"],
            dump_path=dump_path,
        )
