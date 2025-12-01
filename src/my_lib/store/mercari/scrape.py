#!/usr/bin/env python3
import contextlib
import logging
import re
import time

import selenium.common.exceptions
import selenium.webdriver.common.by
import selenium.webdriver.support
import selenium.webdriver.support.ui

import my_lib.notify.slack
import my_lib.selenium_util
import my_lib.store.captcha

TRY_COUNT = 3
ITEM_LIST_XPATH = '//ul[@data-testid="listed-item-list"]//li'
POPUP_CLOSE_XPATHS = [
    # NOTE: 右上のポップアップの閉じるボタン（オークション案内など）
    '//div[contains(@class, "merIconButton")][@aria-label="close"]/button',
    # NOTE: モーダルダイアログのキャンセルボタン（アンバサダーツールバー非表示確認など）
    '//button[contains(text(), "キャンセル")]',
]


def close_popup(driver):
    by_xpath = selenium.webdriver.common.by.By.XPATH
    for xpath in POPUP_CLOSE_XPATHS:
        for button in driver.find_elements(by_xpath, xpath):
            with contextlib.suppress(Exception):
                if button.is_displayed():
                    button.click()
                    time.sleep(0.5)


def parse_item(driver, index):
    time.sleep(5)
    item_xpath = f"{ITEM_LIST_XPATH}[{index}]"

    # 親要素を最初に取得
    by_xpath = selenium.webdriver.common.by.By.XPATH
    item_element = driver.find_element(by_xpath, item_xpath)

    # 全ての子要素を一度に取得してキャッシュ
    elements_cache = {}

    try:
        # 必須要素を一括取得
        elements_cache["link"] = item_element.find_element(by_xpath, ".//a")
        elements_cache["name"] = item_element.find_element(by_xpath, ".//p[@data-testid='item-label']")

        # 価格要素を取得（存在しない場合はリトライ）
        price_elements = item_element.find_elements(
            by_xpath, ".//p[@data-testid='item-label']/following-sibling::span/span[2]"
        )
        if not price_elements:
            driver.refresh()
            time.sleep(5)
            return parse_item(driver, index)
        elements_cache["price"] = price_elements[0]

        # オプション要素を一括取得
        elements_cache["favorite"] = item_element.find_elements(
            by_xpath, ".//p[@data-testid='item-label']/following-sibling::div/div[1]/span"
        )
        elements_cache["view"] = item_element.find_elements(
            by_xpath, ".//p[@data-testid='item-label']/following-sibling::div/div[3]/span"
        )
        elements_cache["private"] = item_element.find_elements(
            by_xpath, ".//span[contains(text(), '公開停止中')]"
        )

    except selenium.common.exceptions.NoSuchElementException:
        driver.refresh()
        time.sleep(5)
        return parse_item(driver, index)

    # キャッシュした要素から値を抽出
    item_url = elements_cache["link"].get_attribute("href")
    item_id = item_url.split("/")[-1]
    name = elements_cache["name"].text
    price = int(elements_cache["price"].text.replace(",", ""))

    # オプション値の取得（デフォルト値で初期化）
    view = 0
    favorite = 0

    if elements_cache["view"]:
        with contextlib.suppress(ValueError, AttributeError):
            view = int(elements_cache["view"][0].text)

    if elements_cache["favorite"]:
        with contextlib.suppress(ValueError, AttributeError):
            favorite = int(elements_cache["favorite"][0].text)

    is_stop = 1 if elements_cache["private"] else 0

    item = {
        "id": item_id,
        "url": item_url,
        "name": name,
        "price": price,
        "view": view,
        "favorite": favorite,
        "is_stop": is_stop,
    }

    return item, item_element, elements_cache["link"]


def auto_reload(driver, wait):
    wait.until(
        selenium.webdriver.support.expected_conditions.presence_of_all_elements_located(
            (selenium.webdriver.common.by.By.XPATH, "//body")
        )
    )

    if my_lib.selenium_util.xpath_exists(
        driver, '//div[contains(@class, "titleContainer")]/p[text()="エラーが発生しました"]'
    ):
        logging.warning("ページの表示でエラーが発生したのでリロードします。")
        driver.refresh()


def execute_item(driver, wait, scrape_config, debug_mode, item_count, index, item_func_list):  # noqa: PLR0913
    item, item_element, item_link = parse_item(driver, index)

    logging.info(
        "[%d/%d] %s [%s] [%s円] [%s view] [%s favorite] を処理します。",
        index,
        item_count,
        item["name"],
        item["id"],
        f"{item['price']:,}",
        f"{item['view']:,}",
        f"{item['favorite']:,}",
    )

    # NOTE: ポップアップがリンクを覆い隠す場合があるため、先に閉じる
    close_popup(driver)

    driver.execute_script("window.scrollTo(0, 0);")
    # NOTE: アイテムにスクロールしてから、ヘッダーに隠れないようちょっと前に戻す
    item_link.location_once_scrolled_into_view  # noqa: B018
    driver.execute_script("window.scrollTo(0, window.pageYOffset - 200);")
    item_link.click()

    auto_reload(driver, wait)

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
                    logging.warning("エラーが %d 回続いたので諦めます。", fail_count)
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

        wait.until(
            selenium.webdriver.support.expected_conditions.presence_of_all_elements_located(
                (selenium.webdriver.common.by.By.XPATH, "//body")
            )
        )
        time.sleep(2)


def load_url(driver, wait, url):
    for i in range(TRY_COUNT):
        driver.execute_script(f'window.location.href = "{url}";')
        try:
            wait.until(
                selenium.webdriver.support.expected_conditions.presence_of_element_located(
                    (selenium.webdriver.common.by.By.XPATH, ITEM_LIST_XPATH)
                )
            )
        except selenium.common.exceptions.TimeoutException:
            logging.exception("Failed to load %s", url)

            if i == TRY_COUNT - 1:
                logging.warning("エラーが %d 回続いたので諦めます。", i + 1)
                raise

        expand_all(driver, wait)
        return


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
        for retry in range(TRY_COUNT):
            try:
                execute_item(driver, wait, scrape_config, debug_mode, item_count, i, item_func_list)
                break
            except Exception:
                logging.exception("エラーが発生しました。リトライします。(retry=%d)", retry + 1)
                if retry == TRY_COUNT - 1:
                    raise
                my_lib.selenium_util.random_sleep(10)
                load_url(driver, wait, list_url)

        if debug_mode:
            break

        my_lib.selenium_util.random_sleep(10)

        load_url(driver, wait, list_url)
