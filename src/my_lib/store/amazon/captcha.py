#!/usr/bin/env python3
import io
import logging
import time

import my_lib.notify.slack
import my_lib.store.captcha
import PIL.Image
import selenium.webdriver.common.by
import selenium.webdriver.support


def resolve_impl(driver, wait, config, xpath):
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
        config["slack"]["bot_token"], config["slack"]["captcha"]["channel"]["id"], file_id
    )

    if captcha is None:
        raise "CAPTCHA を解決できませんでした．"

    driver.find_element(selenium.webdriver.common.by.By.XPATH, xpath["text"]).send_keys(captcha)


def resolve(driver, wait, config):
    if len(driver.find_elements(selenium.webdriver.common.by.By.XPATH, '//button[@type="submit"]')) == 0:
        return

    logging.info("Try to resolve CAPTCHA")

    while True:
        resolve_impl(
            driver,
            wait,
            config,
            {
                "image": '//form[@action="/errors/validateCaptcha"]//img',
                "text": '//input[@id="captchacharacters"]',
            },
        )

        driver.find_element(selenium.webdriver.common.by.By.XPATH, '//button[@type="submit"]').click()

        wait.until(selenium.webdriver.support.expected_conditions.presence_of_all_elements_located)
        time.sleep(0.1)

        if len(driver.find_elements(selenium.webdriver.common.by.By.XPATH, '//button[@type="submit"]')) == 0:
            break

    logging.info("Broke through CAPTCHA")
