"""Selenium バックエンドの Element 実装（移行期の互換用）。

既存の WebElement を Protocol の Element へ適合させる。`selenium.*` の import は
この Selenium バックエンド内にのみ存在する。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import selenium.webdriver.common.by

from my_lib.browser.locator import Locator

if TYPE_CHECKING:
    from selenium.webdriver.remote.webdriver import WebDriver
    from selenium.webdriver.remote.webelement import WebElement

_BY = selenium.webdriver.common.by.By


def _by_and_value(locator: Locator, *, relative: bool) -> tuple[str, str]:
    if locator.kind == "xpath":
        value = locator.value
        if relative and value.startswith("/"):
            value = "." + value
        return (_BY.XPATH, value)
    return (_BY.CSS_SELECTOR, locator.value)


class SeleniumElement:
    """WebElement をラップした Element 実装。"""

    def __init__(self, driver: WebDriver, element: WebElement) -> None:
        self._driver = driver
        self._el = element

    @property
    def text(self) -> str:
        return (self._el.text or "").strip()

    def attr(self, name: str) -> str | None:
        return self._el.get_attribute(name)

    def click(self) -> None:
        self._el.click()

    def type(self, text: str, *, sequential: bool = False) -> None:
        if sequential:
            for ch in text:
                self._el.send_keys(ch)
        else:
            self._el.send_keys(text)

    def clear(self) -> None:
        self._el.clear()

    def press(self, key: str) -> None:
        import selenium.webdriver.common.keys

        key_const = getattr(selenium.webdriver.common.keys.Keys, key.upper(), key)
        self._el.send_keys(key_const)

    def is_visible(self) -> bool:
        return self._el.is_displayed()

    def scroll_into_view(self) -> None:
        self._driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", self._el)

    def screenshot(self) -> bytes:
        return self._el.screenshot_as_png

    def find(self, locator: Locator) -> SeleniumElement | None:
        by, value = _by_and_value(locator, relative=True)
        found = self._el.find_elements(by, value)
        if not found:
            return None
        return SeleniumElement(self._driver, found[0])

    def find_all(self, locator: Locator) -> list[SeleniumElement]:
        by, value = _by_and_value(locator, relative=True)
        return [SeleniumElement(self._driver, e) for e in self._el.find_elements(by, value)]

    def evaluate(self, script: str, *args: object) -> Any:
        return self._driver.execute_script(script, self._el, *args)
