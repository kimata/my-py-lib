"""ロケータ表現。

現状の全プロジェクトは要素特定にほぼ XPath のみを使用しているため、当面は
`Xpath` を第一級とする。将来 CSS / role 等を足せるよう、共通の基底 `Locator` を
介してバックエンドへ渡す設計にしておく。
"""

from __future__ import annotations

import dataclasses
from typing import Literal

LocatorKind = Literal["xpath", "css"]


@dataclasses.dataclass(frozen=True)
class Locator:
    """バックエンド非依存のロケータ。

    バックエンドはこの `kind` / `value` を自身の表現へ変換する
    （Patchright: ``page.locator("xpath=...")`` / ``locator("css=...")`` 等）。
    """

    kind: LocatorKind
    value: str


def Xpath(value: str) -> Locator:
    """XPath ロケータを生成する。"""
    return Locator(kind="xpath", value=value)


def Css(value: str) -> Locator:
    """CSS セレクタロケータを生成する。"""
    return Locator(kind="css", value=value)
