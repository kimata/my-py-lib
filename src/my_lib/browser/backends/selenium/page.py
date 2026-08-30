"""Selenium バックエンドの Page / Frame 実装（移行期の互換用）。"""

from __future__ import annotations

import contextlib
from collections.abc import Iterator
from typing import TYPE_CHECKING, Any

import selenium.common.exceptions
import selenium.webdriver.support.expected_conditions as ec
import selenium.webdriver.support.ui

from my_lib.browser.backends.selenium.element import SeleniumElement, _by_and_value
from my_lib.browser.exceptions import NavigationError, SessionError, WaitTimeoutError
from my_lib.browser.locator import Locator
from my_lib.browser.types import ScreenshotSpec

if TYPE_CHECKING:
    from selenium.webdriver.remote.webdriver import WebDriver
    from selenium.webdriver.support.wait import WebDriverWait


def _wait(driver: WebDriver, timeout: float) -> WebDriverWait:
    return selenium.webdriver.support.ui.WebDriverWait(driver, timeout)


class _SeleniumScope:
    """Page / Frame 共通の要素検索・待機ロジック（driver のカレントフレームに解決する）。"""

    def __init__(self, driver: WebDriver) -> None:
        self._driver = driver

    def find(self, locator: Locator) -> SeleniumElement | None:
        by, value = _by_and_value(locator, relative=False)
        found = self._driver.find_elements(by, value)
        if not found:
            return None
        return SeleniumElement(self._driver, found[0])

    def find_all(self, locator: Locator) -> list[SeleniumElement]:
        by, value = _by_and_value(locator, relative=False)
        return [SeleniumElement(self._driver, e) for e in self._driver.find_elements(by, value)]

    def exists(self, locator: Locator, *, visible: bool = True) -> bool:
        by, value = _by_and_value(locator, relative=False)
        found = self._driver.find_elements(by, value)
        if not found:
            return False
        return found[0].is_displayed() if visible else True

    def wait_visible(self, locator: Locator, *, timeout: float = 30.0) -> SeleniumElement:
        by, value = _by_and_value(locator, relative=False)
        try:
            el = _wait(self._driver, timeout).until(ec.visibility_of_element_located((by, value)))
        except selenium.common.exceptions.TimeoutException as e:
            raise WaitTimeoutError(str(e)) from e
        return SeleniumElement(self._driver, el)

    def wait_clickable(self, locator: Locator, *, timeout: float = 30.0) -> SeleniumElement:
        by, value = _by_and_value(locator, relative=False)
        try:
            el = _wait(self._driver, timeout).until(ec.element_to_be_clickable((by, value)))
        except selenium.common.exceptions.TimeoutException as e:
            raise WaitTimeoutError(str(e)) from e
        return SeleniumElement(self._driver, el)

    def wait_absent(self, locator: Locator, *, timeout: float = 30.0) -> None:
        by, value = _by_and_value(locator, relative=False)
        try:
            _wait(self._driver, timeout).until(ec.invisibility_of_element_located((by, value)))
        except selenium.common.exceptions.TimeoutException as e:
            raise WaitTimeoutError(str(e)) from e

    def wait_text(self, locator: Locator, text: str, *, timeout: float = 30.0) -> None:
        by, value = _by_and_value(locator, relative=False)
        try:
            _wait(self._driver, timeout).until(ec.text_to_be_present_in_element((by, value), text))
        except selenium.common.exceptions.TimeoutException as e:
            raise WaitTimeoutError(str(e)) from e

    def wait_until(self, predicate_js: str, *, timeout: float = 30.0) -> None:
        try:
            _wait(self._driver, timeout).until(lambda d: d.execute_script(predicate_js))
        except selenium.common.exceptions.TimeoutException as e:
            raise WaitTimeoutError(str(e)) from e

    def evaluate(self, script: str, *args: object) -> Any:
        return self._driver.execute_script(script, *args)

    def screenshot(self, spec: ScreenshotSpec | None = None) -> bytes:
        # NOTE: Selenium は全画面スクショの直接指定が無いため spec.full_page は無視する。
        _ = spec
        return self._driver.get_screenshot_as_png()

    def refresh(self) -> None:
        self._driver.refresh()


class SeleniumFrame(_SeleniumScope):
    """iframe にスコープした操作（switch_to はコンテキストマネージャ内に閉じ込める）。"""


class SeleniumPage(_SeleniumScope):
    """WebDriver をラップした Page 実装。"""

    def __init__(self, driver: WebDriver) -> None:
        super().__init__(driver)

    @property
    def raw(self) -> WebDriver:
        return self._driver

    def goto(self, url: str) -> None:
        try:
            self._driver.get(url)
        except selenium.common.exceptions.InvalidSessionIdException as e:
            raise SessionError(str(e)) from e
        except selenium.common.exceptions.WebDriverException as e:
            raise NavigationError(str(e)) from e

    @property
    def url(self) -> str:
        return self._driver.current_url

    @property
    def title(self) -> str:
        return self._driver.title

    @property
    def content(self) -> str:
        return self._driver.page_source

    def set_viewport(self, width: int, height: int) -> None:
        self._driver.set_window_size(width, height)

    @contextlib.contextmanager
    def frame(self, locator: Locator) -> Iterator[SeleniumFrame]:
        by, value = _by_and_value(locator, relative=False)
        element = self._driver.find_element(by, value)
        self._driver.switch_to.frame(element)
        try:
            yield SeleniumFrame(self._driver)
        finally:
            self._driver.switch_to.default_content()
