"""Patchright バックエンドの iframe スコープ実装。

Selenium の ``switch_to.frame`` / ``default_content`` のステートフルモデルを廃し、
`with page.frame(locator) as frame:` の間だけフレーム内へスコープする。
Playwright の FrameLocator（ステートレス）で実装するため、明示的な「戻る」操作は不要。
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

from my_lib.browser.backends.patchright.element import PatchrightElement, _to_selector
from my_lib.browser.exceptions import WaitTimeoutError
from my_lib.browser.locator import Locator
from my_lib.browser.types import ScreenshotSpec

if TYPE_CHECKING:
    from patchright.sync_api import FrameLocator as PwFrameLocator
    from patchright.sync_api import Page as PwPage


class PatchrightFrame:
    """iframe 内にスコープした Page 相当。captcha 等で必要な操作サブセットを提供する。"""

    def __init__(self, pw_page: PwPage, frame_locator: PwFrameLocator) -> None:
        self._page = pw_page
        self._frame = frame_locator

    def find(self, locator: Locator) -> PatchrightElement | None:
        # NOTE: find / find_all は ElementHandle で返す（理由は element.py 冒頭の NOTE 参照）。
        handles = self._frame.locator(_to_selector(locator, relative=False)).element_handles()
        return PatchrightElement(handles[0]) if handles else None

    def find_all(self, locator: Locator) -> list[PatchrightElement]:
        handles = self._frame.locator(_to_selector(locator, relative=False)).element_handles()
        return [PatchrightElement(h) for h in handles]

    def exists(self, locator: Locator, *, visible: bool = True) -> bool:
        loc = self._frame.locator(_to_selector(locator, relative=False))
        if loc.count() == 0:
            return False
        return loc.first.is_visible() if visible else True

    def wait_present(self, locator: Locator, *, timeout: float = 30.0) -> PatchrightElement:
        # NOTE: state="attached" は DOM 存在のみを待つ（可視不問）。
        loc = self._frame.locator(_to_selector(locator, relative=False)).first
        try:
            loc.wait_for(state="attached", timeout=timeout * 1000)
        except Exception as e:
            raise WaitTimeoutError(str(e)) from e
        return PatchrightElement(loc)

    def wait_visible(self, locator: Locator, *, timeout: float = 30.0) -> PatchrightElement:
        loc = self._frame.locator(_to_selector(locator, relative=False)).first
        try:
            loc.wait_for(state="visible", timeout=timeout * 1000)
        except Exception as e:
            raise WaitTimeoutError(str(e)) from e
        return PatchrightElement(loc)

    def wait_clickable(self, locator: Locator, *, timeout: float = 30.0) -> PatchrightElement:
        # Playwright はクリック時に自動でアクショナビリティを待つため、可視待ちで代替する。
        return self.wait_visible(locator, timeout=timeout)

    def wait_absent(self, locator: Locator, *, timeout: float = 30.0) -> None:
        loc = self._frame.locator(_to_selector(locator, relative=False)).first
        try:
            loc.wait_for(state="hidden", timeout=timeout * 1000)
        except Exception as e:
            raise WaitTimeoutError(str(e)) from e

    def wait_text(self, locator: Locator, text: str, *, timeout: float = 30.0) -> None:
        deadline = timeout
        step = 0.5
        while deadline > 0:
            el = self.find(locator)
            if el is not None and text in el.text:
                return
            time.sleep(step)
            deadline -= step
        raise WaitTimeoutError(f"text {text!r} not found in {locator}")

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

    def refresh(self) -> None:
        self._page.reload()
