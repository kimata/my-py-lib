#!/usr/bin/env python3
"""
CAPTCHA を Slack を使って解決するライブラリです。

Usage:
  captcha.py [-c CONFIG] [-i IMAGE] [-D]

Options:
  -c CONFIG         : CONFIG を設定ファイルとして読み込んで実行します。[default: tests/data/config.example.yaml]
  -i IMAGE          : CAPTCA 画像。[default: tests/data/captcha.png]
  -D                : デバッグモードで動作します。
"""

from __future__ import annotations

import logging
import pathlib
import tempfile
import time
import urllib.request
import warnings

import PIL.Image

# pydub の正規表現で SyntaxWarning が出る問題を抑制（Python 3.12+）
# https://github.com/jiaaro/pydub/issues/795
warnings.filterwarnings("ignore", category=SyntaxWarning, module="pydub")
import pydub  # noqa: E402
import selenium.webdriver.common.by
import selenium.webdriver.common.keys
import selenium.webdriver.remote.webdriver
import selenium.webdriver.support
import selenium.webdriver.support.expected_conditions
import selenium.webdriver.support.wait
import slack_sdk
import slack_sdk.errors

import my_lib.notify.mail
import my_lib.notify.slack
import my_lib.selenium_util

_RESPONSE_WAIT_SEC: int = 5
_RESPONSE_TIMEOUT_SEC: int = 300


def recognize_audio(audio_url: str) -> str:
    import speech_recognition

    with tempfile.NamedTemporaryFile(mode="wb", delete=False) as mp3_file:
        mp3_file_name = mp3_file.name
    with tempfile.NamedTemporaryFile(mode="wb", delete=False) as wav_file:
        wav_file_name = wav_file.name

    try:
        urllib.request.urlretrieve(audio_url, mp3_file_name)  # noqa: S310

        pydub.AudioSegment.from_mp3(mp3_file_name).export(wav_file_name, format="wav")

        recognizer = speech_recognition.Recognizer()
        recaptcha_audio = speech_recognition.AudioFile(wav_file_name)
        with recaptcha_audio as source:
            audio = recognizer.record(source)

        return recognizer.recognize_google(audio, language="en-US")  # type: ignore[attr-defined]
    except Exception:
        logging.exception("Failed to recognize audio")
        raise
    finally:
        pathlib.Path(mp3_file_name).unlink(missing_ok=True)
        pathlib.Path(wav_file_name).unlink(missing_ok=True)


def resolve_recaptcha_auto(
    driver: selenium.webdriver.remote.webdriver.WebDriver,
    wait: selenium.webdriver.support.wait.WebDriverWait,
) -> None:
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

    if audio_url is None:
        raise RuntimeError("Failed to get audio URL for CAPTCHA")

    text = recognize_audio(audio_url)

    input_elem = driver.find_element(selenium.webdriver.common.by.By.XPATH, '//input[@id="audio-response"]')
    input_elem.send_keys(text.lower())
    input_elem.send_keys(selenium.webdriver.common.keys.Keys.ENTER)

    driver.switch_to.default_content()


def resolve_recaptcha_mail(
    driver: selenium.webdriver.remote.webdriver.WebDriver,
    wait: selenium.webdriver.support.wait.WebDriverWait,
    config: my_lib.notify.mail.MailConfigTypes,
) -> None:
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
                my_lib.notify.mail.ImageAttachmentFromData(
                    id="recaptcha",
                    data=driver.find_element(
                        selenium.webdriver.common.by.By.XPATH, "//body"
                    ).screenshot_as_png,
                ),
            ),
        )

        tile_list = driver.find_elements(
            selenium.webdriver.common.by.By.XPATH,
            '//table[contains(@class, "rc-imageselect-table")]//td[@role="button"]',
        )
        tile_idx_list = [elem.get_attribute("tabindex") for elem in tile_list]

        # NOTE: メールを見て人間に選択するべき画像のインデックスを入力してもらう。
        # インデックスは左上を 0 として横方向に 1, 2, ... とする形。
        # 入力を簡単にするため、10以上は a, b, ..., g で指定。
        # 0 は入力の完了を意味する。
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


def send_request_text_slack(config: my_lib.notify.slack.HasCaptchaConfig, title: str, message: str) -> str | None:
    logging.info("CAPTCHA: send request [text]")

    title = "CAPTCHA: " + title
    try:
        resp = my_lib.notify.slack.send(
            config, config.captcha.channel.name, my_lib.notify.slack.format_simple(title, message)
        )

        if resp is None:
            return None
        return resp["ts"]
    except slack_sdk.errors.SlackApiError:
        logging.exception("Failed to send text request")
        return None


def recv_response_text_slack(
    config: my_lib.notify.slack.HasCaptchaConfig, ts: str, timeout_sec: int = _RESPONSE_TIMEOUT_SEC
) -> str | None:
    logging.info("CAPTCHA: receive response [text]")

    ch_id = config.captcha.channel.id
    if ch_id is None:
        raise ValueError("captcha channel id is not configured")

    time.sleep(_RESPONSE_WAIT_SEC)
    try:
        client = slack_sdk.WebClient(token=config.bot_token)
        count = 0
        thread_ts: str | None = None
        while True:
            resp = client.conversations_history(channel=ch_id, limit=3)
            if resp is None:
                raise RuntimeError("Failed to get conversations history")

            messages = resp["messages"]
            if messages is None:
                raise RuntimeError("Failed to get messages from conversations history")

            for message in messages:
                if ("thread_ts" in message) and (message["ts"] == ts):
                    thread_ts = message["thread_ts"]
                    break
            else:
                count += 1
                if count > (timeout_sec / _RESPONSE_WAIT_SEC):
                    return None
                time.sleep(_RESPONSE_WAIT_SEC)
                continue
            break

        if thread_ts is None:
            return None

        resp = client.conversations_replies(channel=ch_id, ts=thread_ts)
        if resp is None:
            raise RuntimeError("Failed to get conversations replies")

        messages = resp["messages"]
        if messages is None:
            raise RuntimeError("Failed to get messages from conversations replies")

        return messages[-1]["text"].strip()
    except slack_sdk.errors.SlackApiError:
        logging.exception("Failed to receive response")
        return None


def send_challenge_image_slack(
    config: my_lib.notify.slack.HasCaptchaConfig, title: str, img: PIL.Image.Image, text: str
) -> str | None:
    logging.info("CAPTCHA: send challenge [image]")

    ch_id = config.captcha.channel.id
    if ch_id is None:
        raise ValueError("captcha channel id is not configured")

    return my_lib.notify.slack.upload_image(config, ch_id, title, img, text)


def recv_response_image_slack(
    config: my_lib.notify.slack.HasCaptchaConfig, file_id: str, timeout_sec: int = _RESPONSE_TIMEOUT_SEC
) -> str | None:
    logging.info("CAPTCHA: receive response [image]")

    ch_id = config.captcha.channel.id
    if ch_id is None:
        raise ValueError("captcha channel id is not configured")

    time.sleep(_RESPONSE_WAIT_SEC)
    try:
        client = slack_sdk.WebClient(token=config.bot_token)

        count = 0
        thread_ts: str | None = None
        while True:
            resp = client.conversations_history(channel=ch_id, limit=3)
            if resp is None:
                raise RuntimeError("Failed to get conversations history")

            messages = resp["messages"]
            if messages is None:
                raise RuntimeError("Failed to get messages from conversations history")

            for message in messages:
                if (
                    ("thread_ts" in message)
                    and ("files" in message)
                    and (message["files"][0]["id"] == file_id)
                ):
                    thread_ts = message["thread_ts"]
                    break
            else:
                count += 1
                if count > (timeout_sec / _RESPONSE_WAIT_SEC):
                    return None
                time.sleep(_RESPONSE_WAIT_SEC)
                continue
            break

        if thread_ts is None:
            return None

        resp = client.conversations_replies(channel=ch_id, ts=thread_ts)
        if resp is None:
            raise RuntimeError("Failed to get conversations replies")

        messages = resp["messages"]
        if messages is None:
            raise RuntimeError("Failed to get messages from conversations replies")

        text = messages[-1]["text"].strip()

        logging.info("CAPTCHA: receive %s", text)

        return text
    except slack_sdk.errors.SlackApiError:
        logging.exception("Failed to receive response")
        return None


if __name__ == "__main__":
    # TEST Code
    import docopt
    import PIL.Image

    import my_lib.config
    import my_lib.logger

    assert __doc__ is not None
    args = docopt.docopt(__doc__)

    config_file = args["-c"]
    captcha_file = args["-i"]
    debug_mode = args["-D"]

    my_lib.logger.init("test", level=logging.DEBUG if debug_mode else logging.INFO)

    config = my_lib.config.load(config_file)
    slack_config = my_lib.notify.slack.parse_config(config["slack"])

    if not isinstance(
        slack_config, (my_lib.notify.slack.SlackConfig, my_lib.notify.slack.SlackCaptchaOnlyConfig)
    ):
        raise ValueError("captcha 設定がありません")

    img = PIL.Image.open(captcha_file)

    file_id = send_challenge_image_slack(slack_config, "Amazon Login", img, "🔐 画像 CAPTCHA")

    if file_id is None:
        raise RuntimeError("Failed to send challenge image")

    captcha = recv_response_image_slack(slack_config, file_id)

    logging.info('CAPTCHA is "%s"', captcha)

    ts = send_request_text_slack(slack_config, "CAPTCHA", "📱 SMS で送られてきた数字を入力してください")

    if ts is None:
        raise RuntimeError("Failed to send request text")

    captcha = recv_response_text_slack(slack_config, ts)

    logging.info('CAPTCHA is "%s"', captcha)
