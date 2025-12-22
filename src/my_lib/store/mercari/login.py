#!/usr/bin/env python3

from __future__ import annotations

import logging
import pathlib
import random
import time
from typing import Any

import selenium.common.exceptions
import selenium.webdriver.common.by
import selenium.webdriver.remote.webdriver
import selenium.webdriver.remote.webelement
import selenium.webdriver.support
import selenium.webdriver.support.ui
import selenium.webdriver.support.wait

import my_lib.notify.slack
import my_lib.selenium_util
import my_lib.store.captcha
import my_lib.store.mercari.config

_LINE_LOGIN_TIMEOUT: int = 30

_LOGIN_URL: str = "https://jp.mercari.com"


def execute(
    driver: selenium.webdriver.remote.webdriver.WebDriver,
    wait: selenium.webdriver.support.wait.WebDriverWait,
    mercari_login: my_lib.store.mercari.config.MercariLoginConfig,
    line_login: my_lib.store.mercari.config.LineLoginConfig,
    slack_config: my_lib.notify.slack.SlackConfig | None,
    dump_path: pathlib.Path,
) -> None:  # noqa: PLR0913
    try:
        # NOTE: エラーが起きた後とかだと、一発でページが表示されないことがあるので、事前に一回アクセスさせる。
        logging.info("メルカリにアクセスします。")
        driver.get(_LOGIN_URL)
        wait.until(
            selenium.webdriver.support.expected_conditions.presence_of_element_located(
                (selenium.webdriver.common.by.By.XPATH, "//footer")
            )
        )

        _execute_impl(driver, wait, mercari_login, line_login, slack_config, dump_path)
    except Exception:
        logging.exception("ログインをリトライします。")
        my_lib.selenium_util.dump_page(driver, int(random.random() * 100), dump_path)  # noqa: S311
        # NOTE: 1回だけリトライする
        time.sleep(10)
        _execute_impl(driver, wait, mercari_login, line_login, slack_config, dump_path)


def _execute_impl(
    driver: selenium.webdriver.remote.webdriver.WebDriver,
    wait: selenium.webdriver.support.wait.WebDriverWait,
    mercari_login: my_lib.store.mercari.config.MercariLoginConfig,  # noqa: ARG001
    line_login: my_lib.store.mercari.config.LineLoginConfig,
    slack_config: my_lib.notify.slack.SlackConfig | None,
    dump_path: pathlib.Path,  # noqa: ARG001
) -> None:
    logging.info("ログインを行います。")
    driver.get(_LOGIN_URL)

    wait.until(
        selenium.webdriver.support.expected_conditions.presence_of_element_located(
            (
                selenium.webdriver.common.by.By.XPATH,
                '//button[contains(@class, "iconButton") and @aria-label="お知らせ"]',
            )
        )
    )

    my_lib.selenium_util.click_xpath(driver, '//button[contains(text(), "はじめる")]')
    time.sleep(1)

    account_button = driver.find_elements(
        selenium.webdriver.common.by.By.XPATH,
        '//button[@data-testid="account-button"]',
    )

    if len(account_button) != 0:
        logging.info("既にログイン済みでした。")
        return

    my_lib.selenium_util.click_xpath(driver, '//button[contains(text(), "ログイン")]', wait)

    wait.until(
        selenium.webdriver.support.expected_conditions.presence_of_element_located(
            (selenium.webdriver.common.by.By.XPATH, '//h1[contains(text(), "ログイン")]')
        )
    )

    _login_via_line(driver, wait, line_login, slack_config)

    # time.sleep(2)
    # if len(driver.find_elements(selenium.webdriver.common.by.By.XPATH, '//div[@id="recaptchaV2"]')) != 0:
    #     logging.warning("画像認証が要求されました。")
    #     captcha.resolve_mp3(driver, wait)
    #     logging.warning("画像認証を突破しました。")
    #     click_xpath(driver, '//button[contains(text(), "ログイン")]', wait)

    wait.until(
        selenium.webdriver.support.expected_conditions.presence_of_element_located(
            (selenium.webdriver.common.by.By.XPATH, '//h1[contains(text(), "電話番号の確認")]')
        )
    )

    logging.info("認証番号の対応を行います。")

    code: str | None = None
    ts: str | None = None
    if slack_config is not None:
        logging.info("Slack に SMS で送られてきた認証番号を入力してください")
        ts = my_lib.store.captcha.send_request_text_slack(
            slack_config,
            "Mercari",
            "SMS で送られてきた認証番号を入力してください",
        )
        if ts is None:
            raise RuntimeError("Failed to send request text to Slack")
        code = my_lib.store.captcha.recv_response_text_slack(slack_config, ts)
    else:
        code = input("SMS で送られてきた認証番号を入力してください: ")

    if code is None:
        raise RuntimeError("Failed to receive authentication code")
    driver.find_element(selenium.webdriver.common.by.By.XPATH, '//input[@name="code"]').send_keys(code)
    my_lib.selenium_util.click_xpath(driver, '//button[contains(text(), "認証して完了する")]', wait)

    wait.until(
        selenium.webdriver.support.expected_conditions.presence_of_element_located(
            (
                selenium.webdriver.common.by.By.XPATH,
                '//div[@class="merNavigationTopMenu"]',
            )
        )
    )

    wait.until(
        selenium.webdriver.support.expected_conditions.element_to_be_clickable(
            (
                selenium.webdriver.common.by.By.XPATH,
                '//button[@data-testid="account-button"]',
            )
        )
    )

    if slack_config is not None and ts is not None:
        my_lib.notify.slack.send(
            slack_config,
            slack_config.captcha.channel.name,
            my_lib.notify.slack.format_simple("CAPTCHA", "成功しました"),
            thread_ts=ts,
        )

    logging.info("ログインに成功しました。")


def _login_via_line(
    driver: selenium.webdriver.remote.webdriver.WebDriver,
    wait: selenium.webdriver.support.wait.WebDriverWait,
    line_login: my_lib.store.mercari.config.LineLoginConfig,
    slack_config: my_lib.notify.slack.SlackConfig | None,
) -> None:
    my_lib.selenium_util.click_xpath(driver, '//button[span[contains(text(), "LINEでログイン")]]', wait)

    wait.until(selenium.webdriver.support.expected_conditions.title_contains("LINE Login"))

    if my_lib.selenium_util.xpath_exists(driver, '//input[@name="tid"]'):
        my_lib.selenium_util.input_xpath(driver, '//input[@name="tid"]', line_login.user)
        my_lib.selenium_util.input_xpath(driver, '//input[@name="tpasswd"]', line_login.password)
        my_lib.selenium_util.click_xpath(driver, '//button[contains(text(), "ログイン")]', wait)
    else:
        my_lib.selenium_util.click_xpath(driver, '//button[.//span[normalize-space()="ログイン"]]', wait)

    wait.until(
        selenium.webdriver.support.expected_conditions.presence_of_all_elements_located(
            (selenium.webdriver.common.by.By.XPATH, "//body")
        )
    )

    if "LINE Login" in driver.title:
        code = my_lib.selenium_util.get_text(driver, '//p[contains(@class, "Number")]', "?", wait)

        if slack_config is not None:
            my_lib.store.captcha.send_request_text_slack(
                slack_config,
                "LINE",
                f"LINE アプリで認証番号「{code}」を入力してください。",
            )
        logging.info("LINE アプリで認証番号「%s」を入力してください。", code)

        login_wait = selenium.webdriver.support.ui.WebDriverWait(driver, _LINE_LOGIN_TIMEOUT)

        elem: selenium.webdriver.remote.webelement.WebElement = login_wait.until(
            selenium.webdriver.support.expected_conditions.any_of(
                selenium.webdriver.support.expected_conditions.presence_of_element_located(
                    (
                        selenium.webdriver.common.by.By.XPATH,
                        '//button[contains(normalize-space(.), "許可する")]',
                    )
                ),
                selenium.webdriver.support.expected_conditions.presence_of_element_located(
                    (selenium.webdriver.common.by.By.XPATH, '//h1[contains(text(), "電話番号の確認")]')
                ),
            )
        )

        if elem.tag_name == "button":
            my_lib.selenium_util.click_xpath(driver, '//button[contains(normalize-space(.), "許可する")]')
            my_lib.selenium_util.click_xpath(driver, '//span[contains(normalize-space(.), "戻る")]', wait)

        wait.until(
            selenium.webdriver.support.expected_conditions.presence_of_element_located(
                (
                    selenium.webdriver.common.by.By.XPATH,
                    '//h1[contains(text(), "電話番号の確認")]',
                )
            )
        )
