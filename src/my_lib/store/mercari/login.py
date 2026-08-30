#!/usr/bin/env python3
"""メルカリへのログイン（LINE 認証経由）。

ブラウザ操作はバックエンド非依存の my_lib.browser.Page 越しに行う
（Selenium / Patchright を問わない）。
"""

from __future__ import annotations

import contextlib
import logging
import pathlib
import random
import time

import my_lib.browser
import my_lib.browser.helpers
import my_lib.notify.slack
import my_lib.store.captcha
import my_lib.store.mercari.config
from my_lib.browser import Xpath
from my_lib.browser.protocol import Page

_LINE_LOGIN_TIMEOUT: float = 60.0

_LOGIN_URL: str = "https://jp.mercari.com"


def execute(
    page: Page,
    mercari_login: my_lib.store.mercari.config.MercariLoginConfig,
    line_login: my_lib.store.mercari.config.LineLoginConfig,
    slack_config: my_lib.notify.slack.HasCaptchaConfig | my_lib.notify.slack.SlackEmptyConfig,
    dump_path: pathlib.Path,
) -> None:
    try:
        # NOTE: エラーが起きた後とかだと、一発でページが表示されないことがあるので、事前に一回アクセスさせる。
        logging.info("メルカリにアクセスします。")
        page.goto(_LOGIN_URL)
        page.wait_visible(Xpath("//footer"))

        _execute_impl(page, line_login, slack_config)
    except Exception:
        logging.exception("ログインをリトライします。")
        my_lib.browser.helpers.dump_page(page, random.randint(0, 99), dump_path)  # noqa: S311
        # NOTE: 1回だけリトライする
        time.sleep(10)
        _execute_impl(page, line_login, slack_config)


def _execute_impl(
    page: Page,
    line_login: my_lib.store.mercari.config.LineLoginConfig,
    slack_config: my_lib.notify.slack.HasCaptchaConfig | my_lib.notify.slack.SlackEmptyConfig,
) -> None:
    logging.info("ログインを行います。")
    page.goto(_LOGIN_URL)

    page.wait_visible(Xpath('//button[contains(@class, "iconButton") and @aria-label="お知らせ"]'))

    start_button = page.find(Xpath('//button[contains(text(), "はじめる")]'))
    if start_button is not None:
        start_button.click()
        time.sleep(1)

    if page.exists(Xpath('//button[@data-testid="account-button"]')):
        logging.info("既にログイン済みでした。")
        return

    page.wait_clickable(Xpath('//button[contains(text(), "ログイン")]')).click()
    page.wait_visible(Xpath('//h1[contains(text(), "ログイン")]'))

    _login_via_line(page, line_login, slack_config)

    page.wait_visible(Xpath('//h1[contains(text(), "電話番号の確認")]'))

    logging.info("認証番号の対応を行います。")

    code: str | None = None
    ts: str | None = None
    if not isinstance(slack_config, my_lib.notify.slack.SlackEmptyConfig):
        logging.info("Slack に SMS で送られてきた認証番号を入力してください")
        ts = my_lib.store.captcha.send_request_text_slack(
            slack_config,
            "Mercari",
            "📱 SMS で送られてきた認証番号を入力してください",
        )
        if ts is None:
            raise RuntimeError("Failed to send request text to Slack")
        code = my_lib.store.captcha.recv_response_text_slack(slack_config, ts)
    else:
        code = input("SMS で送られてきた認証番号を入力してください: ")

    if code is None:
        raise RuntimeError("Failed to receive authentication code")

    # NOTE: 認証番号入力欄は name="authNumber"（one-time-code）。React 制御のため 1 文字ずつ打鍵する。
    page.wait_visible(Xpath('//input[@name="authNumber"]')).type(code, sequential=True)

    # NOTE: 全桁入力で自動送信される場合があるため、送信ボタンがあれば押しつつ、無ければ自動遷移を待つ。
    submit = page.find(Xpath('//button[@data-testid="submit"]'))
    if submit is not None:
        with contextlib.suppress(Exception):
            submit.click()

    page.wait_visible(Xpath('//div[@class="merNavigationTopMenu"]'))
    page.wait_clickable(Xpath('//button[@data-testid="account-button"]'))

    if not isinstance(slack_config, my_lib.notify.slack.SlackEmptyConfig) and ts is not None:
        my_lib.notify.slack.send(
            slack_config,
            slack_config.captcha.channel.name,
            my_lib.notify.slack.format_simple("CAPTCHA", "🎉 成功しました"),
            thread_ts=ts,
        )

    logging.info("ログインに成功しました。")


def _login_via_line(
    page: Page,
    line_login: my_lib.store.mercari.config.LineLoginConfig,
    slack_config: my_lib.notify.slack.HasCaptchaConfig | my_lib.notify.slack.SlackEmptyConfig,
) -> None:
    # NOTE: ログインページが電話番号入力画面になった場合、「SNSでログインする」を先にクリック
    if page.exists(Xpath('//button[contains(., "SNSでログインする")]')):
        page.wait_clickable(Xpath('//button[contains(., "SNSでログインする")]')).click()
        time.sleep(1)

    page.wait_clickable(Xpath('//button[span[contains(text(), "LINEでログイン")]]')).click()

    page.wait_until(my_lib.browser.helpers.title_contains_js("LINE Login"))

    # NOTE: LINE ログインページのフォーム描画には間があるため、tid 入力欄の出現を待ってから分岐する。
    #       出現すれば認証情報を入力、出現しなければ既存 LINE セッションの同意ボタンを押す。
    try:
        tid_input = page.wait_visible(Xpath('//input[@name="tid"]'), timeout=15)
    except my_lib.browser.WaitTimeoutError:
        tid_input = None

    if tid_input is not None:
        tid_input.type(line_login.user)
        page.wait_visible(Xpath('//input[@name="tpasswd"]')).type(line_login.password)
        page.wait_clickable(Xpath('//button[contains(text(), "ログイン")]')).click()
    else:
        page.wait_clickable(Xpath('//button[.//span[normalize-space()="ログイン"]]')).click()

    if "LINE Login" not in page.title:
        return

    code = ""
    try:
        number = page.wait_visible(Xpath('//p[contains(@class, "Number")]'), timeout=15)
        code = number.text
    except my_lib.browser.WaitTimeoutError:
        logging.warning("LINE 認証番号の要素が見つかりませんでした")

    if not isinstance(slack_config, my_lib.notify.slack.SlackEmptyConfig):
        my_lib.store.captcha.send_request_text_slack(
            slack_config,
            "LINE",
            f"📱 LINE アプリで認証番号「{code}」を入力してください。",
        )
    logging.info("LINE アプリで認証番号「%s」を入力してください。", code)

    # NOTE: 「許可する」ボタンの出現、または「電話番号の確認」画面への遷移のいずれかを待つ。
    deadline = _LINE_LOGIN_TIMEOUT
    step = 2.0
    while deadline > 0:
        if page.exists(Xpath('//button[contains(normalize-space(.), "許可する")]')):
            page.wait_clickable(Xpath('//button[contains(normalize-space(.), "許可する")]')).click()
            back = page.find(Xpath('//span[contains(normalize-space(.), "戻る")]'))
            if back is not None:
                back.click()
            break
        if page.exists(Xpath('//h1[contains(text(), "電話番号の確認")]')):
            break
        time.sleep(step)
        deadline -= step

    page.wait_visible(Xpath('//h1[contains(text(), "電話番号の確認")]'))
