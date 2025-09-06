#!/usr/bin/env python3
"""
Amazon へのログインをを行います。

Usage:
  login.py [-c CONFIG] [-t TARGET] [-D]

Options:
  -c CONFIG         : CONFIG を設定ファイルとして読み込んで実行します。[default: config.yaml]
  -D                : デバッグモードで動作します。
"""

import logging
import pathlib
import random
import time

import selenium.webdriver.common.by
import selenium.webdriver.support
import selenium.webdriver.support.wait

import my_lib.selenium_util
import my_lib.store.amazon.captcha

LOGIN_URL = "https://www.amazon.co.jp/ap/signin?openid.pape.max_auth_age=0&openid.return_to=https%3A%2F%2Fwww.amazon.co.jp%2Fref%3Dnav_signin&openid.identity=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0%2Fidentifier_select&openid.assoc_handle=jpflex&openid.mode=checkid_setup&openid.claimed_id=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0%2Fidentifier_select&openid.ns=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0"

LOGIN_MARK_XPATH = '//span[contains(text(), "アカウント＆リスト")]'
WAIT_COUNT = 40


def resolve_puzzle(driver, wait, config):
    logging.info("Try to resolve PUZZLE")

    my_lib.store.amazon.captcha.resolve(
        driver,
        wait,
        config,
        {"image": '//img[@alt="captcha"]', "text": '//input[@name="cvf_captcha_input"]'},
    )

    driver.find_element(
        selenium.webdriver.common.by.By.XPATH, '//input[@name="cvf_captcha_captcha_action"]'
    ).click()

    wait.until(selenium.webdriver.support.expected_conditions.presence_of_all_elements_located)
    time.sleep(0.1)


def handle_email_input(driver, config):
    """メールアドレス入力処理"""
    email_xpath = '//input[@type="email" and (@id="ap_email_login" or @id="ap_email")]'
    if my_lib.selenium_util.xpath_exists(driver, email_xpath):
        logging.debug("Input email")
        email_input = driver.find_element(selenium.webdriver.common.by.By.XPATH, email_xpath)
        email_input.clear()
        email_input.send_keys(config["store"]["amazon"]["user"])

        logging.debug("Click continue")
        if my_lib.selenium_util.xpath_exists(driver, '//input[@type="submit"]'):
            driver.find_element(selenium.webdriver.common.by.By.XPATH, '//input[@type="submit"]').click()
            time.sleep(3)


def handle_password_input(driver, wait, config):
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
        config["store"]["amazon"]["pass"],
    )

    if my_lib.selenium_util.xpath_exists(driver, '//input[@name="rememberMe"]'):
        remember_checkbox = driver.find_element(
            selenium.webdriver.common.by.By.XPATH, '//input[@name="rememberMe"]'
        )
        if not remember_checkbox.get_attribute("checked"):
            logging.debug("Check remember")
            remember_checkbox.click()

    if my_lib.selenium_util.xpath_exists(driver, '//input[@id="auth-captcha-guess"]'):
        my_lib.store.amazon.captcha.resolve(
            driver,
            wait,
            config,
            {
                "image": '//img[@id="auth-captcha-image"]',
                "text": '//input[@id="auth-captcha-guess"]',
            },
        )

    time.sleep(0.1)

    logging.debug("Click submit")
    submit_button = driver.find_element(selenium.webdriver.common.by.By.XPATH, '//input[@id="signInSubmit"]')
    driver.execute_script("arguments[0].click();", submit_button)

    wait.until(selenium.webdriver.support.expected_conditions.presence_of_all_elements_located)
    time.sleep(3)


def handle_security_check(driver):
    """セキュリティチェック画面の処理"""
    time.sleep(2)

    security_xpath = (
        '//span[contains(@class, "a-size-base-plus") and '
        '(contains(., "確認コードを入力する") or contains(., "セキュリティ"))]'
    )
    if not my_lib.selenium_util.xpath_exists(driver, security_xpath):
        return

    for i in range(WAIT_COUNT):
        security_check_xpath = '//span[contains(@class, "a-size-base-plus") and contains(., "セキュリティ")]'
        if not my_lib.selenium_util.xpath_exists(driver, security_check_xpath):
            my_lib.selenium_util.dump_page(
                driver,
                int(random.random() * 100),  # noqa: S311
                pathlib.Path(config["data"]["dump"]),
            )
            logging.info("Security check finished!")
            break

        logging.info("Waiting for security check... (%d/%d)", i + 1, WAIT_COUNT)
        time.sleep(2)

    for i in range(WAIT_COUNT):
        wait_xpath = '//span[contains(@class, "a-size-base") and contains(., "少しお待ちください")]'
        if not my_lib.selenium_util.xpath_exists(driver, wait_xpath):
            my_lib.selenium_util.dump_page(
                driver,
                int(random.random() * 100),  # noqa: S311
                pathlib.Path(config["data"]["dump"]),
            )
            logging.info("Acknowledged!")
            break

        logging.info("Waiting for acknowledge... (%d/%d)", i + 1, WAIT_COUNT)
        time.sleep(2)


def execute_impl(driver, wait, config, login_mark_xpath):
    wait.until(selenium.webdriver.support.expected_conditions.presence_of_all_elements_located)
    time.sleep(0.1)

    if my_lib.selenium_util.xpath_exists(driver, login_mark_xpath):
        logging.info("Login succeeded")
        return

    if my_lib.selenium_util.xpath_exists(driver, '//input[@name="cvf_captcha_input"]'):
        resolve_puzzle(driver, wait, config)

    handle_email_input(driver, config)
    handle_password_input(driver, wait, config)
    handle_security_check(driver)

    wait.until(selenium.webdriver.support.expected_conditions.presence_of_all_elements_located)
    time.sleep(0.1)


def execute(driver, wait, config, login_url=LOGIN_URL, login_mark_xpath=LOGIN_MARK_XPATH, retry=2):  # noqa: PLR0913
    logging.info("Login start")

    driver.get(login_url)

    for i in range(retry):
        execute_impl(driver, wait, config, login_mark_xpath)

        if my_lib.selenium_util.xpath_exists(driver, login_mark_xpath):
            logging.info("Login sccessful!")
            return True

        if i != (retry - 1):
            logging.warning("Login retry")

            my_lib.selenium_util.dump_page(
                driver,
                int(random.random() * 100),  # noqa: S311
                pathlib.Path(config["data"]["dump"]),
            )

    logging.error("Login fail")

    return False


if __name__ == "__main__":
    # TEST Code
    import docopt

    import my_lib.config
    import my_lib.logger

    args = docopt.docopt(__doc__)

    config_file = args["-c"]
    target_file = args["-t"]
    debug_mode = args["-D"]

    my_lib.logger.init("test", level=logging.DEBUG if debug_mode else logging.INFO)

    config = my_lib.config.load(config_file)

    driver = my_lib.selenium_util.create_driver("Test", pathlib.Path(config["data"]["selenium"]))
    wait = selenium.webdriver.support.wait.WebDriverWait(driver, 5)

    try:
        execute(driver, wait, config)
    except Exception:
        logging.exception("URL: %s", driver.current_url)

        my_lib.selenium_util.dump_page(
            driver,
            int(random.random() * 100),  # noqa: S311
            pathlib.Path(config["data"]["dump"]),
        )

    driver.quit()
