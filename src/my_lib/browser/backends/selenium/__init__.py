"""Selenium バックエンド（移行期の互換用）。

既存の `my_lib.selenium_util` / `browser_manager` 資産を Protocol へ適合させるアダプタを置く。
未移行プロジェクト（例: ログイン済みプロファイルを再利用する mercari-bot）を、共有 store 層を
Protocol 化した後も動かし続けるためのもの。Phase 1b で実装する。
"""

from __future__ import annotations

from my_lib.browser.protocol import Browser
from my_lib.browser.types import BrowserProfile


def launch(profile: BrowserProfile) -> Browser:
    """（未実装）Selenium バックエンドの起動。"""
    msg = "Selenium バックエンドは Phase 1b で実装予定です"
    raise NotImplementedError(msg)
