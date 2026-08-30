"""ブラウザ抽象層の例外階層。

バックエンド（Selenium / Patchright）固有の例外は、この階層に正規化してから
呼び出し側へ伝播させる。呼び出し側は `selenium.*` / `patchright.*` の例外型を
一切 import しない。
"""

from __future__ import annotations


class BrowserError(Exception):
    """ブラウザ操作に関する例外の基底。"""


class SessionError(BrowserError):
    """ブラウザセッションが無効になった（クラッシュ・切断等）。

    リトライ層はこの例外を捕捉して、プロファイル削除とクリーン再起動を試みる。
    Selenium の ``InvalidSessionIdException`` 等はこの型へ正規化する。
    """


class NavigationError(BrowserError):
    """ページ遷移・読み込みに失敗した。"""


class ElementNotFoundError(BrowserError):
    """指定したロケータに一致する要素が見つからなかった。"""


class WaitTimeoutError(BrowserError):
    """待機条件がタイムアウトした。"""
