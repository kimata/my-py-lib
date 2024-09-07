#!/usr/bin/env python3
import json
import logging
import pathlib
import tempfile

import my_lib.footprint
import slack_sdk

# NOTE: テスト用
notify_hist = []

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
        client.chat_postMessage(
            channel=ch_name,
            text=message["text"],
            blocks=message["json"],
        )
    except slack_sdk.errors.SlackClientError as e:
        logging.warning(e)


def split_send(token, ch_name, title, message, formatter=format_simple):
    LINE_SPLIT = 20

    logging.info("Post slack channel: %s", ch_name)

    message_lines = message.splitlines()
    for i in range(0, len(message_lines), LINE_SPLIT):
        send(
            token,
            ch_name,
            formatter(title, "\n".join(message_lines[i : i + LINE_SPLIT])),
        )


def info(token, ch_name, name, message, formatter=format_simple):
    title = "Info: " + name
    split_send(token, ch_name, title, message, formatter)


def error_img(token, ch_id, title, img, text):
    client = slack_sdk.WebClient(token=token)

    with tempfile.TemporaryDirectory() as dname:
        img_path = pathlib.Path(dname) / "error.png"
        img.save(img_path)

        try:
            logging.info(img_path)
            client.files_upload_v2(channel=ch_id, file=str(img_path), title=title, initial_comment=text)
        except slack_sdk.errors.SlackApiError as e:
            logging.warning(e.response["error"])


def error(  # noqa: PLR0913
    token,
    ch_name,
    name,
    message,
    interval_min=INTERVAL_MIN,
    formatter=format_simple,
):
    title = "Error: " + name

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
    name,
    message,
    attatch_img,
    interval_min=INTERVAL_MIN,
    formatter=format_simple,
):  # def error_with_image
    title = "Error: " + name

    hist_add(message)

    if my_lib.footprint.elapsed(NOTIFY_FOOTPRINT) <= interval_min * 60:
        logging.warning("Interval is too short. Skipping.")
        return

    split_send(token, ch_name, title, message, formatter)

    if attatch_img is not None:
        if ch_id is None:
            raise ValueError("ch_id is None")  # noqa: TRY003, EM101

        error_img(token, ch_id, title, attatch_img["data"], attatch_img["text"])

    my_lib.footprint.update(NOTIFY_FOOTPRINT)


# NOTE: テスト用
def interval_clear():
    my_lib.footprint.clear(NOTIFY_FOOTPRINT)


# NOTE: テスト用
def hist_clear():
    global notify_hist  # noqa: PLW0603

    notify_hist = []


# NOTE: テスト用
def hist_add(message):
    global notify_hist

    notify_hist.append(message)


# NOTE: テスト用
def hist_get():
    global notify_hist

    return notify_hist
