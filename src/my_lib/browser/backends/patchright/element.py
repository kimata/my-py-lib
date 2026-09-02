"""Patchright バックエンドの Element 実装。

Playwright の Locator（オートウェイト付き）または ElementHandle を 1 要素へ束ねて包む。
`patchright.*` の型はこのバックエンド内にのみ存在する。

NOTE: find / find_all の結果は ElementHandle で返す。
      Locator は操作のたびにセレクタを再評価してオートウェイトするため、検索結果一覧の
      ように数十〜数百要素を走査して属性を読むだけの用途では 1 要素あたり数秒かかり
      （ラクマで 20 件の取得に 535 秒）、Selenium 時代の要素ハンドル直接操作より
      2 桁遅かった。ElementHandle なら同じ処理が 2 秒で済む。
      wait_* 系が返す要素は操作対象（クリック・入力）なのでオートウェイト付きの
      Locator のまま維持する。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from my_lib.browser.locator import Locator
from my_lib.browser.types import BoundingBox

if TYPE_CHECKING:
    from patchright.sync_api import ElementHandle as PwElementHandle
    from patchright.sync_api import Locator as PwLocator


def _to_selector(locator: Locator, *, relative: bool) -> str:
    """共通ロケータを Playwright セレクタ文字列へ変換する。

    relative=True（要素起点の子孫検索）で XPath が "/" 始まりの場合は、
    ドキュメント全体でなく起点要素配下に絞るため "." を前置する。
    """
    if locator.kind == "xpath":
        value = locator.value
        if relative and value.startswith("/"):
            value = "." + value
        return f"xpath={value}"
    return f"css={locator.value}"


class PatchrightElement:
    """Playwright の Locator または ElementHandle をラップした Element 実装。"""

    def __init__(self, target: PwLocator | PwElementHandle) -> None:
        # ElementHandle は query_selector_all を持ち、Locator は持たない
        self._handle: PwElementHandle | None = None
        self._loc: PwLocator | None = None
        if callable(getattr(target, "query_selector_all", None)):
            self._handle = cast("PwElementHandle", target)
        else:
            self._loc = cast("PwLocator", target)

    @property
    def _target(self) -> PwLocator | PwElementHandle:
        if self._handle is not None:
            return self._handle
        return cast("PwLocator", self._loc)

    @property
    def text(self) -> str:
        return (self._target.inner_text() or "").strip()

    def attr(self, name: str) -> str | None:
        # NOTE: Selenium の get_attribute は href/src を解決済みの絶対 URL で返す。
        #       Playwright の get_attribute は生の属性値（相対パス）を返すため、
        #       挙動を合わせるべく href/src は DOM プロパティ（絶対 URL）を優先して返す。
        if name in ("href", "src"):
            resolved = self._target.evaluate("(el, prop) => el[prop] || null", name)
            if resolved:
                return str(resolved)
        return self._target.get_attribute(name)

    def click(self) -> None:
        self._target.click()

    def type(self, text: str, *, sequential: bool = False) -> None:
        if not sequential:
            self._target.fill(text)
            return
        self._target.click()
        if self._handle is not None:
            self._handle.type(text, delay=80)
        else:
            cast("PwLocator", self._loc).press_sequentially(text, delay=80)

    def clear(self) -> None:
        self._target.fill("")

    def press(self, key: str) -> None:
        self._target.press(key)

    def is_visible(self) -> bool:
        return self._target.is_visible()

    def scroll_into_view(self) -> None:
        # NOTE: scroll_into_view_if_needed はアクション可能性チェックを伴い、
        #       非可視要素に対してはタイムアウト（既定 30 秒）まで待つ。
        #       Selenium 実装と同じく JS で即時にスクロールする。
        self._target.evaluate("el => el.scrollIntoView({block: 'center'})")

    def bounding_box(self) -> BoundingBox | None:
        box = self._target.bounding_box()
        if box is None:
            return None
        return BoundingBox(x=box["x"], y=box["y"], width=box["width"], height=box["height"])

    def screenshot(self) -> bytes:
        return self._target.screenshot()

    def find(self, locator: Locator) -> PatchrightElement | None:
        selector = _to_selector(locator, relative=True)
        if self._handle is not None:
            found = self._handle.query_selector(selector)
            return PatchrightElement(found) if found is not None else None
        handles = cast("PwLocator", self._loc).locator(selector).element_handles()
        return PatchrightElement(handles[0]) if handles else None

    def find_all(self, locator: Locator) -> list[PatchrightElement]:
        selector = _to_selector(locator, relative=True)
        if self._handle is not None:
            handles = self._handle.query_selector_all(selector)
        else:
            handles = cast("PwLocator", self._loc).locator(selector).element_handles()
        return [PatchrightElement(h) for h in handles]

    def evaluate(self, script: str, *args: object) -> Any:
        # NOTE: Playwright の evaluate は第 1 引数に要素を束ねる。追加引数は 2 要素目以降。
        if args:
            return self._target.evaluate(script, list(args))
        return self._target.evaluate(script)
