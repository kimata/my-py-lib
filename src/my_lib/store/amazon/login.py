#!/usr/bin/env python3
"""
Amazon へのログインをを行います。

Usage:
  login.py [-c CONFIG] [-t TARGET] [-D]

Options:
  -c CONFIG         : CONFIG を設定ファイルとして読み込んで実行します。[default: tests/fixtures/config.example.yaml]
  -D                : デバッグモードで動作します。
"""

from __future__ import annotations

import io
import logging
import pathlib
import random
import time

import PIL.Image
import selenium.webdriver.common.by
import selenium.webdriver.remote.webdriver
import selenium.webdriver.support
import selenium.webdriver.support.expected_conditions
import selenium.webdriver.support.wait

import my_lib.notify.slack
import my_lib.selenium_util
import my_lib.store.amazon.captcha
import my_lib.store.captcha
from my_lib.store.amazon.config import AmazonLoginConfig

_LOGIN_URL: str = "https://www.amazon.co.jp/ap/signin?openid.pape.max_auth_age=0&openid.return_to=https%3A%2F%2Fwww.amazon.co.jp%2Fref%3Dnav_signin&openid.identity=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0%2Fidentifier_select&openid.assoc_handle=jpflex&openid.mode=checkid_setup&openid.claimed_id=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0%2Fidentifier_select&openid.ns=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0"

_LOGIN_MARK_XPATH: str = '//span[contains(text(), "アカウント＆リスト")]'
_WAIT_COUNT: int = 40


def _resolve_puzzle(
    driver: selenium.webdriver.remote.webdriver.WebDriver,
    wait: selenium.webdriver.support.wait.WebDriverWait,
    slack_config: my_lib.notify.slack.HasCaptchaConfig,
) -> None:
    logging.info("Try to resolve PUZZLE")

    my_lib.store.amazon.captcha.resolve(
        driver,
        wait,
        slack_config,
        {"image": '//img[@alt="captcha"]', "text": '//input[@name="cvf_captcha_input"]'},
    )

    driver.find_element(
        selenium.webdriver.common.by.By.XPATH, '//input[@name="cvf_captcha_captcha_action"]'
    ).click()

    wait.until(
        selenium.webdriver.support.expected_conditions.presence_of_element_located(
            (
                selenium.webdriver.common.by.By.XPATH,
                '//div[contains(@class, "footer") or contains(@class, "Footer")]',
            )
        )
    )
    time.sleep(0.1)


def _handle_email_input(
    driver: selenium.webdriver.remote.webdriver.WebDriver,
    login_config: AmazonLoginConfig,
) -> None:
    """メールアドレス入力処理"""
    email_xpath = '//input[@type="email" and (@id="ap_email_login" or @id="ap_email")]'
    if my_lib.selenium_util.xpath_exists(driver, email_xpath):
        logging.debug("Input email")
        email_input = driver.find_element(selenium.webdriver.common.by.By.XPATH, email_xpath)
        email_input.clear()
        email_input.send_keys(login_config.user)

        logging.debug("Click continue")
        if my_lib.selenium_util.xpath_exists(driver, '//input[@type="submit"]'):
            driver.find_element(selenium.webdriver.common.by.By.XPATH, '//input[@type="submit"]').click()
            time.sleep(3)


def _handle_password_input(
    driver: selenium.webdriver.remote.webdriver.WebDriver,
    wait: selenium.webdriver.support.wait.WebDriverWait,
    login_config: AmazonLoginConfig,
    slack_config: my_lib.notify.slack.HasCaptchaConfig | None,
) -> None:
    """パスワード入力処理"""
    if not my_lib.selenium_util.xpath_exists(driver, '//input[@id="ap_password"]'):
        return

    logging.debug("Input password")
    pass_input = wait.until(
        selenium.webdriver.support.expected_conditions.element_to_be_clickable(
            (selenium.webdriver.common.by.By.XPATH, '//input[@id="ap_password"]')
        )
    )
    driver.execute_script(
        "arguments[0].value = arguments[1];",
        pass_input,
        login_config.password,
    )

    if my_lib.selenium_util.xpath_exists(driver, '//input[@name="rememberMe"]'):
        remember_checkbox = driver.find_element(
            selenium.webdriver.common.by.By.XPATH, '//input[@name="rememberMe"]'
        )
        if not remember_checkbox.get_attribute("checked"):
            logging.debug("Check remember")
            remember_checkbox.click()

    if my_lib.selenium_util.xpath_exists(driver, '//input[@id="auth-captcha-guess"]'):
        if slack_config is None:
            raise ValueError("captcha 設定がありません")
        my_lib.store.amazon.captcha.resolve(
            driver,
            wait,
            slack_config,
            {
                "image": '//img[@id="auth-captcha-image"]',
                "text": '//input[@id="auth-captcha-guess"]',
            },
        )

    time.sleep(0.1)

    logging.debug("Click submit")
    submit_button = driver.find_element(selenium.webdriver.common.by.By.XPATH, '//input[@id="signInSubmit"]')
    driver.execute_script("arguments[0].click();", submit_button)

    wait.until(
        selenium.webdriver.support.expected_conditions.presence_of_element_located(
            (
                selenium.webdriver.common.by.By.XPATH,
                '//div[contains(@class, "footer") or contains(@class, "Footer")]',
            )
        )
    )


def _handle_quiz(
    driver: selenium.webdriver.remote.webdriver.WebDriver,
    slack_config: my_lib.notify.slack.HasCaptchaConfig,
    dump_path: pathlib.Path,
) -> None:
    if not my_lib.selenium_util.xpath_exists(driver, '//h1[contains(normalize-space(.), "クイズ")]'):
        return

    file_id = my_lib.store.captcha.send_challenge_image_slack(
        slack_config,
        "Amazon Login",
        PIL.Image.open(
            io.BytesIO(
                driver.find_element(
                    selenium.webdriver.common.by.By.XPATH, '//div[contains(@class, "amzn-captcha-modal")]'
                ).screenshot_as_png
            )
        ),
        "画像クイズ",
    )

    if file_id is None:
        raise RuntimeError("Failed to send challenge image to Slack")
    captcha = my_lib.store.captcha.recv_response_image_slack(slack_config, file_id)

    if captcha is None:
        raise RuntimeError("クイズを解決できませんでした。")

    digits = [int(ch) for ch in captcha if ch.isdigit()]
    for digit in digits:
        xpath = f'//canvas/button[normalize-space(text())="{digit}"]'
        button = driver.find_element(selenium.webdriver.common.by.By.XPATH, xpath)
        button.click()
        time.sleep(0.2)

    my_lib.selenium_util.dump_page(
        driver,
        int(random.random() * 100),  # noqa: S311
        dump_path,
    )

    driver.find_element(
        selenium.webdriver.common.by.By.XPATH, '//button[@id="amzn-btn-verify-internal"]'
    ).click()
    time.sleep(2)


def _handle_security_check(
    driver: selenium.webdriver.remote.webdriver.WebDriver,
    dump_path: pathlib.Path,
) -> None:
    """セキュリティチェック画面の処理"""
    security_xpath = (
        '//span[contains(@class, "a-size-base-plus") and '
        '(contains(., "確認コードを入力する") or contains(., "セキュリティ"))]'
    )
    if not my_lib.selenium_util.xpath_exists(driver, security_xpath):
        return

    for i in range(_WAIT_COUNT):
        security_check_xpath = '//span[contains(@class, "a-size-base-plus") and contains(., "セキュリティ")]'
        if not my_lib.selenium_util.xpath_exists(driver, security_check_xpath):
            my_lib.selenium_util.dump_page(
                driver,
                int(random.random() * 100),  # noqa: S311
                dump_path,
            )
            logging.info("Security check finished!")
            break

        logging.info("Waiting for security check... (%d/%d)", i + 1, _WAIT_COUNT)
        time.sleep(2)

    for i in range(_WAIT_COUNT):
        wait_xpath = '//span[contains(@class, "a-size-base") and contains(., "少しお待ちください")]'
        if not my_lib.selenium_util.xpath_exists(driver, wait_xpath):
            my_lib.selenium_util.dump_page(
                driver,
                int(random.random() * 100),  # noqa: S311
                dump_path,
            )
            logging.info("Acknowledged!")
            break

        logging.info("Waiting for acknowledge... (%d/%d)", i + 1, _WAIT_COUNT)
        time.sleep(2)


def _execute_impl(
    driver: selenium.webdriver.remote.webdriver.WebDriver,
    wait: selenium.webdriver.support.wait.WebDriverWait,
    login_config: AmazonLoginConfig,
    slack_config: my_lib.notify.slack.HasCaptchaConfig | None,
    login_mark_xpath: str,
) -> None:
    wait.until(
        selenium.webdriver.support.expected_conditions.presence_of_element_located(
            (
                selenium.webdriver.common.by.By.XPATH,
                '//div[contains(@class, "footer") or contains(@class, "Footer")]',
            )
        )
    )

    if my_lib.selenium_util.xpath_exists(driver, login_mark_xpath):
        logging.info("Login succeeded")
        return

    if my_lib.selenium_util.xpath_exists(driver, '//input[@name="cvf_captcha_input"]'):
        if slack_config is None:
            raise ValueError("captcha 設定がありません")
        _resolve_puzzle(driver, wait, slack_config)

    _handle_email_input(driver, login_config)
    _handle_password_input(driver, wait, login_config, slack_config)

    if slack_config is not None:
        _handle_quiz(driver, slack_config, login_config.dump_path)
    _handle_security_check(driver, login_config.dump_path)

    wait.until(
        selenium.webdriver.support.expected_conditions.presence_of_element_located(
            (
                selenium.webdriver.common.by.By.XPATH,
                '//div[contains(@class, "footer") or contains(@class, "Footer")]',
            )
        )
    )
    time.sleep(0.1)


def execute(
    driver: selenium.webdriver.remote.webdriver.WebDriver,
    wait: selenium.webdriver.support.wait.WebDriverWait,
    login_config: AmazonLoginConfig,
    slack_config: my_lib.notify.slack.HasCaptchaConfig | None = None,
    login_url: str = _LOGIN_URL,
    login_mark_xpath: str = _LOGIN_MARK_XPATH,
    retry: int = 2,
) -> bool:  # noqa: PLR0913
    logging.info("Login start")

    driver.get(login_url)

    for i in range(retry):
        _execute_impl(driver, wait, login_config, slack_config, login_mark_xpath)

        if my_lib.selenium_util.xpath_exists(driver, login_mark_xpath):
            logging.info("Login sccessful!")
            return True

        if i != (retry - 1):
            logging.warning("Login retry")

            my_lib.selenium_util.dump_page(
                driver,
                int(random.random() * 100),  # noqa: S311
                login_config.dump_path,
            )

    logging.error("Login fail")

    return False


if __name__ == "__main__":
    # TEST Code
    from typing import Any

    import docopt

    import my_lib.config
    import my_lib.logger

    assert __doc__ is not None
    args = docopt.docopt(__doc__)

    config_file = args["-c"]
    target_file = args["-t"]
    debug_mode = args["-D"]

    my_lib.logger.init("test", level=logging.DEBUG if debug_mode else logging.INFO)

    config: dict[str, Any] = my_lib.config.load(config_file)
    login_config = AmazonLoginConfig.from_dict(
        config["store"]["amazon"], pathlib.Path(config["data"]["dump"])
    )

    driver = my_lib.selenium_util.create_driver("Test", pathlib.Path(config["data"]["selenium"]))
    wait = selenium.webdriver.support.wait.WebDriverWait(driver, 5)

    slack_config_parsed = my_lib.notify.slack.parse_config(config["slack"]) if "slack" in config else None
    slack_config: my_lib.notify.slack.HasCaptchaConfig | None = (
        slack_config_parsed
        if isinstance(
            slack_config_parsed,
            (my_lib.notify.slack.SlackConfig, my_lib.notify.slack.SlackCaptchaOnlyConfig),
        )
        else None
    )

    try:
        execute(driver, wait, login_config, slack_config)
    except Exception:
        logging.exception("URL: %s", driver.current_url)

        my_lib.selenium_util.dump_page(
            driver,
            int(random.random() * 100),  # noqa: S311
            login_config.dump_path,
        )

    driver.quit()
