#!/usr/bin/env python3
"""
CAPTCHA を Slack を使って解決するライブラリです．

Usage:
  captcha.py [-c CONFIG] [-i IMAGE] [-D]

Options:
  -c CONFIG         : CONFIG を設定ファイルとして読み込んで実行します．[default: config.yaml]
  -i IMAGE          : CAPTCA 画像．[default: tests/data/captcha.png]
  -D                : デバッグモードで動作します．
"""

import logging
import pathlib
import tempfile
import time
import urllib

import my_lib.notify.mail
import my_lib.notify.slack
import my_lib.selenium_util
import pydub
import selenium.webdriver.common.by
import selenium.webdriver.common.keys
import selenium.webdriver.support
import slack_sdk
import speech_recognition

RESPONSE_WAIT_SEC = 5
RESPONSE_TIMEOUT_SEC = 300


def recognize_audio(audio_url):
    mp3_file = tempfile.NamedTemporaryFile(mode="wb", delete=False)
    wav_file = tempfile.NamedTemporaryFile(mode="wb", delete=False)

    try:
        urllib.request.urlretrieve(audio_url, mp3_file.name)  # noqa: S310

        pydub.AudioSegment.from_mp3(mp3_file.name).export(wav_file.name, format="wav")

        recognizer = speech_recognition.Recognizer()
        recaptcha_audio = speech_recognition.AudioFile(wav_file.name)
        with recaptcha_audio as source:
            audio = recognizer.record(source)

        return recognizer.recognize_google(audio, language="en-US")
    except:
        logging.exception("Failed to recognize audio")
        raise
    finally:
        pathlib.Path(mp3_file.name).unlink(missing_ok=True)
        pathlib.Path(wav_file.name).unlink(missing_ok=True)


def resolve_recaptcha_auto(driver, wait):
    wait.until(
        selenium.webdriver.support.expected_conditions.frame_to_be_available_and_switch_to_it(
            (selenium.webdriver.common.by.By.XPATH, '//iframe[@title="reCAPTCHA"]')
        )
    )
    my_lib.selenium_util.click_xpath(
        driver,
        '//span[contains(@class, "recaptcha-checkbox")]',
        move=True,
    )
    driver.switch_to.default_content()
    wait.until(
        selenium.webdriver.support.expected_conditions.frame_to_be_available_and_switch_to_it(
            (selenium.webdriver.common.by.By.XPATH, '//iframe[contains(@title, "reCAPTCHA による確認")]')
        )
    )
    wait.until(
        selenium.webdriver.support.expected_conditions.element_to_be_clickable(
            (selenium.webdriver.common.by.By.XPATH, '//div[@id="rc-imageselect-target"]')
        )
    )
    my_lib.selenium_util.click_xpath(driver, '//button[contains(@title, "確認用の文字を音声")]', move=True)
    time.sleep(0.5)

    audio_url = driver.find_element(
        selenium.webdriver.common.by.By.XPATH, '//audio[@id="audio-source"]'
    ).get_attribute("src")

    text = recognize_audio(audio_url)

    input_elem = driver.find_element(selenium.webdriver.common.by.By.XPATH, '//input[@id="audio-response"]')
    input_elem.send_keys(text.lower())
    input_elem.send_keys(selenium.webdriver.common.keys.Keys.ENTER)

    driver.switch_to.default_content()


def resolve_recaptcha_mail(driver, wait, config):
    wait.until(
        selenium.webdriver.support.expected_conditions.frame_to_be_available_and_switch_to_it(
            (selenium.webdriver.common.by.By.XPATH, '//iframe[@title="reCAPTCHA"]')
        )
    )
    my_lib.selenium_util.click_xpath(
        driver,
        '//span[contains(@class, "recaptcha-checkbox")]',
        move=True,
    )
    driver.switch_to.default_content()
    wait.until(
        selenium.webdriver.support.expected_conditions.frame_to_be_available_and_switch_to_it(
            (selenium.webdriver.common.by.By.XPATH, '//iframe[contains(@title, "reCAPTCHA による確認")]')
        )
    )
    wait.until(
        selenium.webdriver.support.expected_conditions.element_to_be_clickable(
            (selenium.webdriver.common.by.By.XPATH, '//div[@id="rc-imageselect-target"]')
        )
    )
    while True:
        # NOTE: 問題画像を切り抜いてメールで送信
        my_lib.notify.mail.send(
            config,
            my_lib.notify.mail.build_message(
                "reCAPTCHA",
                "reCAPTCHA",
                {
                    "data": driver.find_element(
                        selenium.webdriver.common.by.By.XPATH, "//body"
                    ).screenshot_as_png,
                    "id": "recaptcha",
                },
            ),
        )

        tile_list = driver.find_elements(
            selenium.webdriver.common.by.By.XPATH,
            '//table[contains(@class, "rc-imageselect-table")]//td[@role="button"]',
        )
        tile_idx_list = [elem.get_attribute("tabindex") for elem in tile_list]

        # NOTE: メールを見て人間に選択するべき画像のインデックスを入力してもらう．
        # インデックスは左上を 0 として横方向に 1, 2, ... とする形．
        # 入力を簡単にするため，10以上は a, b, ..., g で指定．
        # 0 は入力の完了を意味する．
        select_str = input("選択タイル(1-9,a-g,end=0): ").strip()

        if select_str == "0":
            if my_lib.selenium_util.click_xpath(
                driver, '//button[contains(text(), "スキップ")]', move=True, is_warn=False
            ):
                time.sleep(0.5)
                continue
            if my_lib.selenium_util.click_xpath(
                driver, '//button[contains(text(), "確認")]', move=True, is_warn=False
            ):
                time.sleep(0.5)

                if my_lib.selenium_util.is_display(
                    driver, '//div[contains(text(), "新しい画像も")]'
                ) or my_lib.selenium_util.is_display(driver, '//div[contains(text(), "もう一度")]'):
                    continue
                break
            my_lib.selenium_util.click_xpath(
                driver, '//button[contains(text(), "次へ")]', move=True, is_warn=False
            )
            time.sleep(0.5)

        for idx in list(select_str):
            if ord(idx) <= 57:  # noqa: SIM108
                tile_idx = ord(idx) - 48
            else:
                tile_idx = ord(idx) - 97 + 10

            if tile_idx >= len(tile_idx_list):
                continue

            index = tile_idx_list[tile_idx - 1]
            my_lib.selenium_util.click_xpath(
                driver,
                f'//table[contains(@class, "rc-imageselect-table")]//td[@tabindex="{index}"]',
                move=True,
            )
        time.sleep(0.5)

    driver.switch_to.default_content()


def send_request_text_slack(token, ch_name, title, message):
    logging.info("CAPTCHA: send request [text]")

    try:
        resp = my_lib.notify.slack.send(token, ch_name, my_lib.notify.slack.format_simple(title, message))

        return resp["ts"]
    except slack_sdk.errors.SlackApiError:
        logging.exception("Failed to send text request")
        return None


def recv_response_text_slack(token, ch_id, ts, timeout_sec=RESPONSE_TIMEOUT_SEC):
    logging.info("CAPTCHA: receive response [text]")

    time.sleep(RESPONSE_WAIT_SEC)
    try:
        client = slack_sdk.WebClient(token=token)
        count = 0
        thread_ts = None
        while True:
            resp = client.conversations_history(channel=ch_id, limit=3)

            for message in resp["messages"]:
                if ("thread_ts" in message) and (message["ts"] == ts):
                    thread_ts = message["thread_ts"]
                    break
            else:
                count += 1
                if count > (timeout_sec / RESPONSE_WAIT_SEC):
                    return None
                time.sleep(RESPONSE_WAIT_SEC)
                continue
            break

        if thread_ts is None:
            return None

        resp = client.conversations_replies(channel=ch_id, ts=thread_ts)

        return resp["messages"][-1]["text"].strip()
    except slack_sdk.errors.SlackApiError:
        logging.exception("Failed to receive response")


def send_challenge_image_slack(token, ch_id, title, img, text):
    logging.info("CAPTCHA: send challenge [image]")

    return my_lib.notify.slack.upload_image(token, ch_id, title, img, text)


def recv_response_image_slack(token, ch_id, file_id, timeout_sec=RESPONSE_TIMEOUT_SEC):
    logging.info("CAPTCHA: receive response [image]")

    time.sleep(RESPONSE_WAIT_SEC)
    try:
        client = slack_sdk.WebClient(token=token)

        count = 0
        thread_ts = None
        while True:
            resp = client.conversations_history(channel=ch_id, limit=3)

            for message in resp["messages"]:
                if (
                    ("thread_ts" in message)
                    and ("files" in message)
                    and (message["files"][0]["id"] == file_id)
                ):
                    thread_ts = message["thread_ts"]
                    break
            else:
                count += 1
                if count > (timeout_sec / RESPONSE_WAIT_SEC):
                    return None
                time.sleep(RESPONSE_WAIT_SEC)
                continue
            break

        if thread_ts is None:
            return None

        resp = client.conversations_replies(channel=ch_id, ts=thread_ts)

        return resp["messages"][-1]["text"].strip()
    except slack_sdk.errors.SlackApiError:
        logging.exception("Failed to receive response")


if __name__ == "__main__":
    # TEST Code
    import docopt
    import my_lib.config
    import my_lib.logger
    import PIL.Image

    args = docopt.docopt(__doc__)

    config_file = args["-c"]
    captcha_file = args["-i"]
    debug_mode = args["-D"]

    my_lib.logger.init("test", level=logging.DEBUG if debug_mode else logging.INFO)

    config = my_lib.config.load(config_file)
    img = PIL.Image.open(captcha_file)

    file_id = send_challenge_image_slack(
        config["slack"]["bot_token"],
        config["slack"]["captcha"]["channel"]["id"],
        "Amazon Login",
        img,
        "画像 CAPTCHA",
    )

    captcha = recv_response_image_slack(
        config["slack"]["bot_token"], config["slack"]["captcha"]["channel"]["id"], file_id
    )

    logging.info('CAPTCHA is "%s"', captcha)

    ts = send_request_text_slack(
        config["slack"]["bot_token"],
        config["slack"]["captcha"]["channel"]["id"],
        "CAPTCHA",
        "SMS で送られてきた数字を入力してください",
    )

    captcha = recv_response_text_slack(
        config["slack"]["bot_token"], config["slack"]["captcha"]["channel"]["id"], ts
    )

    logging.info('CAPTCHA is "%s"', captcha)
