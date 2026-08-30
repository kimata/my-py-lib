#!/usr/bin/env python3
"""
CAPTCHA を Slack を使って解決するライブラリです。

Usage:
  captcha.py [-c CONFIG] [-i IMAGE] [-D]

Options:
  -c CONFIG         : CONFIG を設定ファイルとして読み込んで実行します。
                      [default: tests/fixtures/config.example.yaml]
  -i IMAGE          : CAPTCA 画像。[default: tests/fixtures/captcha.png]
  -D                : デバッグモードで動作します。
"""

from __future__ import annotations

import logging
import pathlib
import tempfile
import time
import urllib.request
import warnings
from typing import TypeAlias

import PIL.Image

# pydub の正規表現で SyntaxWarning が出る問題を抑制（Python 3.12+）
# https://github.com/jiaaro/pydub/issues/795
warnings.filterwarnings("ignore", category=SyntaxWarning, module="pydub")
import pydub  # noqa: E402
import slack_sdk  # noqa: E402
import slack_sdk.errors  # noqa: E402

import my_lib.notify.mail  # noqa: E402
import my_lib.notify.slack  # noqa: E402
from my_lib.browser import Xpath  # noqa: E402
from my_lib.browser.protocol import Element, FrameScope, Page  # noqa: E402

_RESPONSE_WAIT_SEC: int = 5
_RESPONSE_TIMEOUT_SEC: int = 300

# find 系ヘルパーのスコープ（Page / FrameScope / Element はいずれも find/find_all を持つ）
_Findable: TypeAlias = Page | FrameScope | Element


def _find(scope: _Findable, xpath: str) -> Element:
    """要素を 1 つ取得する（存在しなければ例外）。"""
    element = scope.find(Xpath(xpath))
    if element is None:
        raise RuntimeError(f"要素が見つかりません: {xpath}")
    return element


def _click_if_exists(scope: FrameScope, xpath: str) -> bool:
    """要素が存在すればクリックして True を返す（存在しなければ False）。"""
    element = scope.find(Xpath(xpath))
    if element is None:
        return False
    element.click()
    return True


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


def resolve_recaptcha_auto(page: Page) -> None:
    # チェックボックス iframe: 「私はロボットではありません」をクリック
    with page.frame(Xpath('//iframe[@title="reCAPTCHA"]')) as checkbox_frame:
        checkbox_frame.wait_clickable(Xpath('//span[contains(@class, "recaptcha-checkbox")]')).click()

    # チャレンジ iframe: 音声チャレンジに切り替えて回答する
    with page.frame(Xpath('//iframe[contains(@title, "reCAPTCHA による確認")]')) as challenge_frame:
        challenge_frame.wait_clickable(Xpath('//div[@id="rc-imageselect-target"]'))
        challenge_frame.wait_clickable(Xpath('//button[contains(@title, "確認用の文字を音声")]')).click()
        time.sleep(0.5)

        audio_url = _find(challenge_frame, '//audio[@id="audio-source"]').attr("src")
        if audio_url is None:
            raise RuntimeError("Failed to get audio URL for CAPTCHA")

        text = recognize_audio(audio_url)

        input_elem = _find(challenge_frame, '//input[@id="audio-response"]')
        input_elem.type(text.lower())
        input_elem.press("Enter")


def resolve_recaptcha_mail(page: Page, config: my_lib.notify.mail.MailConfigTypes) -> None:
    # チェックボックス iframe: 「私はロボットではありません」をクリック
    with page.frame(Xpath('//iframe[@title="reCAPTCHA"]')) as checkbox_frame:
        checkbox_frame.wait_clickable(Xpath('//span[contains(@class, "recaptcha-checkbox")]')).click()

    # チャレンジ iframe: 画像チャレンジをメール経由で人間に解いてもらう
    with page.frame(Xpath('//iframe[contains(@title, "reCAPTCHA による確認")]')) as challenge_frame:
        challenge_frame.wait_clickable(Xpath('//div[@id="rc-imageselect-target"]'))
        while True:
            # NOTE: 問題画像を切り抜いてメールで送信
            my_lib.notify.mail.send(
                config,
                my_lib.notify.mail.build_message(
                    "reCAPTCHA",
                    "reCAPTCHA",
                    my_lib.notify.mail.ImageAttachmentFromData(
                        id="recaptcha",
                        data=_find(challenge_frame, "//body").screenshot(),
                    ),
                ),
            )

            tile_list = challenge_frame.find_all(
                Xpath('//table[contains(@class, "rc-imageselect-table")]//td[@role="button"]')
            )
            tile_idx_list = [elem.attr("tabindex") for elem in tile_list]

            # NOTE: メールを見て人間に選択するべき画像のインデックスを入力してもらう。
            # インデックスは左上を 0 として横方向に 1, 2, ... とする形。
            # 入力を簡単にするため、10以上は a, b, ..., g で指定。
            # 0 は入力の完了を意味する。
            select_str = input("選択タイル(1-9,a-g,end=0): ").strip()

            if select_str == "0":
                if _click_if_exists(challenge_frame, '//button[contains(text(), "スキップ")]'):
                    time.sleep(0.5)
                    continue
                if _click_if_exists(challenge_frame, '//button[contains(text(), "確認")]'):
                    time.sleep(0.5)

                    if challenge_frame.exists(
                        Xpath('//div[contains(text(), "新しい画像も")]')
                    ) or challenge_frame.exists(Xpath('//div[contains(text(), "もう一度")]')):
                        continue
                    break
                _click_if_exists(challenge_frame, '//button[contains(text(), "次へ")]')
                time.sleep(0.5)

            for idx in list(select_str):
                if ord(idx) <= 57:  # noqa: SIM108
                    tile_idx = ord(idx) - 48
                else:
                    tile_idx = ord(idx) - 97 + 10

                if tile_idx >= len(tile_idx_list):
                    continue

                index = tile_idx_list[tile_idx - 1]
                _click_if_exists(
                    challenge_frame,
                    f'//table[contains(@class, "rc-imageselect-table")]//td[@tabindex="{index}"]',
                )
            time.sleep(0.5)


def send_request_text_slack(
    config: my_lib.notify.slack.HasCaptchaConfig, title: str, message: str
) -> str | None:
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

    assert __doc__ is not None  # noqa: S101
    args = docopt.docopt(__doc__)

    config_file = args["-c"]
    captcha_file = args["-i"]
    debug_mode = args["-D"]

    my_lib.logger.init("test", level=logging.DEBUG if debug_mode else logging.INFO)

    config = my_lib.config.load(config_file)
    slack_config = my_lib.notify.slack.SlackConfig.parse(config["slack"])

    if not isinstance(
        slack_config,
        my_lib.notify.slack.SlackConfig | my_lib.notify.slack.SlackCaptchaOnlyConfig,
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
