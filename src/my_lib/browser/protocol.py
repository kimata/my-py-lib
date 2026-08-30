"""ブラウザ抽象層の Protocol 定義。

`Browser` / `Page` / `Element` / `Maintenance` はバックエンド非依存の抽象で、
`selenium.*` / `patchright.*` の型を一切露出しない。待機は auto-wait 前提の
意味メソッド（`wait_visible` 等）に集約し、EC オブジェクトの値渡しは行わない。
iframe / タブはステートレスなスコープ（context manager）として表現する。
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from contextlib import AbstractContextManager
from typing import Protocol, runtime_checkable

from my_lib.browser.locator import Locator
from my_lib.browser.types import BoundingBox, ScreenshotSpec

# 待機のデフォルトタイムアウト（秒）
DEFAULT_TIMEOUT_SEC: float = 30.0


@runtime_checkable
class Element(Protocol):
    """DOM 要素のハンドル。"""

    @property
    def text(self) -> str:
        """要素のテキスト（前後空白を除去した値）。"""
        ...

    def attr(self, name: str) -> str | None:
        """属性値を取得する（存在しなければ None）。"""
        ...

    def click(self) -> None:
        """要素をクリックする。"""
        ...

    def type(self, text: str, *, sequential: bool = False) -> None:
        """テキストを入力する。

        Args:
            text: 入力文字列。
            sequential: True なら 1 文字ずつ打鍵する（React 制御の OTP 入力等で必要）。

        """
        ...

    def clear(self) -> None:
        """入力値をクリアする。"""
        ...

    def press(self, key: str) -> None:
        """キーを送出する（例: "Enter" / "Escape"）。"""
        ...

    def is_visible(self) -> bool:
        """要素が可視かどうか。"""
        ...

    def scroll_into_view(self) -> None:
        """要素が見える位置までスクロールする。"""
        ...

    def bounding_box(self) -> BoundingBox | None:
        """要素の位置とサイズ（見えていなければ None）。"""
        ...

    def screenshot(self) -> bytes:
        """要素単体のスクリーンショット（PNG バイト列）。"""
        ...

    def find(self, locator: Locator) -> Element | None:
        """この要素を起点に子孫要素を 1 つ検索する。"""
        ...

    def find_all(self, locator: Locator) -> Sequence[Element]:
        """この要素を起点に子孫要素を全件検索する。"""
        ...

    def evaluate(self, script: str, *args: object) -> object:
        """この要素を対象に JS を実行する（Selenium の arguments[0] 相当は第 1 引数の this）。"""
        ...


@runtime_checkable
class FrameScope(Protocol):
    """iframe 内にスコープした操作サブセット。

    フレームは独立したナビゲーションを持たないため、`goto`/`url`/`title` 等は持たず、
    要素検索・待機・JS 実行・スクリーンショットのみを提供する。
    """

    def find(self, locator: Locator) -> Element | None: ...
    def find_all(self, locator: Locator) -> Sequence[Element]: ...
    def exists(self, locator: Locator, *, visible: bool = True) -> bool: ...
    def wait_visible(self, locator: Locator, *, timeout: float = DEFAULT_TIMEOUT_SEC) -> Element: ...
    def wait_clickable(self, locator: Locator, *, timeout: float = DEFAULT_TIMEOUT_SEC) -> Element: ...
    def wait_absent(self, locator: Locator, *, timeout: float = DEFAULT_TIMEOUT_SEC) -> None: ...
    def wait_text(self, locator: Locator, text: str, *, timeout: float = DEFAULT_TIMEOUT_SEC) -> None: ...
    def wait_until(self, predicate_js: str, *, timeout: float = DEFAULT_TIMEOUT_SEC) -> None: ...
    def evaluate(self, script: str, *args: object) -> object: ...
    def screenshot(self, spec: ScreenshotSpec | None = None) -> bytes: ...
    def refresh(self) -> None: ...


@runtime_checkable
class Page(Protocol):
    """1 つのタブに対する操作。"""

    def goto(self, url: str) -> None:
        """URL へ遷移する。"""
        ...

    @property
    def url(self) -> str:
        """現在の URL。"""
        ...

    @property
    def title(self) -> str:
        """現在のタイトル。"""
        ...

    @property
    def content(self) -> str:
        """現在の HTML（page_source 相当）。"""
        ...

    def find(self, locator: Locator) -> Element | None:
        """要素を 1 つ検索する（無ければ None）。"""
        ...

    def find_all(self, locator: Locator) -> Sequence[Element]:
        """要素を全件検索する。"""
        ...

    def exists(self, locator: Locator, *, visible: bool = True) -> bool:
        """要素が存在するか（visible=True なら可視であること）。"""
        ...

    def wait_visible(self, locator: Locator, *, timeout: float = DEFAULT_TIMEOUT_SEC) -> Element:
        """要素が可視になるまで待って返す。"""
        ...

    def wait_clickable(self, locator: Locator, *, timeout: float = DEFAULT_TIMEOUT_SEC) -> Element:
        """要素がクリック可能になるまで待って返す。"""
        ...

    def wait_absent(self, locator: Locator, *, timeout: float = DEFAULT_TIMEOUT_SEC) -> None:
        """要素が消える（不可視になる）まで待つ。"""
        ...

    def wait_text(self, locator: Locator, text: str, *, timeout: float = DEFAULT_TIMEOUT_SEC) -> None:
        """要素に指定テキストが現れるまで待つ。"""
        ...

    def wait_until(self, predicate_js: str, *, timeout: float = DEFAULT_TIMEOUT_SEC) -> None:
        """任意の JS 述語が真を返すまで待つ（画像ロード完了等のカスタム条件）。"""
        ...

    def evaluate(self, script: str, *args: object) -> object:
        """ページコンテキストで JS を実行して結果を返す。"""
        ...

    def screenshot(self, spec: ScreenshotSpec | None = None) -> bytes:
        """スクリーンショット（PNG バイト列）。"""
        ...

    def frame(self, locator: Locator) -> AbstractContextManager[FrameScope]:
        """iframe をスコープとして開く（with を抜けると自動的に元のフレームへ戻る）。"""
        ...

    def refresh(self) -> None:
        """ページを再読み込みする。"""
        ...

    def set_viewport(self, width: int, height: int) -> None:
        """ビューポート（ウィンドウ）サイズを変更する。"""
        ...


@runtime_checkable
class Maintenance(Protocol):
    """キャッシュ・履歴・GC 等の保守操作（内部の CDP を隠蔽する）。"""

    def clear_cache(self) -> None:
        """ブラウザキャッシュを消去する。"""
        ...

    def clear_history(self) -> None:
        """ナビゲーション履歴を消去する。"""
        ...

    def collect_garbage(self) -> None:
        """GC を明示的に走らせる（長時間稼働のメモリ肥大対策）。"""
        ...


@runtime_checkable
class Browser(Protocol):
    """ブラウザ（1 つのコンテキスト）。複数タブを束ねる。"""

    def new_page(self) -> Page:
        """新しいページ（タブ）を開いて返す。"""
        ...

    def tab(self, url: str) -> AbstractContextManager[Page]:
        """新しいタブで URL を開き、with を抜けると閉じて元のタブへ戻る。"""
        ...

    def pages(self) -> Sequence[Page]:
        """現在開いている全ページ。"""
        ...

    @property
    def maintenance(self) -> Maintenance:
        """保守操作インターフェース。"""
        ...

    def close(self) -> None:
        """ブラウザを終了する。"""
        ...


@runtime_checkable
class BrowserSession(Protocol):
    """`(driver, wait)` タプルに代わる、呼び出し側が受け取るセッション。

    store 層・各プロジェクトはこの `BrowserSession` を受け取り、`session.page` を操作する。
    """

    @property
    def browser(self) -> Browser:
        """ブラウザ本体。"""
        ...

    @property
    def page(self) -> Page:
        """既定ページ（最初のタブ）。"""
        ...


def iter_pages(browser: Browser) -> Iterator[Page]:
    """全ページを走査するユーティリティ。"""
    yield from browser.pages()
