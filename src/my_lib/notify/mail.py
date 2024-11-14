#!/usr/bin/env python3
"""
メールで通知を行います．

Usage:
  mail.py [-c CONFIG] [-d] [-m MESSAGE]

Options:
  -c CONFIG         : CONFIG を設定ファイルとして読み込んで実行します．[default: config.yaml]
  -m MESSAGE        : 送信するメッセージ．[default: TEST]
  -d                : デバッグモードで動作します．
"""

import email.mime.image
import email.mime.multipart
import email.mime.text
import logging
import pathlib
import smtplib

import my_lib.footprint

NOTIFY_FOOTPRINT = pathlib.Path("/dev/shm/notify/mail/send")  # noqa: S108
INTERVAL_MIN = 60


def send_impl(config, to, message, subject, png_data=None):
    smtp = smtplib.SMTP(config["mail"]["smtp"]["host"], config["mail"]["smtp"]["port"])
    smtp.starttls()
    smtp.login(config["mail"]["user"], config["mail"]["pass"])

    if subject is None:
        subject = config["mail"].get("subject", "Notify")

    msg = email.mime.multipart.MIMEMultipart()
    msg["Subject"] = subject
    msg["To"] = to
    msg["From"] = config["mail"]["from"]

    if png_data is not None:
        cid = "image"
        img = email.mime.image.MIMEImage(png_data, name="image.png")
        img.add_header("Content-ID", "<" + cid + ">")
        msg.attach(img)

        message += f'<br/><img src="cid:{cid}"/>'

    msg.attach(email.mime.text.MIMEText(message, "html"))

    smtp.send_message(msg)

    logging.info("Sent mail")

    smtp.quit()


def send(config, message, subject=None, png_data=None, is_log_message=True, interval_min=INTERVAL_MIN):  # noqa: PLR0913
    if is_log_message:
        logging.info("notify: %s", message)

    if my_lib.footprint.elapsed(NOTIFY_FOOTPRINT) <= interval_min * 60:
        logging.warning("Interval is too short. Skipping.")
        return

    to_list = []
    if type(config["mail"]["to"]) is list:
        to_list.extend(config["mail"]["to"])
    else:
        to_list.append(config["mail"]["to"])

    for to in to_list:
        send_impl(config, to, message, subject, png_data)

    my_lib.footprint.update(NOTIFY_FOOTPRINT)


if __name__ == "__main__":
    import docopt
    import my_lib.config
    import my_lib.logger

    args = docopt.docopt(__doc__)

    config_file = args["-c"]
    message = args["-m"]
    debug_mode = args["-d"]

    my_lib.logger.init("test", level=logging.DEBUG if debug_mode else logging.INFO)

    config = my_lib.config.load(config_file)

    send(config, message)
