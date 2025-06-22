#!/usr/bin/env python3
import contextlib
import logging
import re
import time

import my_lib.notify.slack
import my_lib.selenium_util
import my_lib.store.captcha
import selenium.common.exceptions
import selenium.webdriver.common.by
import selenium.webdriver.support
import selenium.webdriver.support.ui

TRY_COUNT = 3
ITEM_LIST_XPATH = '//ul[@data-testid="listed-item-list"]//li'


def parse_item(driver, index):
    time.sleep(5)
    item_xpath = f"{ITEM_LIST_XPATH}[{index}]"

    # 親要素を最初に取得
    by_xpath = selenium.webdriver.common.by.By.XPATH
    item_element = driver.find_element(by_xpath, item_xpath)

    # 子要素用の相対XPath
    relative_xpaths = {
        "url": ".//a",
        "name": ".//p[@data-testid='item-label']",
        "price": ".//p[@data-testid='item-label']/following-sibling::span/span[2]",
        "favorite": ".//p[@data-testid='item-label']/following-sibling::div/div[1]/span",
        "view": ".//p[@data-testid='item-label']/following-sibling::div/div[3]/span",
        "private": ".//span[contains(text(), '公開停止中')]",
    }

    # 必須要素の取得
    item_url = item_element.find_element(by_xpath, relative_xpaths["url"]).get_attribute("href")
    item_id = item_url.split("/")[-1]
    name = item_element.find_element(by_xpath, relative_xpaths["name"]).text

    # 価格要素の存在確認
    if not item_element.find_elements(by_xpath, relative_xpaths["price"]):
        driver.refresh()
        time.sleep(5)
        return parse_item(driver, index)

    price = int(item_element.find_element(by_xpath, relative_xpaths["price"]).text.replace(",", ""))

    # 公開停止フラグ
    is_stop = 1 if item_element.find_elements(by_xpath, relative_xpaths["private"]) else 0

    # オプション要素の取得（エラーハンドリング付き）
    view = 0
    favorite = 0

    view_elements = item_element.find_elements(by_xpath, relative_xpaths["view"])
    if view_elements:
        with contextlib.suppress(ValueError, AttributeError):
            view = int(view_elements[0].text)

    favorite_elements = item_element.find_elements(by_xpath, relative_xpaths["favorite"])
    if favorite_elements:
        with contextlib.suppress(ValueError, AttributeError):
            favorite = int(favorite_elements[0].text)

    return {
        "id": item_id,
        "url": item_url,
        "name": name,
        "price": price,
        "view": view,
        "favorite": favorite,
        "is_stop": is_stop,
    }


def execute_item(driver, wait, scrape_config, debug_mode, index, item_func_list):  # noqa: PLR0913
    item = parse_item(driver, index)

    logging.info(
        "%s [%s] [%s円] [%s view] [%s favorite] を処理します。",
        item["name"],
        item["id"],
        f"{item['price']:,}",
        f"{item['view']:,}",
        f"{item['favorite']:,}",
    )

    driver.execute_script("window.scrollTo(0, 0);")
    item_link = driver.find_element(
        selenium.webdriver.common.by.By.XPATH,
        ITEM_LIST_XPATH + "[" + str(index) + "]//a",
    )
    # NOTE: アイテムにスクロールしてから、ヘッダーに隠れないようちょっと前に戻す
    item_link.location_once_scrolled_into_view  # noqa: B018
    driver.execute_script("window.scrollTo(0, window.pageYOffset - 200);")
    item_link.click()

    try:
        wait.until(
            selenium.webdriver.support.expected_conditions.title_contains(re.sub(" +", " ", item["name"]))
        )
    except selenium.common.exceptions.TimeoutException:
        logging.exception("Invalid title: %s", driver.title)
        raise

    item_url = driver.current_url

    fail_count = 0
    for item_func in item_func_list:
        while True:
            try:
                item_func(driver, wait, scrape_config, item, debug_mode)
                fail_count = 0
                break
            except (
                selenium.common.exceptions.TimeoutException,
                selenium.common.exceptions.ElementNotInteractableException,
            ):
                logging.exception("エラーが発生しました")
                fail_count += 1

                if fail_count >= TRY_COUNT:
                    logging.warning("エラーが %d 回続いたので諦めます。")
                    raise

                if driver.current_url != item_url:
                    driver.back()
                    time.sleep(1)
                if driver.current_url != item_url:
                    driver.get(item_url)

                my_lib.selenium_util.random_sleep(10)

        time.sleep(10)


def expand_all(driver, wait):
    MORE_BUTTON_XPATH = '//div[contains(@class, "merButton")]/button[contains(text(), "もっと見る")]'

    while len(driver.find_elements(selenium.webdriver.common.by.By.XPATH, MORE_BUTTON_XPATH)) != 0:
        my_lib.selenium_util.click_xpath(driver, MORE_BUTTON_XPATH, wait)

        wait.until(selenium.webdriver.support.expected_conditions.presence_of_all_elements_located)
        time.sleep(2)


def iter_items_on_display(driver, wait, scrape_config, debug_mode, item_func_list):
    my_lib.selenium_util.click_xpath(
        driver,
        '//button[@data-testid="account-button"]',
        wait,
    )
    my_lib.selenium_util.click_xpath(driver, '//a[contains(text(), "出品した商品")]', wait)

    wait.until(
        selenium.webdriver.support.expected_conditions.presence_of_element_located(
            (
                selenium.webdriver.common.by.By.XPATH,
                ITEM_LIST_XPATH,
            )
        )
    )

    time.sleep(1)

    expand_all(driver, wait)

    item_count = len(
        driver.find_elements(
            selenium.webdriver.common.by.By.XPATH,
            ITEM_LIST_XPATH,
        )
    )

    logging.info("%d 個の出品があります。", item_count)

    list_url = driver.current_url
    for i in range(1, item_count + 1):
        execute_item(driver, wait, scrape_config, debug_mode, i, item_func_list)

        if debug_mode:
            break

        my_lib.selenium_util.random_sleep(10)
        driver.get(list_url)
        wait.until(
            selenium.webdriver.support.expected_conditions.presence_of_element_located(
                (selenium.webdriver.common.by.By.XPATH, ITEM_LIST_XPATH)
            )
        )

        expand_all(driver, wait)
