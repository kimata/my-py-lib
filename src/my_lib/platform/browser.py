"""Stable browser automation exports."""

from my_lib.browser_manager import BrowserManager, BrowserProfile
from my_lib.selenium_util import SeleniumError, clear_cache, create_driver, quit_driver_gracefully

__all__ = [
    "BrowserManager",
    "BrowserProfile",
    "SeleniumError",
    "clear_cache",
    "create_driver",
    "quit_driver_gracefully",
]
