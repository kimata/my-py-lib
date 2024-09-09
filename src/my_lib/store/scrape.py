#!/usr/bin/env python3
"""
ショップをスクレイピングで解析して価格情報を取得するライブラリです．

Usage:
  scrape.py [-c CONFIG] [-d]

Options:n
  -c CONFIG         : CONFIG を設定ファイルとして読み込んで実行します．[default: config.yaml]
  -d                : デバッグモードで動作します．
"""

import logging
import os
import pathlib
import random
import re
import string
import time
import urllib

# import my_lib.captcha
import my_lib.selenium_util
import selenium.webdriver.common.by
import selenium.webdriver.support
import selenium.webdriver.support.wait

TIMEOUT_SEC = 4
DATA_PATH = pathlib.Path(os.path.dirname(__file__)).parent / "data"  # noqa: PTH120
DUMP_PATH = str(DATA_PATH / "debug")


def resolve_template(template, item):
    tmpl = string.Template(template)
    return tmpl.safe_substitute(item_name=item["name"])


def process_action(driver, wait, item, action_list, name="action"):  # noqa:C901
    logging.info("Process action: %s", name)

    for action in action_list:
        logging.debug("action: %s.", action["type"])
        if action["type"] == "input":
            if not my_lib.selenium_util.xpath_exists(driver, resolve_template(action["xpath"], item)):
                logging.debug("Element not found. Interrupted.")
                return
            driver.find_element(
                selenium.webdriver.common.by.By.XPATH, resolve_template(action["xpath"], item)
            ).send_keys(resolve_template(action["value"], item))
        elif action["type"] == "click":
            if not my_lib.selenium_util.xpath_exists(driver, resolve_template(action["xpath"], item)):
                logging.debug("Element not found. Interrupted.")
                return
            driver.find_element(
                selenium.webdriver.common.by.By.XPATH, resolve_template(action["xpath"], item)
            ).click()
        # elif action["type"] == "recaptcha":
        #     my_lib.captcha.resolve_mp3(driver, wait)
        # elif action["type"] == "captcha":
        #     input_xpath = '//input[@id="captchacharacters"]'
        #     if not my_lib.selenium_util.xpath_exists(driver, input_xpath):
        #         logging.debug("Element not found.")
        #         continue
        #     domain = urllib.parse.urlparse(driver.current_url).netloc

        #     logging.warning("Resolve captche is needed at %s.", domain)

        #     my_lib.selenium_util.dump_page(driver, int(random.random() * 100))  # noqa: S311
        #     code = input(f"{domain} captcha: ")

        #     driver.find_element(selenium.webdriver.common.by.By.XPATH, input_xpath).send_keys(code)
        #     driver.find_element(selenium.webdriver.common.by.By.XPATH, '//button[@type="submit"]').click()
        elif action["type"] == "sixdigit":
            # NOTE: これは今のところ Ubiquiti Store USA 専用
            digit_code = input(f"{urllib.parse.urlparse(driver.current_url).netloc} app code: ")
            for i, code in enumerate(list(digit_code)):
                driver.find_element(
                    selenium.webdriver.common.by.By.XPATH, '//input[@data-id="' + str(i) + '"]'
                ).send_keys(code)
        else:
            raise ValueError("Unknown action")

        time.sleep(4)


def process_preload(driver, wait, item, loop):
    logging.info("Process preload: %s", item["name"])

    if "preload" not in item:
        return

    if (loop % item["preload"]["every"]) != 0:
        logging.info("Skip preload. (loop=%d)", loop)
        return

    driver.get(item["preload"]["url"])
    time.sleep(2)

    process_action(driver, wait, item, item["preload"]["action"], "preload action")


def check_impl(driver, item, loop):  # noqa: PLR0912, C901
    wait = selenium.webdriver.support.wait.WebDriverWait(driver, TIMEOUT_SEC)

    process_preload(driver, wait, item, loop)

    logging.info("Fetch: %s", item["url"])

    driver.get(item["url"])
    wait.until(selenium.webdriver.support.expected_conditions.presence_of_all_elements_located)
    time.sleep(2)

    if "action" in item:
        process_action(driver, wait, item, item["action"])

    logging.info("Parse: %s", item["name"])

    if not my_lib.selenium_util.xpath_exists(driver, item["price_xpath"]):
        logging.warning("%s: price not found.", item["name"])
        item["stock"] = 0
        my_lib.selenium_util.dump_page(driver, int(random.random() * 100))  # noqa: S311
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
        item["price"] = int(m.group(1).replace(",", ""))
    except Exception:
        if item["stock"] == 0:
            # NOTE: 在庫がない場合は，価格が取得できなくてもエラーにしない
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
        m = re.match(
            r"background-image: url\([\"'](.*)[\"']\)",
            style_text,
        )
        thumb_url = m.group(1)
        if not re.compile(r"^\.\.").search(thumb_url):
            thumb_url = "/" + thumb_url

        item["thumb_url"] = urllib.parse.urljoin(driver.current_url, thumb_url)

    return item


def fetch_price(driver, item, loop):
    try:
        logging.warning("Check %s", item["name"])

        return check_impl(driver, item, loop)
    except:
        logging.exception("Failed to check %s", driver.current_url)
        my_lib.selenium_util.dump_page(driver, int(random.random() * 100))  # noqa: S311
        my_lib.selenium_util.clean_dump()
        raise


if __name__ == "__main__":
    # TEST Code
    import docopt
    import my_lib.config
    import my_lib.logger

    args = docopt.docopt(__doc__)

    config_file = args["-c"]
    debug_mode = args["-d"]

    my_lib.logger.init("test", level=logging.DEBUG if debug_mode else logging.INFO)

    config = my_lib.config.load(config_file)

    driver = my_lib.selenium_util.create_driver("Test", pathlib.Path("data"))

    item = {
        "name": "Raspberry Pi 5 / 8GB (switch-science)",
        "url": "https://www.switch-science.com/products/9250",
        "price_xpath": '//div[contains(@class, "price__current")]/span[contains(@class, "money")]',
        "thumb_img_xpath": '//div[@class="product-gallery--image-background"]/img',
        "unavailable_xpath": '//button[contains(@id, "BIS_trigger") and contains(text(), "入荷通知登録")]',
    }

    logging.info(fetch_price(driver, item, 0))
