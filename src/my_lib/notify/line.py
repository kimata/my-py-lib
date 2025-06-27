#!/usr/bin/env python3
"""
Line を使って通知を送ります。

Usage:
  line.py [-c CONFIG] [-D] [-m MESSAGE]

Options:
  -c CONFIG         : CONFIG を設定ファイルとして読み込んで実行します。[default: config.yaml]
  -m MESSAGE        : 送信するメッセージ。[default: TEST]
  -D                : デバッグモードで動作します。
"""

import collections
import logging
import os

import linebot.v3.messaging

# NOTE: テスト用
notify_hist = collections.defaultdict(lambda: [])  # noqa: PIE807


def get_msg_config(line_config):
    return linebot.v3.messaging.Configuration(
        host="https://api.line.me", access_token=line_config["channel"]["access_token"]
    )


def send_impl(line_config, message):
    hist_add(message.alt_text)

    msg_config = get_msg_config(line_config)

    with linebot.v3.messaging.ApiClient(msg_config) as client:
        api = linebot.v3.messaging.MessagingApi(client)
        try:
            api.broadcast(linebot.v3.messaging.BroadcastRequest(messages=[message]))
        except Exception:
            logging.exception("Failed to send message")


def send(line_config, message):
    send_impl(line_config, linebot.v3.messaging.TemplateMessage.from_dict(message))


def error(line_config, text):
    message = linebot.v3.messaging.FlexMessage.from_dict(
        {
            "type": "flex",
            "altText": f"ERROR: {text:.300}",
            "contents": {
                "type": "bubble",
                "body": {
                    "type": "box",
                    "layout": "vertical",
                    "contents": [
                        {
                            "type": "text",
                            "text": "ERROR",
                            "weight": "bold",
                            "color": "#FF3300",
                            "size": "sm",
                        },
                        {"type": "separator", "margin": "sm"},
                        {
                            "type": "box",
                            "layout": "horizontal",
                            "margin": "lg",
                            "contents": [
                                {
                                    "type": "text",
                                    "text": text,
                                    "size": "xs",
                                    "color": "#000000",
                                    "wrap": True,
                                    "flex": 0,
                                }
                            ],
                        },
                    ],
                },
                "styles": {"footer": {"separator": True}},
            },
        },
    )

    send_impl(line_config, message)


def info(line_config, text):
    message = linebot.v3.messaging.FlexMessage.from_dict(
        {
            "type": "flex",
            "altText": f"INFO: {text}",
            "contents": {
                "type": "bubble",
                "body": {
                    "type": "box",
                    "layout": "vertical",
                    "contents": [
                        {
                            "type": "text",
                            "text": "INFO",
                            "weight": "bold",
                            "color": "#1DB446",
                            "size": "sm",
                        },
                        {"type": "separator", "margin": "sm"},
                        {
                            "type": "box",
                            "layout": "horizontal",
                            "margin": "lg",
                            "contents": [
                                {
                                    "type": "text",
                                    "text": text,
                                    "size": "xs",
                                    "color": "#000000",
                                    "wrap": True,
                                    "flex": 0,
                                }
                            ],
                        },
                    ],
                },
                "styles": {"footer": {"separator": True}},
            },
        },
    )

    send_impl(line_config, message)


# NOTE: テスト用
def hist_clear():
    hist_get().clear()


# NOTE: テスト用
def hist_add(message):
    hist_get().append(message)


# NOTE: テスト用
def hist_get():
    global notify_hist

    worker = os.environ.get("PYTEST_XDIST_WORKER", "0")

    return notify_hist[worker]


if __name__ == "__main__":
    # TEST Code
    import docopt

    import my_lib.config
    import my_lib.logger

    args = docopt.docopt(__doc__)

    config_file = args["-c"]
    message = args["-m"]
    debug_mode = args["-D"]

    my_lib.logger.init("test", level=logging.DEBUG if debug_mode else logging.INFO)

    config = my_lib.config.load(config_file)

    rainfall_info = {
        "cloud_url": "https://www.jma.go.jp/bosai/nowc/#zoom:12/lat:35.671522/lon:139.774761/colordepth:normal/elements:hrpns&slmcs&slmcs_fcst",
        "cloud_image": "https://picsum.photos/200",  # Dummy
    }

    message = {
        "type": "template",
        "altText": "雨が降り始めました！",
        "template": {
            "type": "buttons",
            "thumbnailImageUrl": rainfall_info["cloud_image"],
            "imageAspectRatio": "rectangle",
            "imageSize": "cover",
            "imageBackgroundColor": "#FFFFFF",
            "title": "天気速報",
            "text": "雨が降り始めました！",
            "defaultAction": {"type": "uri", "label": "雨雲を見る", "uri": rainfall_info["cloud_url"]},
            "actions": [
                {"type": "uri", "label": "雨雲を見る", "uri": rainfall_info["cloud_url"]},
            ],
        },
    }

    send(config["notify"]["line"], message)
    error(config["notify"]["line"], "Test")
