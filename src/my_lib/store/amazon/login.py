#!/usr/bin/env python3
"""
Amazon へのログインをを行います．

Usage:
  login.py [-c CONFIG] [-t TARGET] [-d]

Options:
  -c CONFIG         : CONFIG を設定ファイルとして読み込んで実行します．[default: config.yaml]
  -d                : デバッグモードで動作します．
"""

import logging
import pathlib
import random
import time

import my_lib.store.amazon.captcha
import selenium.webdriver.common.by
import selenium.webdriver.support
import selenium.webdriver.support.wait

LOGIN_URL = "https://www.amazon.co.jp/ap/signin?openid.pape.max_auth_age=0&openid.return_to=https%3A%2F%2Fwww.amazon.co.jp%2Fref%3Dnav_signin&openid.identity=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0%2Fidentifier_select&openid.assoc_handle=jpflex&openid.mode=checkid_setup&openid.claimed_id=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0%2Fidentifier_select&openid.ns=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0"

LOGIN_MARK_XPATH = '//span[contains(text(), "アカウント＆リスト")]'


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


def execute_impl(driver, wait, config, login_mark_xpath):
    wait.until(selenium.webdriver.support.expected_conditions.presence_of_all_elements_located)
    time.sleep(0.1)

    if len(driver.find_elements(selenium.webdriver.common.by.By.XPATH, login_mark_xpath)) != 0:
        logging.info("Login succeeded")
        return

    if (
        len(driver.find_elements(selenium.webdriver.common.by.By.XPATH, '//input[@name="cvf_captcha_input"]'))
        != 0
    ):
        resolve_puzzle(driver, wait, config)

    if (
        len(
            driver.find_elements(
                selenium.webdriver.common.by.By.XPATH, '//input[@type="email" and @id="ap_email"]'
            )
        )
        != 0
    ):
        logging.debug("Input email")
        driver.find_element(
            selenium.webdriver.common.by.By.XPATH, '//input[@type="email" and @id="ap_email"]'
        ).clear()
        driver.find_element(
            selenium.webdriver.common.by.By.XPATH, '//input[@type="email" and @id="ap_email"]'
        ).send_keys(config["store"]["amazon"]["user"])

        logging.debug("Click continue")
        if len(driver.find_elements(selenium.webdriver.common.by.By.XPATH, '//input[@id="continue"]')) != 0:
            driver.find_element(selenium.webdriver.common.by.By.XPATH, '//input[@id="continue"]').click()
            time.sleep(2)

    logging.debug("Input password")
    wait.until(
        selenium.webdriver.support.expected_conditions.element_to_be_clickable(
            (selenium.webdriver.common.by.By.XPATH, '//input[@id="ap_password"]')
        )
    )

    driver.find_element(selenium.webdriver.common.by.By.XPATH, '//input[@id="ap_password"]').send_keys(
        config["store"]["amazon"]["pass"]
    )

    if len(driver.find_elements(selenium.webdriver.common.by.By.XPATH, '//input[@name="rememberMe"]')) != 0:
        if not driver.find_element(
            selenium.webdriver.common.by.By.XPATH, '//input[@name="rememberMe"]'
        ).get_attribute("checked"):
            logging.debug("Check remember")
            driver.find_element(selenium.webdriver.common.by.By.XPATH, '//input[@name="rememberMe"]').click()

    if (
        len(driver.find_elements(selenium.webdriver.common.by.By.XPATH, '//input[@id="auth-captcha-guess"]'))
        != 0
    ):
        my_lib.store.amazon.captcha.resolve(
            driver,
            wait,
            config,
            {"image": '//img[@id="auth-captcha-image"]', "text": '//input[@id="auth-captcha-guess"]'},
        )

    driver.find_element(selenium.webdriver.common.by.By.XPATH, '//input[@id="signInSubmit"]').click()

    wait.until(selenium.webdriver.support.expected_conditions.presence_of_all_elements_located)
    time.sleep(0.1)

    if logging.getLogger().getEffectiveLevel() == logging.DEBUG:
        my_lib.selenium_util.dump_page(
            driver,
            int(random.random() * 100),
            pathlib.Path(config["data"]["dump"]),
        )


def execute(driver, wait, config, login_url=LOGIN_URL, login_mark_xpath=LOGIN_MARK_XPATH, retry=2):
    logging.info("Login start")

    driver.get(login_url)

    for i in range(retry):
        execute_impl(driver, wait, config, login_mark_xpath)

        if len(driver.find_elements(selenium.webdriver.common.by.By.XPATH, login_mark_xpath)) != 0:
            logging.info("Login sccessful!")
            return True

        if i != (retry - 1):
            logging.warning("Login retry")

            my_lib.selenium_util.dump_page(
                driver,
                int(random.random() * 100),
                pathlib.Path(config["data"]["dump"]),
            )

    logging.error("Login fail")

    return False


if __name__ == "__main__":
    import docopt
    import my_lib.config
    import my_lib.logger

    args = docopt.docopt(__doc__)

    config_file = args["-c"]
    target_file = args["-t"]
    debug_mode = args["-d"]

    my_lib.logger.init("test", level=logging.DEBUG if debug_mode else logging.INFO)

    config = my_lib.config.load(config_file)

    driver = my_lib.selenium_util.create_driver("Test", pathlib.Path(config["data"]["selenium"]))
    wait = selenium.webdriver.support.wait.WebDriverWait(driver, 5)

    try:
        execute(driver, wait, config)
    except Exception:
        logging.error("URL: %s", driver.current_url)

        my_lib.selenium_util.dump_page(
            driver,
            int(random.random() * 100),
            pathlib.Path(config["data"]["dump"]),
        )

    driver.quit()
