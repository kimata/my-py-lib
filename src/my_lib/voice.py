#!/usr/bin/env python3
"""
VOICEVOX を WEB API 経由でたたいて、音声ファイルを生成します。

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
import urllib.parse
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
        audio_data = wav_in.readframes(n_frames)

    # WAV の sample dtype を推定（ここでは 16bit 限定）
    dtype = {1: np.int8, 2: np.int16, 4: np.int32}[sampwidth]
    audio = np.frombuffer(audio_data, dtype=dtype)

    # ステレオ → モノラル（加算ではなく平均にする）
    if n_channels == 2:
        audio = audio.reshape(-1, 2)
        audio = audio.mean(axis=1).astype(dtype)

    # リサンプリング
    if framerate != 44100:
        num_samples = int(len(audio) * 44100 / framerate)
        audio = scipy.signal.resample(audio, num_samples).astype(dtype)

    # 書き出し
    out_buf = io.BytesIO()
    with wave.open(out_buf, "wb") as wav_out:
        wav_out.setnchannels(1)
        wav_out.setsampwidth(sampwidth)
        wav_out.setframerate(44100)
        wav_out.writeframes(audio.tobytes())

    return out_buf.getvalue()


def synthesize(config, text, volume=2, speaker_id=3):
    if not isinstance(text, str) or len(text.strip()) == 0:
        raise ValueError("Text must be a non-empty string")  # noqa: EM101, TRY003
    if not isinstance(speaker_id, int) or speaker_id < 0:
        raise ValueError("Speaker ID must be a non-negative integer")  # noqa: EM101, TRY003
    if not isinstance(volume, (int, float)) or volume < 0:
        raise ValueError("Volume must be a non-negative number")  # noqa: EM101, TRY003

    server_url = config["voice"]["server"]["url"]
    parsed_url = urllib.parse.urlparse(server_url)
    if not parsed_url.scheme or not parsed_url.netloc:
        raise ValueError("Invalid server URL in configuration")  # noqa: EM101, TRY003

    try:
        query_url = get_query_url(config, text, speaker_id)
        req = urllib.request.Request(query_url, method="POST")  # noqa: S310

        with urllib.request.urlopen(req, timeout=30) as res:  # noqa: S310
            query_json = json.loads(res.read().decode("utf-8"))

        query_json["volumeScale"] = volume
        query_json["speedScale"] = 0.9

        synthesis_url = get_synthesis_url(config, speaker_id)
        req = urllib.request.Request(  # noqa: S310
            synthesis_url, data=json.dumps(query_json).encode("utf-8"), method="POST"
        )
        req.add_header("Content-Type", "application/json")

        with urllib.request.urlopen(req, timeout=30) as res:  # noqa: S310
            return convert_wav_data(res.read())

    except (urllib.error.URLError, urllib.error.HTTPError) as e:
        raise RuntimeError(f"Failed to communicate with voice server: {e}") from e  # noqa: EM102, TRY003
    except (json.JSONDecodeError, KeyError) as e:
        raise RuntimeError(f"Invalid response from voice server: {e}") from e  # noqa: EM102, TRY003


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
