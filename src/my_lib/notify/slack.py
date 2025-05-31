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

import collections
import json
import logging
import math
import os
import pathlib
import tempfile
import threading
import time

import my_lib.footprint
import slack_sdk

# NOTE: テスト用
thread_local = threading.local()
notify_hist = collections.defaultdict(lambda: [])  # noqa: PIE807

NOTIFY_FOOTPRINT = pathlib.Path("/dev/shm/notify/slack/error")  # noqa: S108
INTERVAL_MIN = 60

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


def format_simple(title, message):
    return {
        "text": message,
        "json": json.loads(SIMPLE_TMPL.format(title=title, message=json.dumps(message))),
    }


def send(token, ch_name, message):
    try:
        client = slack_sdk.WebClient(token=token)

        return client.chat_postMessage(
            channel=ch_name,
            text=message["text"],
            blocks=message["json"],
        )
    except slack_sdk.errors.SlackClientError:
        logging.exception("Failed to send Slack message")


def split_send(token, ch_name, title, message, formatter=format_simple):
    LINE_SPLIT = 20

    logging.info("Post slack channel: %s", ch_name)

    message_lines = message.splitlines()
    total = math.ceil(len(message_lines) / LINE_SPLIT)
    for i in range(0, len(message_lines), LINE_SPLIT):
        split_title = title if total == 1 else f"{title} ({i + 1}/{total})"

        send(
            token,
            ch_name,
            formatter(split_title, "\n".join(message_lines[i : i + LINE_SPLIT])),
        )

        time.sleep(1)


def info(token, ch_name, title, message, formatter=format_simple):
    title = "Info: " + title
    split_send(token, ch_name, title, message, formatter)


def upload_image(token, ch_id, title, img, text):
    client = slack_sdk.WebClient(token=token)

    with tempfile.TemporaryDirectory() as dname:
        img_path = pathlib.Path(dname) / "image.png"
        img.save(img_path)

        try:
            resp = client.files_upload_v2(
                channel=ch_id, file=str(img_path), title=title, initial_comment=text
            )

            return resp["files"][0]["id"]
        except slack_sdk.errors.SlackApiError:
            logging.exception("Failed to sendo Slack message")

            return None


def error(  # noqa: PLR0913
    token,
    ch_name,
    title,
    message,
    interval_min=INTERVAL_MIN,
    formatter=format_simple,
):
    title = "Error: " + title

    hist_add(message)

    if my_lib.footprint.elapsed(NOTIFY_FOOTPRINT) <= interval_min * 60:
        logging.warning("Interval is too short. Skipping.")
        return

    split_send(token, ch_name, title, message, formatter)

    my_lib.footprint.update(NOTIFY_FOOTPRINT)


def error_with_image(  # noqa: PLR0913
    token,
    ch_name,
    ch_id,
    title,
    message,
    attatch_img,
    interval_min=INTERVAL_MIN,
    formatter=format_simple,
):  # def error_with_image
    title = "Error: " + title

    hist_add(message)

    if my_lib.footprint.elapsed(NOTIFY_FOOTPRINT) <= interval_min * 60:
        logging.warning("Interval is too short. Skipping.")
        return

    split_send(token, ch_name, title, message, formatter)

    if attatch_img is not None:
        if ch_id is None:
            raise ValueError("ch_id is None")  # noqa: TRY003, EM101

        upload_image(token, ch_id, title, attatch_img["data"], attatch_img["text"])

    my_lib.footprint.update(NOTIFY_FOOTPRINT)


# NOTE: テスト用
def interval_clear():
    my_lib.footprint.clear(NOTIFY_FOOTPRINT)


# NOTE: テスト用
def hist_clear():
    hist_get(True).clear()
    hist_get(False).clear()


# NOTE: テスト用
def hist_add(message):
    hist_get(True).append(message)
    hist_get(False).append(message)


# NOTE: テスト用
def hist_get(is_thread_local=True):
    global thread_local
    global notify_hist

    worker = os.environ.get("PYTEST_XDIST_WORKER", "0")

    if is_thread_local:
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

    config = my_lib.config.load(config_file)

    if "slack" not in config:
        logging.warning("Slack の設定が記載されていません。")
        sys.exit(-1)

    client = slack_sdk.WebClient(token=config["slack"]["bot_token"])

    if "info" in config["slack"]:
        info(
            config["slack"]["bot_token"],
            config["slack"]["info"]["channel"]["name"],
            "Test",
            "This is test",
        )

    if "error" in config["slack"]:
        error(
            config["slack"]["bot_token"],
            config["slack"]["error"]["channel"]["name"],
            "Test",
            "This is test",
        )
