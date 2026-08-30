"""Patchright バックエンドの Element 実装。

Playwright の Locator（オートウェイト付き）を 1 要素へ束ねて包む。
`patchright.*` の型はこのバックエンド内にのみ存在する。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from my_lib.browser.locator import Locator
from my_lib.browser.types import BoundingBox

if TYPE_CHECKING:
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
    """Playwright Locator をラップした Element 実装。"""

    def __init__(self, pw_locator: PwLocator) -> None:
        self._loc = pw_locator

    @property
    def text(self) -> str:
        return (self._loc.inner_text() or "").strip()

    def attr(self, name: str) -> str | None:
        # NOTE: Selenium の get_attribute は href/src を解決済みの絶対 URL で返す。
        #       Playwright の get_attribute は生の属性値（相対パス）を返すため、
        #       挙動を合わせるべく href/src は DOM プロパティ（絶対 URL）を優先して返す。
        if name in ("href", "src"):
            resolved = self._loc.evaluate("(el, prop) => el[prop] || null", name)
            if resolved:
                return str(resolved)
        return self._loc.get_attribute(name)

    def click(self) -> None:
        self._loc.click()

    def type(self, text: str, *, sequential: bool = False) -> None:
        if sequential:
            self._loc.click()
            self._loc.press_sequentially(text, delay=80)
        else:
            self._loc.fill(text)

    def clear(self) -> None:
        self._loc.fill("")

    def press(self, key: str) -> None:
        self._loc.press(key)

    def is_visible(self) -> bool:
        return self._loc.is_visible()

    def scroll_into_view(self) -> None:
        self._loc.scroll_into_view_if_needed()

    def bounding_box(self) -> BoundingBox | None:
        box = self._loc.bounding_box()
        if box is None:
            return None
        return BoundingBox(x=box["x"], y=box["y"], width=box["width"], height=box["height"])

    def screenshot(self) -> bytes:
        return self._loc.screenshot()

    def find(self, locator: Locator) -> PatchrightElement | None:
        child = self._loc.locator(_to_selector(locator, relative=True))
        if child.count() == 0:
            return None
        return PatchrightElement(child.first)

    def find_all(self, locator: Locator) -> list[PatchrightElement]:
        child = self._loc.locator(_to_selector(locator, relative=True))
        return [PatchrightElement(child.nth(i)) for i in range(child.count())]

    def evaluate(self, script: str, *args: object) -> Any:
        # NOTE: Playwright の evaluate は第 1 引数に要素を束ねる。追加引数は 2 要素目以降。
        if args:
            return self._loc.evaluate(script, list(args))
        return self._loc.evaluate(script)
