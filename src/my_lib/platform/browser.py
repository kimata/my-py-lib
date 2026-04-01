"""Stable browser automation exports with lazy heavy imports."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from selenium.webdriver.remote.webdriver import WebDriver

    from my_lib.browser_manager import BrowserManager, BrowserProfile
    from my_lib.selenium_util import SeleniumError


def __getattr__(name: str) -> Any:
    if name in {"BrowserManager", "BrowserProfile"}:
        from my_lib import browser_manager

        value = getattr(browser_manager, name)
        globals()[name] = value
        return value
    if name == "SeleniumError":
        from my_lib import selenium_util

        value = selenium_util.SeleniumError
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def create_driver(*args: Any, **kwargs: Any) -> WebDriver:
    from my_lib import selenium_util

    return selenium_util.create_driver(*args, **kwargs)


def quit_driver_gracefully(driver: WebDriver, wait_sec: float = 5) -> None:
    from my_lib import selenium_util

    selenium_util.quit_driver_gracefully(driver, wait_sec=wait_sec)


def clear_cache(driver: WebDriver) -> None:
    from my_lib import selenium_util

    selenium_util.clear_cache(driver)


__all__ = [
    "BrowserManager",
    "BrowserProfile",
    "SeleniumError",
    "clear_cache",
    "create_driver",
    "quit_driver_gracefully",
]
