#!/usr/bin/env python3
from __future__ import annotations

import logging
from typing import Any

import fluent.sender  # type: ignore[import-untyped]


def get_handle(tag: str, host: str, port: int = 24224) -> fluent.sender.FluentSender:
    # NOTE: forward_packet_error はデフォルト True だが、True だと msgpack 化できない
    # データを送った際に「エラー内容のパケット」へ差し替えて送信したうえ成功扱いに
    # なってしまう。実データが送られていないのに liveness が更新され続けるのを防ぐため
    # False にして emit を失敗させる。
    return fluent.sender.FluentSender(tag, host=host, port=port, forward_packet_error=False)


def send(handle: fluent.sender.FluentSender, label: str, data: dict[str, Any]) -> bool:
    if not handle.emit(label, data):
        logging.error(handle.last_error)
        handle.clear_last_error()
        return False

    return True


def send_with_time(
    handle: fluent.sender.FluentSender, label: str, data: dict[str, Any], timestamp: float
) -> bool:
    """タイムスタンプ指定付きで送信する (スプールからの再送用)。"""
    if not handle.emit_with_time(label, int(timestamp), data):
        logging.error(handle.last_error)
        handle.clear_last_error()
        return False

    return True


def close(handle: fluent.sender.FluentSender) -> None:
    """未送信バッファを送信してから sender を閉じる。

    プロセス終了時に呼ばないと、内部バッファ (最大 1MB) の未送信データが破棄される。
    """
    handle.close()
