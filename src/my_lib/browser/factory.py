"""バックエンド選択。

`BrowserBackend` に応じて対応するバックエンドの `launch` を呼び、`Browser` を返す。
バックエンド固有ライブラリの import は各バックエンドのサブパッケージ内で行うため、
未使用バックエンドの依存が無くても本モジュールは import できる。
"""

from __future__ import annotations

from my_lib.browser.protocol import Browser
from my_lib.browser.types import BrowserBackend, BrowserProfile


def launch(profile: BrowserProfile, backend: BrowserBackend = BrowserBackend.PATCHRIGHT) -> Browser:
    """指定バックエンドでブラウザを起動する。"""
    if backend is BrowserBackend.PATCHRIGHT:
        from my_lib.browser.backends.patchright import launch as launch_patchright

        return launch_patchright(profile)

    if backend is BrowserBackend.SELENIUM:
        from my_lib.browser.backends.selenium import launch as launch_selenium

        return launch_selenium(profile)

    msg = f"未対応のバックエンドです: {backend}"
    raise ValueError(msg)
