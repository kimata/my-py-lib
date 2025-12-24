#!/usr/bin/env python3
"""
スクレイピングで Amazon の価格情報を取得するライブラリです。

Usage:
  scrape.py [-c CONFIG] [-t ASIN] [-s DATA_PATH] [-D]

Options:
  -c CONFIG         : CONFIG を設定ファイルとして読み込んで実行します。[default: config.yaml]
  -t ASIN           : 価格情報を取得する ASIN。[default: B01MUZOWBH]
  -s DATA_PATH      : Selenium で使うブラウザのデータを格納するディレクトリ。[default: data]
  -D                : デバッグモードで動作します。
"""

from __future__ import annotations

import io
import logging
import pathlib
import random
import re
import time
import traceback
from typing import Any

import PIL.Image
import selenium.webdriver.common.by
import selenium.webdriver.remote.webdriver
import selenium.webdriver.support
import selenium.webdriver.support.wait

import my_lib.notify.slack
import my_lib.selenium_util
import my_lib.store.amazon.captcha


def fetch_price_impl(
    driver: selenium.webdriver.remote.webdriver.WebDriver,
    wait: selenium.webdriver.support.wait.WebDriverWait,
    slack_config: my_lib.notify.slack.SlackErrorProtocol | None,
    item: dict[str, Any],
) -> dict[str, Any]:  # noqa: C901, PLR0912
    PRICE_ELEM_LIST: list[dict[str, str]] = [
        {
            "xpath": '//span[contains(@class, "apexPriceToPay")]/span[@aria-hidden]',
            "type": "html",
        },
        {
            "xpath": '//span[contains(@class, "priceToPay")]/span[@aria-hidden]',
            "type": "text",
        },
        {
            "xpath": '//span[contains(@class, "priceBlockBuyingPriceString")]',
            "type": "text",
        },
    ]

    if (
        len(
            driver.find_elements(
                selenium.webdriver.common.by.By.XPATH, '//b[@class="h1" and contains(text(), "ご迷惑")]'
            )
        )
        != 0
    ):
        logging.warning("Failed to load page: %s", item["url"])
        time.sleep(5)
        return {}

    my_lib.selenium_util.click_xpath(driver, '//span[@id="black-curtain-yes-button"]', is_warn=False)
    my_lib.selenium_util.click_xpath(
        driver,
        '//span[contains(@class, "a-button")]//button[normalize-space(text()) = "ショッピングを続ける"]',
        is_warn=False,
    )

    # my_lib.store.amazon.captcha.resolve(driver, wait, config)

    category: str | None = None
    try:
        breadcrumb_list = driver.find_elements(
            selenium.webdriver.common.by.By.XPATH, "//div[contains(@class, 'a-breadcrumb')]//li//a"
        )
        category = next(x.text for x in breadcrumb_list)

    except Exception:
        logging.exception("Failed to fetch category")

    price_text = ""
    for price_elem in PRICE_ELEM_LIST:
        if len(driver.find_elements(selenium.webdriver.common.by.By.XPATH, price_elem["xpath"])) == 0:
            continue

        logging.debug('xpath: "%s', price_elem["xpath"])

        if price_elem["type"] == "html":
            inner_html = driver.find_element(
                selenium.webdriver.common.by.By.XPATH, price_elem["xpath"]
            ).get_attribute("innerHTML")
            if inner_html is not None:
                price_text = inner_html.strip()
        else:
            price_text = driver.find_element(selenium.webdriver.common.by.By.XPATH, price_elem["xpath"]).text
        break

    if price_text == "":
        if (
            len(
                driver.find_elements(
                    selenium.webdriver.common.by.By.XPATH, '//span[contains(@class, "a-color-price")]'
                )
            )
            != 0
        ):
            price_text = driver.find_element(
                selenium.webdriver.common.by.By.XPATH, '//span[contains(@class, "a-color-price")]'
            ).text
            if price_text in {"現在在庫切れです。", "この商品は現在お取り扱いできません。"}:
                logging.warning("Price is NOT displayed: %s", item["url"])
                return {"price": 0, "category": category}
        elif (
            len(
                driver.find_elements(
                    selenium.webdriver.common.by.By.XPATH,
                    (
                        '//div[contains(@class, "a-box-inner") and contains(@class, "a-padding-medium")]'
                        '/span[contains(text(), "ありません")]'
                    ),
                )
            )
            != 0
        ):
            return {"price": 0, "category": category}
        else:
            logging.warning("Unable to fetch price: %s", item["url"])

            if slack_config is not None:
                my_lib.notify.slack.error_with_image(
                    slack_config,
                    "価格取得に失敗",
                    "{url}\nprice_text='{price_text}'".format(url=item["url"], price_text=price_text),
                    {
                        "data": PIL.Image.open(io.BytesIO(driver.get_screenshot_as_png())),
                        "text": "スクリーンショット",
                    },
                )
            return {"price": 0, "category": category}

    try:
        m = re.match(r".*?(\d{1,3}(?:,\d{3})*)", re.sub(r"[^0-9][0-9]+個", "", price_text))
        if m is None:
            raise ValueError(f"Failed to parse price: {price_text}")
        price = int(m.group(1).replace(",", ""))
    except Exception:
        logging.warning('Unable to parse "%s": %s.', price_text, item["url"])

        if slack_config is not None:
            my_lib.notify.slack.error_with_image(
                slack_config,
                "価格取得に失敗",
                "{url}\n{traceback}".format(url=item["url"], traceback=traceback.format_exc()),
                {
                    "data": PIL.Image.open(io.BytesIO(driver.get_screenshot_as_png())),
                    "text": "スクリーンショット",
                },
            )
        return {"price": 0, "category": category}

    return {"price": price, "category": category}


def fetch_price(
    driver: selenium.webdriver.remote.webdriver.WebDriver,
    wait: selenium.webdriver.support.wait.WebDriverWait,
    config: dict[str, Any],
    item: dict[str, Any],
) -> dict[str, Any]:
    try:
        with my_lib.selenium_util.browser_tab(driver, item["url"]):
            wait.until(
                selenium.webdriver.support.expected_conditions.presence_of_element_located(
                    (
                        selenium.webdriver.common.by.By.XPATH,
                        '//div[contains(@class, "footer") or contains(@class, "Footer")]',
                    )
                )
            )

            slack_config_parsed = (
                my_lib.notify.slack.parse_config(config["slack"]) if "slack" in config else None
            )
            slack_config: my_lib.notify.slack.SlackErrorProtocol | None = (
                slack_config_parsed
                if isinstance(
                    slack_config_parsed,
                    (
                        my_lib.notify.slack.SlackConfig,
                        my_lib.notify.slack.SlackErrorInfoConfig,
                        my_lib.notify.slack.SlackErrorOnlyConfig,
                    ),
                )
                else None
            )
            item |= fetch_price_impl(driver, wait, slack_config, item)

            if (item["price"] is None) or (item["price"] == 0):
                my_lib.selenium_util.dump_page(
                    driver,
                    int(random.random() * 100),  # noqa: S311
                    pathlib.Path(config["data"]["dump"]),
                )
    except Exception:
        logging.exception("Failed to fetch price")

    return item


if __name__ == "__main__":
    # TEST Code
    import pathlib

    import docopt
    import selenium.webdriver.support.wait

    import my_lib.config
    import my_lib.logger
    import my_lib.pretty
    import my_lib.selenium_util

    args = docopt.docopt(__doc__)

    config_file = args["-c"]
    data_path = args["-s"]
    asin = args["-t"]
    debug_mode = args["-D"]

    my_lib.logger.init("test", level=logging.DEBUG if debug_mode else logging.INFO)

    config = my_lib.config.load(config_file)

    driver = my_lib.selenium_util.create_driver("Test", pathlib.Path(data_path))
    wait = selenium.webdriver.support.wait.WebDriverWait(driver, 2)

    logging.info(
        my_lib.pretty.format(
            fetch_price(driver, wait, config, {"url": f"https://www.amazon.co.jp/dp/{asin}"})
        )
    )
