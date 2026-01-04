#!/usr/bin/env python3
"""
ショップをスクレイピングで解析して価格情報を取得するライブラリです。

Usage:
  scrape.py [-c CONFIG] [-s DATA_PATH] [-D]

Options:
  -c CONFIG         : CONFIG を設定ファイルとして読み込んで実行します。
                      [default: tests/fixtures/config.example.yaml]
  -s DATA_PATH      : Selenium で使うブラウザのデータを格納するディレクトリ。[default: data]
  -D                : デバッグモードで動作します。
"""

from __future__ import annotations

import logging
import pathlib
import random
import re
import string
import time
import urllib.parse
from dataclasses import dataclass
from typing import Any, Literal

import selenium.webdriver.common.by
import selenium.webdriver.remote.webdriver
import selenium.webdriver.support
import selenium.webdriver.support.expected_conditions
import selenium.webdriver.support.wait

import my_lib.selenium_util
import my_lib.store.captcha

_TIMEOUT_SEC: int = 4


# === Action 型定義 ===
@dataclass(frozen=True)
class InputAction:
    """入力アクション"""

    type: Literal["input"]
    xpath: str
    value: str


@dataclass(frozen=True)
class ClickAction:
    """クリックアクション"""

    type: Literal["click"]
    xpath: str


@dataclass(frozen=True)
class RecaptchaAction:
    """reCAPTCHA 解決アクション"""

    type: Literal["recaptcha"]


@dataclass(frozen=True)
class CaptchaAction:
    """CAPTCHA 解決アクション"""

    type: Literal["captcha"]


@dataclass(frozen=True)
class SixDigitAction:
    """6桁コード入力アクション"""

    type: Literal["sixdigit"]


Action = InputAction | ClickAction | RecaptchaAction | CaptchaAction | SixDigitAction


def parse_action(data: dict[str, Any]) -> Action:
    """辞書形式のアクション定義を Action 型に変換する"""
    action_type = data.get("type")

    if action_type == "input":
        return InputAction(
            type="input",
            xpath=data["xpath"],
            value=data["value"],
        )
    elif action_type == "click":
        return ClickAction(
            type="click",
            xpath=data["xpath"],
        )
    elif action_type == "recaptcha":
        return RecaptchaAction(type="recaptcha")
    elif action_type == "captcha":
        return CaptchaAction(type="captcha")
    elif action_type == "sixdigit":
        return SixDigitAction(type="sixdigit")
    else:
        raise ValueError(f"Unknown action type: {action_type}")


def parse_action_list(data_list: list[dict[str, Any]]) -> list[Action]:
    """辞書形式のアクションリストを Action 型のリストに変換する"""
    return [parse_action(data) for data in data_list]


def _resolve_template(template: str, item: dict[str, Any]) -> str:
    tmpl = string.Template(template)
    return tmpl.safe_substitute(item_name=item["name"])


def process_action(
    driver: selenium.webdriver.remote.webdriver.WebDriver,
    wait: selenium.webdriver.support.wait.WebDriverWait,
    item: dict[str, Any],
    action_list: list[Action],
    name: str = "action",
    *,
    dump_path: pathlib.Path,
) -> None:
    logging.info("Process action: %s", name)

    for action in action_list:
        logging.debug("action: %s.", action.type)
        if isinstance(action, InputAction):
            xpath = _resolve_template(action.xpath, item)
            if not my_lib.selenium_util.xpath_exists(driver, xpath):
                logging.debug("Element not found. Interrupted.")
                return
            value = _resolve_template(action.value, item)
            driver.find_element(selenium.webdriver.common.by.By.XPATH, xpath).send_keys(value)
        elif isinstance(action, ClickAction):
            xpath = _resolve_template(action.xpath, item)
            if not my_lib.selenium_util.xpath_exists(driver, xpath):
                logging.debug("Element not found. Interrupted.")
                return
            driver.find_element(selenium.webdriver.common.by.By.XPATH, xpath).click()
        elif isinstance(action, RecaptchaAction):
            my_lib.store.captcha.resolve_recaptcha_auto(driver, wait)
        elif isinstance(action, CaptchaAction):
            input_xpath = '//input[@id="captchacharacters"]'
            if not my_lib.selenium_util.xpath_exists(driver, input_xpath):
                logging.debug("Element not found.")
                continue
            domain = urllib.parse.urlparse(driver.current_url).netloc

            logging.warning("Resolve captche is needed at %s.", domain)

            my_lib.selenium_util.dump_page(driver, int(random.random() * 100), dump_path)  # noqa: S311
            code = input(f"{domain} captcha: ")

            driver.find_element(selenium.webdriver.common.by.By.XPATH, input_xpath).send_keys(code)
            driver.find_element(selenium.webdriver.common.by.By.XPATH, '//button[@type="submit"]').click()
        elif isinstance(action, SixDigitAction):
            # NOTE: これは今のところ Ubiquiti Store USA 専用
            digit_code = input(f"{urllib.parse.urlparse(driver.current_url).netloc} app code: ")
            for i, code in enumerate(list(digit_code)):
                driver.find_element(
                    selenium.webdriver.common.by.By.XPATH, '//input[@data-id="' + str(i) + '"]'
                ).send_keys(code)

        time.sleep(4)


def _process_preload(
    driver: selenium.webdriver.remote.webdriver.WebDriver,
    wait: selenium.webdriver.support.wait.WebDriverWait,
    item: dict[str, Any],
    loop: int,
    *,
    dump_path: pathlib.Path,
) -> None:
    logging.info("Process preload: %s", item["name"])

    if "preload" not in item:
        return

    if (loop % item["preload"]["every"]) != 0:
        logging.info("Skip preload. (loop=%d)", loop)
        return

    driver.get(item["preload"]["url"])
    time.sleep(2)

    actions = parse_action_list(item["preload"]["action"])
    process_action(driver, wait, item, actions, "preload action", dump_path=dump_path)


def _fetch_price_impl(
    driver: selenium.webdriver.remote.webdriver.WebDriver,
    item: dict[str, Any],
    loop: int,
    *,
    dump_path: pathlib.Path,
) -> dict[str, Any] | bool:
    wait = selenium.webdriver.support.wait.WebDriverWait(driver, _TIMEOUT_SEC)

    _process_preload(driver, wait, item, loop, dump_path=dump_path)

    logging.info("Fetch: %s", item["url"])

    driver.get(item["url"])
    wait.until(
        selenium.webdriver.support.expected_conditions.presence_of_element_located(
            (selenium.webdriver.common.by.By.XPATH, "//body")
        )
    )
    time.sleep(2)

    if "action" in item:
        process_action(driver, wait, item, parse_action_list(item["action"]), dump_path=dump_path)

    logging.info("Parse: %s", item["name"])

    if not my_lib.selenium_util.xpath_exists(driver, item["price_xpath"]):
        logging.warning("%s: price not found.", item["name"])
        item["stock"] = 0
        my_lib.selenium_util.dump_page(driver, int(random.random() * 100), dump_path)  # noqa: S311

        return False

    if "unavailable_xpath" in item:
        if len(driver.find_elements(selenium.webdriver.common.by.By.XPATH, item["unavailable_xpath"])) != 0:
            item["stock"] = 0
        else:
            item["stock"] = 1
    else:
        item["stock"] = 1

    price_text = driver.find_element(selenium.webdriver.common.by.By.XPATH, item["price_xpath"]).text
    try:
        m = re.match(r".*?(\d{1,3}(?:,\d{3})*)", price_text)
        if m is None:
            raise ValueError(f"Failed to parse price: {price_text}")
        item["price"] = int(m.group(1).replace(",", ""))
        logging.info("%s%s", f"""{item["price"]:,}""", item["price_unit"])
    except Exception:
        if item["stock"] == 0:
            # NOTE: 在庫がない場合は、価格が取得できなくてもエラーにしない
            pass
        else:
            logging.debug('Unable to parse price: "%s"', price_text)
            raise

    if "thumb_url" not in item:
        if ("thumb_img_xpath" in item) and my_lib.selenium_util.xpath_exists(driver, item["thumb_img_xpath"]):
            item["thumb_url"] = urllib.parse.urljoin(
                driver.current_url,
                driver.find_element(
                    selenium.webdriver.common.by.By.XPATH, item["thumb_img_xpath"]
                ).get_attribute("src"),
            )
    elif ("thumb_block_xpath" in item) and my_lib.selenium_util.xpath_exists(
        driver, item["thumb_block_xpath"]
    ):
        style_text = driver.find_element(
            selenium.webdriver.common.by.By.XPATH, item["thumb_block_xpath"]
        ).get_attribute("style")
        if style_text is not None:
            m = re.match(
                r"background-image: url\([\"'](.*)[\"']\)",
                style_text,
            )
            if m is not None:
                thumb_url = m.group(1)
                if not re.compile(r"^\.\.").search(thumb_url):
                    thumb_url = "/" + thumb_url

                item["thumb_url"] = urllib.parse.urljoin(driver.current_url, thumb_url)

    return item


def fetch_price(
    driver: selenium.webdriver.remote.webdriver.WebDriver,
    item: dict[str, Any],
    loop: int = 0,
    *,
    dump_path: pathlib.Path,
) -> dict[str, Any] | bool:
    try:
        logging.info("Check %s", item["name"])

        return _fetch_price_impl(driver, item, loop, dump_path=dump_path)
    except Exception:
        logging.exception("Failed to check %s", driver.current_url)
        my_lib.selenium_util.dump_page(driver, int(random.random() * 100), dump_path)  # noqa: S311
        my_lib.selenium_util.clean_dump(dump_path)
        raise


if __name__ == "__main__":
    # TEST Code
    import docopt

    import my_lib.config
    import my_lib.logger

    assert __doc__ is not None  # noqa: S101
    args = docopt.docopt(__doc__)

    config_file = args["-c"]
    data_path = args["-s"]
    debug_mode = args["-D"]

    my_lib.logger.init("test", level=logging.DEBUG if debug_mode else logging.INFO)

    config = my_lib.config.load(config_file)

    driver = my_lib.selenium_util.create_driver("Test", pathlib.Path(data_path))

    item = {
        "name": "Raspberry Pi 5 / 8GB (switch-science)",
        "url": "https://www.switch-science.com/products/9250",
        "price_xpath": '//div[contains(@class, "price__current")]/span[contains(@class, "money")]',
        "thumb_img_xpath": '//div[@class="product-gallery--image-background"]/img',
        "unavailable_xpath": '//button[contains(@id, "BIS_trigger") and contains(text(), "入荷通知登録")]',
    }

    logging.info(fetch_price(driver, item, dump_path=pathlib.Path(data_path)))
