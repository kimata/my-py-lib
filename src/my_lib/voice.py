#!/usr/bin/env python3
"""
VOICEVOX を WEB API 経由でたたいて，音声ファイルを生成します。

Usage:
  voice.py [-c CONFIG] [-m MESSAGE] [-s SPEAKER_ID] [-o WAV] [-D]

Options:
  -c CONFIG         : CONFIG を設定ファイルとして読み込んで実行します。[default: config.yaml]
  -m MESSAGE        : 音声化するメッセージ。[default: テストです]
  -s SPEAKER_ID     : スピーカ。[default: 3]
  -o WAV            : 書き出す音声ファイル。[default: text.wav]
  -D                : デバッグモードで動作します。
"""

import io
import json
import logging
import time
import urllib.request
import wave

import numpy as np
import scipy.signal
import simpleaudio


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


# MEMO: 一般的なサンプリングレートに変更
def convert_wav_data(wav_data_in):
    with wave.open(io.BytesIO(wav_data_in), "rb") as wav_in:
        n_channels = wav_in.getnchannels()
        sampwidth = wav_in.getsampwidth()
        framerate = wav_in.getframerate()
        n_frames = wav_in.getnframes()
        comptype = wav_in.getcomptype()
        compname = wav_in.getcompname()

        audio_data = wav_in.readframes(n_frames)

        if framerate != 44100:
            audio_data = np.frombuffer(audio_data, dtype=np.int16)
            resampled_data = scipy.signal.resample(audio_data, int(len(audio_data) * 44100 / framerate))
            audio_data = resampled_data.astype(np.int16).tobytes()

        if n_channels == 2:
            audio_data = np.frombuffer(audio_data, dtype=np.int16)
            resampled_data = audio_data[::2] // 2 + audio_data[1::2] // 2
            audio_data = resampled_data.astype(np.int16).tobytes()

        with io.BytesIO() as wav_data_out:
            with wave.open(wav_data_out, "wb") as wav_out:
                wav_out.setnchannels(1)
                wav_out.setsampwidth(sampwidth)
                wav_out.setframerate(44100)
                wav_out.setcomptype(comptype, compname)
                wav_out.writeframes(audio_data)

            return wav_data_out.getvalue()


def synthesize(config, text, volume=2, speaker_id=3):
    req = urllib.request.Request(get_query_url(config, text, speaker_id), method="POST")  # noqa: S310
    res = urllib.request.urlopen(req)  # noqa: S310
    query_json = json.loads(res.read().decode("utf-8"))
    query_json["volumeScale"] = volume
    query_json["speedScale"] = 0.9

    req = urllib.request.Request(  # noqa: S310
        get_synthesis_url(config, speaker_id), data=json.dumps(query_json).encode("utf-8"), method="POST"
    )
    req.add_header("Content-Type", "application/json")
    res = urllib.request.urlopen(req)  # noqa: S310

    return convert_wav_data(res.read())


def play(wav_data, duration_sec=None):
    if duration_sec is None:
        simpleaudio.WaveObject.from_wave_file(io.BytesIO(wav_data)).play().wait_done()
    else:
        simpleaudio.WaveObject.from_wave_file(io.BytesIO(wav_data)).play()
        time.sleep(duration_sec)


if __name__ == "__main__":
    # TEST Code
    import pathlib

    import docopt
    import my_lib.config
    import my_lib.logger

    args = docopt.docopt(__doc__)

    config_file = args["-c"]
    message = args["-m"]
    speaker_id = args["-s"]
    out_file = args["-o"]
    debug_mode = args["-D"]

    my_lib.logger.init("my-lib.config", level=logging.DEBUG if debug_mode else logging.INFO)

    config = my_lib.config.load(config_file)

    wav_data = synthesize(config, message, speaker_id)

    with pathlib.Path(out_file).open("wb") as f:
        f.write(wav_data)

    play(wav_data)
