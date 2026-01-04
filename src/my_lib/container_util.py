#!/usr/bin/env python3
"""コンテナ関連のユーティリティ関数."""

from __future__ import annotations

import logging
import os
import pathlib


def get_uptime() -> float:
    """
    コンテナの起動からの経過時間を取得する.

    /proc/1/stat からプロセス開始時刻を取得して計算する。

    Returns:
        コンテナの起動からの経過時間（秒）。
        取得に失敗した場合は float("inf") を返す。

    """
    try:
        with pathlib.Path("/proc/1/stat").open() as f:
            stat = f.read().split()
            # 22番目のフィールドが starttime (clock ticks since boot)
            starttime_ticks = int(stat[21])

        with pathlib.Path("/proc/uptime").open() as f:
            uptime_seconds = float(f.read().split()[0])

        # clock ticks を秒に変換（通常 100 ticks/sec）
        ticks_per_sec = os.sysconf("SC_CLK_TCK")
        process_start_since_boot = starttime_ticks / ticks_per_sec

        return uptime_seconds - process_start_since_boot
    except Exception:
        logging.exception("Failed to get container uptime")
        return float("inf")  # 取得失敗時は猶予期間を過ぎたとみなす
