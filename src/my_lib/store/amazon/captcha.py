#!/usr/bin/env python3

from __future__ import annotations

import io

import PIL.Image
import selenium.webdriver.common.by
import selenium.webdriver.remote.webdriver
import selenium.webdriver.support
import selenium.webdriver.support.expected_conditions
import selenium.webdriver.support.wait

import my_lib.notify.slack
import my_lib.store.captcha


def resolve(
    driver: selenium.webdriver.remote.webdriver.WebDriver,
    wait: selenium.webdriver.support.wait.WebDriverWait,  # noqa: ARG001
    slack_config: my_lib.notify.slack.HasCaptchaConfig,
    xpath: dict[str, str],
) -> None:
    file_id = my_lib.store.captcha.send_challenge_image_slack(
        slack_config,
        "Amazon Login",
        PIL.Image.open(
            io.BytesIO(
                driver.find_element(selenium.webdriver.common.by.By.XPATH, xpath["image"]).screenshot_as_png
            )
        ),
        "画像 CAPTCHA",
    )

    if file_id is None:
        raise RuntimeError("Failed to send challenge image to Slack")
    captcha = my_lib.store.captcha.recv_response_image_slack(slack_config, file_id)

    if captcha is None:
        raise RuntimeError("CAPTCHA を解決できませんでした。")

    driver.find_element(selenium.webdriver.common.by.By.XPATH, xpath["text"]).send_keys(captcha)
