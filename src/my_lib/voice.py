#!/usr/bin/env python3
"""
VOICEVOX を WEB API 経由でたたいて，音声ファイルを生成します．

Usage:
  voice.py [-c CONFIG] [-m MESSAGE] [-s SPEAKER_ID] [-d] [-o WAV]

Options:
  -c CONFIG         : CONFIG を設定ファイルとして読み込んで実行します．[default: config.yaml]
  -m MESSAGE        : 音声化するメッセージ．[default: テストです]
  -s SPEAKER_ID     : スピーカ．[default: 3]
  -d                : デバッグモードで動作します．
  -o WAV            : 書き出す音声ファイル．[default: text.wav]
"""

import logging
import urllib.request


def get_query_url(config, text, speaker_id):
    return urllib.parse.urlunparse(
        urllib.parse.urlparse(
            urllib.parse.urljoin(config["voice"]["server"]["url"], "/audio_query")
        )._replace(query=urllib.parse.urlencode({"text": text, "speaker": speaker_id}))
    )


def get_synthesis_url(config, speaker_id):
    return urllib.parse.urlunparse(
        urllib.parse.urlparse(urllib.parse.urljoin(config["voice"]["server"]["url"], "/synthesis"))._replace(
            query=urllib.parse.urlencode({"speaker": speaker_id})
        )
    )


def synthesize(config, text, speaker_id=3):
    req = urllib.request.Request(get_query_url(config, text, speaker_id), method="POST")  # noqa: S310
    res = urllib.request.urlopen(req)  # noqa: S310
    query_json = res.read()

    req = urllib.request.Request(get_synthesis_url(config, speaker_id), data=query_json, method="POST")  # noqa: S310
    req.add_header("Content-Type", "application/json")
    res = urllib.request.urlopen(req)  # noqa: S310

    return res.read()


if __name__ == "__main__":
    import pathlib

    import docopt
    import my_lib.config
    import my_lib.logger

    args = docopt.docopt(__doc__)

    config_file = args["-c"]
    message = args["-m"]
    speaker_id = args["-s"]
    debug_mode = args["-d"]
    out_file = args["-o"]

    my_lib.logger.init("my-lib.config", level=logging.DEBUG if debug_mode else logging.INFO)

    config = my_lib.config.load(config_file)

    wav_data = synthesize(config, message, speaker_id)
    with pathlib.Path.open(out_file, "wb") as f:
        f.write(wav_data)
