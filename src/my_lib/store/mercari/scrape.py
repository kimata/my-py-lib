#!/usr/bin/env python3
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

RETRY_COUNT = 3
ITEM_LIST_XPATH = '//div[@data-testid="listed-item-list"]//div[contains(@class, "merListItem")]'


def parse_item(driver, index):
    time.sleep(5)
    item_xpath = ITEM_LIST_XPATH + "[" + str(index) + "]"
    item_url_xpath = item_xpath + "//a"
    item_name_xpath = item_xpath + '//span[contains(@class, "itemLabel")]'
    item_price_xpath = item_xpath + '//span[@class="merPrice"]/span[contains(@class, "number")]'

    # item_price_xpath = (
    #     item_xpath
    #     + '//div[@data-testid="price"]/span[contains(@class, "currency")]/following-sibling::span[1]'
    # )

    item_view_xpath = (
        item_xpath + '//mer-icon-eye-outline/following-sibling::span[contains(@class, "iconText")]'
    )
    item_private_xpath = item_xpath + '//span[contains(@class, "informationLabel")]'

    item_url = driver.find_element(selenium.webdriver.common.by.By.XPATH, item_url_xpath).get_attribute(
        "href"
    )
    item_id = item_url.split("/")[-1]

    name = driver.find_element(selenium.webdriver.common.by.By.XPATH, item_name_xpath).text

    if len(driver.find_elements(selenium.webdriver.common.by.By.XPATH, item_price_xpath)) == 0:
        driver.refresh()
        time.sleep(5)
        return parse_item(driver, index)

    price = int(
        driver.find_element(selenium.webdriver.common.by.By.XPATH, item_price_xpath).text.replace(",", "")
    )
    is_stop = 0

    if len(driver.find_elements(selenium.webdriver.common.by.By.XPATH, item_private_xpath)) != 0:
        is_stop = 1

    try:
        view = int(driver.find_element(selenium.webdriver.common.by.By.XPATH, item_view_xpath).text)
    except Exception:
        view = 0

    return {
        "id": item_id,
        "url": item_url,
        "name": name,
        "price": price,
        "view": view,
        "is_stop": is_stop,
    }


def execute_item(driver, wait, scrape_config, debug_mode, index, item_func_list):
    item = parse_item(driver, index)

    logging.info(
        "{name} [{id}] [{price:,}円] [{view:,} view] を処理します．".format(
            id=item["id"], name=item["name"], price=item["price"], view=item["view"]
        )
    )

    driver.execute_script("window.scrollTo(0, 0);")
    item_link = driver.find_element(
        selenium.webdriver.common.by.By.XPATH,
        ITEM_LIST_XPATH + "[" + str(index) + "]//a",
    )
    # NOTE: アイテムにスクロールしてから，ヘッダーに隠れないようちょっと前に戻す
    item_link.location_once_scrolled_into_view
    driver.execute_script("window.scrollTo(0, window.pageYOffset - 200);")
    item_link.click()

    wait.until(selenium.webdriver.support.expected_conditions.title_contains(re.sub(" +", " ", item["name"])))

    item_url = driver.current_url

    fail_count = 0
    for item_func in item_func_list:
        while True:
            try:
                item_func(driver, wait, scrape_config, item, debug_mode)
                fail_count = 0
                break
            except selenium.common.exceptions.TimeoutException:
                fail_count += 1

                if fail_count > RETRY_COUNT:
                    raise

                logging.warning("タイムアウトしたので，リトライします．")

                if driver.current_url != item_url:
                    driver.back()
                    time.sleep(1)
                if driver.current_url != item_url:
                    driver.get(item_url)
                my_lib.selenium_util.random_sleep(5)

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

    logging.info("{item_count}個の出品があります．".format(item_count=item_count))

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
