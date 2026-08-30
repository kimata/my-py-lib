#!/usr/bin/env python3

from __future__ import annotations

import io
from typing import TYPE_CHECKING

import PIL.Image

import my_lib.notify.slack
import my_lib.store.captcha
from my_lib.browser import Xpath

if TYPE_CHECKING:
    from my_lib.browser import Element, Page


def _find(page: Page, xpath: str) -> Element:
    """要素を 1 つ取得する（存在しなければ例外）。"""
    element = page.find(Xpath(xpath))
    if element is None:
        raise RuntimeError(f"要素が見つかりません: {xpath}")
    return element


def resolve(
    page: Page,
    slack_config: my_lib.notify.slack.HasCaptchaConfig,
    xpath: dict[str, str],
) -> None:
    file_id = my_lib.store.captcha.send_challenge_image_slack(
        slack_config,
        "Amazon Login",
        PIL.Image.open(io.BytesIO(_find(page, xpath["image"]).screenshot())),
        "画像 CAPTCHA",
    )

    if file_id is None:
        raise RuntimeError("Failed to send challenge image to Slack")
    captcha = my_lib.store.captcha.recv_response_image_slack(slack_config, file_id)

    if captcha is None:
        raise RuntimeError("CAPTCHA を解決できませんでした。")

    _find(page, xpath["text"]).type(captcha)
