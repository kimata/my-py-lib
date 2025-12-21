#!/usr/bin/env python3
"""
Slack で通知を行います。

Usage:
  slack.py [-c CONFIG] [-m MESSAGE] [-D]

Options:
  -c CONFIG         : CONFIG を設定ファイルとして読み込んで実行します。[default: config.yaml]
  -m MESSAGE        : 送信するメッセージ。[default: TEST]
  -D                : デバッグモードで動作します。
"""

from __future__ import annotations

import collections
import json
import logging
import math
import os
import pathlib
import tempfile
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, TypedDict

import slack_sdk
import slack_sdk.web.slack_response
from PIL import Image

import my_lib.footprint

NOTIFY_FOOTPRINT: pathlib.Path = pathlib.Path("/dev/shm/notify/slack/error")  # noqa: S108
INTERVAL_MIN: int = 60

SIMPLE_TMPL = """\
[
    {{
        "type": "header",
    "text": {{
            "type": "plain_text",
        "text": "{title}",
            "emoji": true
        }}
    }},
    {{
        "type": "section",
        "text": {{
            "type": "mrkdwn",
        "text": {message}
    }}
    }}
]
"""


class FormattedMessage(TypedDict):
    text: str
    json: list[dict[str, Any]]


class AttachImage(TypedDict):
    data: Image.Image
    text: str


@dataclass(frozen=True)
class SlackChannelConfig:
    """Slack チャンネル設定"""

    name: str
    id: str | None = None  # info チャンネルでは id は不要


@dataclass(frozen=True)
class SlackInfoConfig:
    """Slack 情報通知設定"""

    channel: SlackChannelConfig


@dataclass(frozen=True)
class SlackCaptchaConfig:
    """Slack CAPTCHA 通知設定"""

    channel: SlackChannelConfig


@dataclass(frozen=True)
class SlackErrorConfig:
    """Slack エラー通知設定"""

    channel: SlackChannelConfig
    interval_min: int


@dataclass(frozen=True)
class SlackConfig:
    """Slack 設定"""

    bot_token: str
    from_name: str
    info: SlackInfoConfig
    captcha: SlackCaptchaConfig
    error: SlackErrorConfig


def _parse_slack_channel(data: dict[str, Any]) -> SlackChannelConfig:
    return SlackChannelConfig(
        name=data["name"],
        id=data.get("id"),
    )


def _parse_slack_info(data: dict[str, Any]) -> SlackInfoConfig:
    return SlackInfoConfig(channel=_parse_slack_channel(data["channel"]))


def _parse_slack_captcha(data: dict[str, Any]) -> SlackCaptchaConfig:
    return SlackCaptchaConfig(channel=_parse_slack_channel(data["channel"]))


def _parse_slack_error(data: dict[str, Any]) -> SlackErrorConfig:
    return SlackErrorConfig(
        channel=_parse_slack_channel(data["channel"]),
        interval_min=data["interval_min"],
    )


def parse_slack_config(data: dict[str, Any]) -> SlackConfig:
    """Slack 設定をパースする"""
    return SlackConfig(
        bot_token=data["bot_token"],
        from_name=data["from"],
        info=_parse_slack_info(data["info"]),
        captcha=_parse_slack_captcha(data["captcha"]),
        error=_parse_slack_error(data["error"]),
    )


# NOTE: テスト用
thread_local = threading.local()
notify_hist: collections.defaultdict[str, list[str]] = collections.defaultdict(lambda: [])  # noqa: PIE807
_hist_lock = threading.Lock()  # スレッドセーフティ用ロック


def format_simple(title: str, message: str) -> FormattedMessage:
    return {
        "text": message,
        "json": json.loads(SIMPLE_TMPL.format(title=title, message=json.dumps(message))),
    }


def send(
    token: str, ch_name: str, message: FormattedMessage, thread_ts: str | None = None
) -> slack_sdk.web.slack_response.SlackResponse | None:
    try:
        client = slack_sdk.WebClient(token=token)

        kwargs: dict[str, Any] = {
            "channel": ch_name,
            "text": message["text"],
            "blocks": message["json"],
        }
        if thread_ts:
            kwargs["thread_ts"] = thread_ts

        return client.chat_postMessage(**kwargs)
    except slack_sdk.errors.SlackClientError:
        logging.exception("Failed to send Slack message")
        return None


def split_send(
    token: str,
    ch_name: str,
    title: str,
    message: str,
    formatter: Callable[[str, str], FormattedMessage] = format_simple,
) -> str | None:
    LINE_SPLIT = 20

    logging.info("Post slack channel: %s", ch_name)

    if not message or not message.strip():
        logging.warning("Empty message, skipping Slack notification")
        return None

    message_lines = message.splitlines()
    total = math.ceil(len(message_lines) / LINE_SPLIT)
    thread_ts: str | None = None

    for i in range(0, len(message_lines), LINE_SPLIT):
        # メッセージ内容を事前に生成
        message_content = "\n".join(message_lines[i : i + LINE_SPLIT])

        # 空のメッセージはスキップ
        if not message_content or not message_content.strip():
            continue

        split_title = title if total == 1 else f"{title} ({(i // LINE_SPLIT) + 1}/{total})"

        # 最初のメッセージを送信
        if i == 0:
            response = send(
                token,
                ch_name,
                formatter(split_title, message_content),
            )
            # 最初のメッセージのタイムスタンプを保存（スレッドがない場合でも画像投稿で使用）
            if response:
                thread_ts = response.get("ts")
        elif thread_ts:
            # 2つ以上に分割される場合は、2番目以降をスレッドへの返信として送信
            try:
                client = slack_sdk.WebClient(token=token)
                formatted_msg = formatter(split_title, message_content)
                client.chat_postMessage(
                    channel=ch_name,
                    text=formatted_msg["text"],
                    blocks=formatted_msg["json"],
                    thread_ts=thread_ts,
                )
            except slack_sdk.errors.SlackClientError:
                logging.exception("Failed to send Slack message in thread")
        else:
            # フォールバック: thread_tsが取得できなかった場合は通常通り送信
            send(
                token,
                ch_name,
                formatter(split_title, message_content),
            )

        time.sleep(1)

    return thread_ts


def info(
    config: SlackConfig,
    title: str,
    message: str,
    formatter: Callable[[str, str], FormattedMessage] = format_simple,
) -> None:
    title = "Info: " + title
    split_send(config.bot_token, config.info.channel.name, title, message, formatter)


def upload_image(  # noqa: PLR0913
    token: str,
    ch_id: str,
    title: str,
    img: Image.Image,
    text: str,
    thread_ts: str | None = None,
) -> str | None:
    client = slack_sdk.WebClient(token=token)

    with tempfile.TemporaryDirectory() as dname:
        img_path = pathlib.Path(dname) / "image.png"
        img.save(img_path)

        try:
            kwargs: dict[str, Any] = {
                "channel": ch_id,
                "file": str(img_path),
                "title": title,
                "initial_comment": text,
            }
            if thread_ts:
                kwargs["thread_ts"] = thread_ts

            resp = client.files_upload_v2(**kwargs)

            return resp["files"][0]["id"]
        except slack_sdk.errors.SlackApiError:
            logging.exception("Failed to send Slack message")

            return None


def error(
    config: SlackConfig,
    title: str,
    message: str,
    formatter: Callable[[str, str], FormattedMessage] = format_simple,
) -> None:
    title = "Error: " + title

    hist_add(message)

    interval_min = config.error.interval_min
    if my_lib.footprint.elapsed(NOTIFY_FOOTPRINT) <= interval_min * 60:
        logging.warning("Interval is too short. Skipping.")
        return

    split_send(config.bot_token, config.error.channel.name, title, message, formatter)

    my_lib.footprint.update(NOTIFY_FOOTPRINT)


def error_with_image(
    config: SlackConfig,
    title: str,
    message: str,
    attach_img: AttachImage | None,
    formatter: Callable[[str, str], FormattedMessage] = format_simple,
) -> None:
    title = "Error: " + title

    hist_add(message)

    interval_min = config.error.interval_min
    if my_lib.footprint.elapsed(NOTIFY_FOOTPRINT) <= interval_min * 60:
        logging.warning("Interval is too short. Skipping.")
        return

    thread_ts = split_send(
        config.bot_token, config.error.channel.name, title, message, formatter
    )

    if attach_img is not None:
        ch_id = config.error.channel.id
        if ch_id is None:
            raise ValueError("error channel id is not configured")

        upload_image(config.bot_token, ch_id, title, attach_img["data"], attach_img["text"], thread_ts)

    my_lib.footprint.update(NOTIFY_FOOTPRINT)


# NOTE: テスト用
def interval_clear() -> None:
    my_lib.footprint.clear(NOTIFY_FOOTPRINT)


# NOTE: テスト用
def hist_clear() -> None:
    hist_get(True).clear()
    hist_get(False).clear()


# NOTE: テスト用
def hist_add(message: str) -> None:
    hist_get(True).append(message)
    hist_get(False).append(message)


# NOTE: テスト用
def hist_get(is_thread_local: bool = True) -> list[str]:
    global thread_local
    global notify_hist
    global _hist_lock

    worker = os.environ.get("PYTEST_XDIST_WORKER", "0")

    if is_thread_local:
        # スレッドセーフな初期化（Double-checked locking パターン）
        if not hasattr(thread_local, "notify_hist"):
            with _hist_lock:
                if not hasattr(thread_local, "notify_hist"):
                    thread_local.notify_hist = collections.defaultdict(lambda: [])  # noqa: PIE807

        return thread_local.notify_hist[worker]
    else:
        return notify_hist[worker]


if __name__ == "__main__":
    # TEST Code
    import sys

    import docopt

    import my_lib.config
    import my_lib.logger

    args = docopt.docopt(__doc__)

    config_file = args["-c"]
    message = args["-m"]
    debug_mode = args["-D"]

    my_lib.logger.init("test", level=logging.DEBUG if debug_mode else logging.INFO)

    raw_config = my_lib.config.load(config_file)

    if "slack" not in raw_config:
        logging.warning("Slack の設定が記載されていません。")
        sys.exit(-1)

    slack_config = parse_slack_config(raw_config["slack"])

    info(slack_config, "Test", "This is test")
    error(slack_config, "Test", "This is test")
