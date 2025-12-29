#!/usr/bin/env python3
"""メルカリスクレイピングの進捗通知用 Protocol 定義"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class ProgressObserver(Protocol):
    """スクレイピング進捗を通知するための Protocol

    iter_items_on_display などで進捗を監視するために使用します。
    TTY 環境では Rich による進捗表示、非 TTY 環境では logging へのフォールバックなど、
    実装側で適切な表示方法を選択できます。

    Examples:
        class MyProgressDisplay:
            def on_total_count(self, count: int) -> None:
                print(f"Total: {count}")

            def on_item_start(self, index: int, total: int, item: dict[str, Any]) -> None:
                print(f"Processing {index}/{total}: {item['name']}")

            def on_item_complete(self, index: int, total: int, item: dict[str, Any]) -> None:
                print(f"Completed {index}/{total}")

        observer = MyProgressDisplay()
        iter_items_on_display(driver, wait, debug_mode, [handler], progress_observer=observer)

    """

    def on_total_count(self, count: int) -> None:
        """アイテム総数が判明したときに呼ばれる

        Args:
            count: 出品中のアイテム総数

        """
        ...

    def on_item_start(self, index: int, total: int, item: dict[str, Any]) -> None:
        """各アイテムの処理開始時に呼ばれる

        Args:
            index: 現在のアイテムのインデックス（1始まり）
            total: アイテム総数
            item: アイテム情報（id, name, price, view, favorite, is_stop など）

        """
        ...

    def on_item_complete(self, index: int, total: int, item: dict[str, Any]) -> None:
        """各アイテムの処理完了時に呼ばれる

        Args:
            index: 現在のアイテムのインデックス（1始まり）
            total: アイテム総数
            item: アイテム情報

        """
        ...
