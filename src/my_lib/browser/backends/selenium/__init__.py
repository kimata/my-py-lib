"""Selenium バックエンド（移行期の互換用）。

既存の `my_lib.selenium_util` / `create_driver` を Protocol へ適合させるアダプタ。
未移行プロジェクト（例: ログイン済みプロファイルを再利用する mercari-bot）を、共有 store 層を
Protocol 化した後も動かし続けるためのもの。`selenium.*` の import はこのサブパッケージ内にのみ存在する。
"""

from my_lib.browser.backends.selenium.browser import SeleniumBrowser, launch

__all__ = ["SeleniumBrowser", "launch"]
