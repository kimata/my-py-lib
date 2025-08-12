#!/usr/bin/env python3
import io

import PIL.Image
import selenium.webdriver.common.by
import selenium.webdriver.support

import my_lib.notify.slack
import my_lib.store.captcha


def resolve(driver, wait, config, xpath):  # noqa: ARG001
    file_id = my_lib.store.captcha.send_challenge_image_slack(
        config["slack"]["bot_token"],
        config["slack"]["captcha"]["channel"]["id"],
        "Amazon Login",
        PIL.Image.open(
            io.BytesIO(
                driver.find_element(selenium.webdriver.common.by.By.XPATH, xpath["image"]).screenshot_as_png
            )
        ),
        "画像 CAPTCHA",
    )

    captcha = my_lib.store.captcha.recv_response_image_slack(
        config["slack"]["bot_token"], config["slack"]["captcha"]["channel"]["id"], "image", file_id
    )

    if captcha is None:
        raise RuntimeError("CAPTCHA を解決できませんでした。")

    driver.find_element(selenium.webdriver.common.by.By.XPATH, xpath["text"]).send_keys(captcha)
