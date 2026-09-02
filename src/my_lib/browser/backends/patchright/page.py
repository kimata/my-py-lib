"""Patchright バックエンドの Page 実装。"""

from __future__ import annotations

import contextlib
from collections.abc import Iterator
from typing import TYPE_CHECKING, Any

from my_lib.browser.backends.patchright.element import PatchrightElement, _to_selector
from my_lib.browser.backends.patchright.frame import PatchrightFrame
from my_lib.browser.exceptions import NavigationError, WaitTimeoutError
from my_lib.browser.locator import Locator
from my_lib.browser.types import ScreenshotSpec

if TYPE_CHECKING:
    from patchright.sync_api import Page as PwPage


class PatchrightPage:
    """Playwright Page をラップした Page 実装。"""

    def __init__(self, pw_page: PwPage) -> None:
        self._page = pw_page

    @property
    def raw(self) -> PwPage:
        """内部の Playwright Page（保守操作・タブ管理から参照する）。"""
        return self._page

    def goto(self, url: str) -> None:
        try:
            self._page.goto(url, wait_until="domcontentloaded")
        except Exception as e:
            raise NavigationError(str(e)) from e

    @property
    def url(self) -> str:
        return self._page.url

    @property
    def title(self) -> str:
        return self._page.title()

    @property
    def content(self) -> str:
        return self._page.content()

    def find(self, locator: Locator) -> PatchrightElement | None:
        loc = self._page.locator(_to_selector(locator, relative=False))
        if loc.count() == 0:
            return None
        return PatchrightElement(loc.first)

    def find_all(self, locator: Locator) -> list[PatchrightElement]:
        loc = self._page.locator(_to_selector(locator, relative=False))
        return [PatchrightElement(loc.nth(i)) for i in range(loc.count())]

    def exists(self, locator: Locator, *, visible: bool = True) -> bool:
        loc = self._page.locator(_to_selector(locator, relative=False))
        if loc.count() == 0:
            return False
        return loc.first.is_visible() if visible else True

    def wait_present(self, locator: Locator, *, timeout: float = 30.0) -> PatchrightElement:
        # NOTE: state="attached" は DOM 存在のみを待つ（可視不問）。
        #       Selenium の presence_of_element_located 相当。
        loc = self._page.locator(_to_selector(locator, relative=False)).first
        try:
            loc.wait_for(state="attached", timeout=timeout * 1000)
        except Exception as e:
            raise WaitTimeoutError(str(e)) from e
        return PatchrightElement(loc)

    def wait_visible(self, locator: Locator, *, timeout: float = 30.0) -> PatchrightElement:
        # NOTE: 複数マッチ時は「いずれかが可視になる」を待つ（Selenium の
        # visibility_of_any_elements_located 相当）。.first 固定だと DOM 先頭の
        # 不可視要素（例: Amazon の hidden な rhf-footer）にロックされ、
        # 後方に可視の要素があってもタイムアウトする。
        loc = self._page.locator(_to_selector(locator, relative=False)).filter(visible=True).first
        try:
            loc.wait_for(state="visible", timeout=timeout * 1000)
        except Exception as e:
            raise WaitTimeoutError(str(e)) from e
        return PatchrightElement(loc)

    def wait_clickable(self, locator: Locator, *, timeout: float = 30.0) -> PatchrightElement:
        # Playwright はクリック時に自動でアクショナビリティを待つため、可視待ちで代替する。
        return self.wait_visible(locator, timeout=timeout)

    def wait_absent(self, locator: Locator, *, timeout: float = 30.0) -> None:
        loc = self._page.locator(_to_selector(locator, relative=False)).first
        try:
            loc.wait_for(state="hidden", timeout=timeout * 1000)
        except Exception as e:
            raise WaitTimeoutError(str(e)) from e

    def wait_text(self, locator: Locator, text: str, *, timeout: float = 30.0) -> None:
        try:
            self._page.locator(_to_selector(locator, relative=False)).first.filter(has_text=text).wait_for(
                state="visible", timeout=timeout * 1000
            )
        except Exception as e:
            raise WaitTimeoutError(str(e)) from e

    def wait_until(self, predicate_js: str, *, timeout: float = 30.0) -> None:
        try:
            self._page.wait_for_function(predicate_js, timeout=timeout * 1000)
        except Exception as e:
            raise WaitTimeoutError(str(e)) from e

    def evaluate(self, script: str, *args: object) -> Any:
        return self._page.evaluate(script, list(args) if args else None)

    def screenshot(self, spec: ScreenshotSpec | None = None) -> bytes:
        full = bool(spec and spec.full_page)
        return self._page.screenshot(full_page=full)

    @contextlib.contextmanager
    def frame(self, locator: Locator) -> Iterator[PatchrightFrame]:
        frame_locator = self._page.frame_locator(_to_selector(locator, relative=False))
        yield PatchrightFrame(self._page, frame_locator)
        # NOTE: FrameLocator はステートレスなので明示的な戻り処理は不要。

    def refresh(self) -> None:
        self._page.reload()

    def set_viewport(self, width: int, height: int) -> None:
        self._page.set_viewport_size({"width": width, "height": height})
