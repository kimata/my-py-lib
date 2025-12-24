#!/usr/bin/env python3
"""
VOICEVOX を WEB API 経由でたたいて、音声ファイルを生成します。

Usage:
  voice.py [-c CONFIG] [-m MESSAGE] [-s SPEAKER_ID] [-o WAV] [-D]

Options:
  -c CONFIG         : CONFIG を設定ファイルとして読み込んで実行します。[default: tests/data/config.example.yaml]
  -m MESSAGE        : 音声化するメッセージ。[default: テストです]
  -s SPEAKER_ID     : スピーカ。[default: 3]
  -o WAV            : 書き出す音声ファイル。[default: text.wav]
  -D                : デバッグモードで動作します。
"""

from __future__ import annotations

import io
import json
import logging
import time
import urllib.parse
import urllib.request
import wave
from typing import Any

import numpy as np
import pyaudio
import scipy.signal


def get_query_url(config: dict[str, Any], text: str, speaker_id: int) -> str:
    return urllib.parse.urlunparse(
        urllib.parse.urlparse(
            urllib.parse.urljoin(config["voice"]["server"]["url"], "/audio_query")
        )._replace(query=urllib.parse.urlencode({"text": text, "speaker": speaker_id}))
    )


def get_synthesis_url(config: dict[str, Any], speaker_id: int) -> str:
    return urllib.parse.urlunparse(
        urllib.parse.urlparse(urllib.parse.urljoin(config["voice"]["server"]["url"], "/synthesis"))._replace(
            query=urllib.parse.urlencode({"speaker": speaker_id})
        )
    )


# MEMO: 一般的なサンプリングレートに変更
def convert_wav_data(wav_data_in: bytes) -> bytes:
    with wave.open(io.BytesIO(wav_data_in), "rb") as wav_in:
        n_channels = wav_in.getnchannels()
        sampwidth = wav_in.getsampwidth()
        framerate = wav_in.getframerate()
        n_frames = wav_in.getnframes()
        audio_data = wav_in.readframes(n_frames)

    # WAV の sample dtype を推定
    dtype_map: dict[int, type[np.signedinteger[Any]]] = {1: np.int8, 2: np.int16, 4: np.int32}
    if sampwidth not in dtype_map:
        logging.error("Unsupported sampwidth: %d, defaulting to int16", sampwidth)
        sampwidth = 2  # Default to 16-bit
    dtype = dtype_map[sampwidth]
    audio: np.ndarray[Any, np.dtype[Any]] = np.frombuffer(audio_data, dtype=dtype)

    # ステレオ → モノラル（加算ではなく平均にする）
    if n_channels == 2:
        audio = audio.reshape(-1, 2)
        audio = audio.mean(axis=1)
        # 平均後に適切な範囲にクリッピングしてから型変換
        if dtype == np.int16:
            audio = np.clip(audio, -32768, 32767).astype(dtype)
        elif dtype == np.int8:
            audio = np.clip(audio, -128, 127).astype(dtype)
        elif dtype == np.int32:
            audio = np.clip(audio, -2147483648, 2147483647).astype(dtype)
        else:
            logging.warning("Unexpected datatype: %s", np.dtype(dtype).name)

    # リサンプリング
    if framerate != 44100:
        num_samples = int(len(audio) * 44100 / framerate)
        audio_resampled = scipy.signal.resample(audio, num_samples)
        # リサンプリング後に適切な範囲にクリッピングしてから型変換
        if dtype == np.int16:
            audio = np.clip(audio_resampled, -32768, 32767).astype(dtype)
        elif dtype == np.int8:
            audio = np.clip(audio_resampled, -128, 127).astype(dtype)
        elif dtype == np.int32:
            audio = np.clip(audio_resampled, -2147483648, 2147483647).astype(dtype)
        else:
            logging.warning("Unexpected datatype: %s", np.dtype(dtype).name)

    # 書き出し
    out_buf = io.BytesIO()
    with wave.open(out_buf, "wb") as wav_out:
        wav_out.setnchannels(1)
        wav_out.setsampwidth(sampwidth)
        wav_out.setframerate(44100)
        wav_out.writeframes(audio.tobytes())

    return out_buf.getvalue()


def synthesize(
    config: dict[str, Any], text: str, speaker_id: int = 3, volume: int | float = 2
) -> bytes:
    if not isinstance(text, str) or len(text.strip()) == 0:
        raise ValueError("Text must be a non-empty string")
    if not isinstance(speaker_id, int) or speaker_id < 0:
        raise ValueError("Speaker ID must be a non-negative integer")
    if not isinstance(volume, (int, float)) or volume < 0:
        raise ValueError("Volume must be a non-negative number")

    server_url = config["voice"]["server"]["url"]
    parsed_url = urllib.parse.urlparse(server_url)
    if not parsed_url.scheme or not parsed_url.netloc:
        raise ValueError("Invalid server URL in configuration")

    try:
        query_url = get_query_url(config, text, speaker_id)
        req = urllib.request.Request(query_url, method="POST")  # noqa: S310

        with urllib.request.urlopen(req, timeout=30) as res:  # noqa: S310
            query_json: dict[str, Any] = json.loads(res.read().decode("utf-8"))

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
        raise RuntimeError(f"Failed to communicate with voice server: {e}") from e
    except (json.JSONDecodeError, KeyError) as e:
        raise RuntimeError(f"Invalid response from voice server: {e}") from e


def play(wav_data: bytes, duration_sec: float | None = None) -> None:
    # Check if data needs conversion (only convert if not already 44.1kHz mono)
    with wave.open(io.BytesIO(wav_data), "rb") as wav_check:
        needs_conversion = wav_check.getframerate() != 44100 or wav_check.getnchannels() != 1

    if needs_conversion:
        wav_data = convert_wav_data(wav_data)

    # PyAudio instance
    p = pyaudio.PyAudio()
    stream: pyaudio.Stream | None = None

    try:
        with wave.open(io.BytesIO(wav_data), "rb") as wav_file:
            # Get audio parameters (already standardized by convert_wav_data)
            channels = wav_file.getnchannels()
            framerate = wav_file.getframerate()
            sampwidth = wav_file.getsampwidth()

            # Get format from sample width
            audio_format_map: dict[int, int] = {1: pyaudio.paInt8, 2: pyaudio.paInt16, 4: pyaudio.paInt32}
            audio_format = audio_format_map.get(sampwidth, pyaudio.paInt16)

            # Open stream
            stream = p.open(
                format=audio_format, channels=channels, rate=framerate, output=True, frames_per_buffer=1024
            )

            # Play audio in chunks
            chunk_size = 1024
            start_time = time.time() if duration_sec else None

            while True:
                data = wav_file.readframes(chunk_size)
                if not data:
                    break

                # Check duration limit
                if duration_sec and start_time and (time.time() - start_time) >= duration_sec:
                    break

                stream.write(data)

    finally:
        # Clean up
        if stream:
            stream.stop_stream()
            stream.close()
        p.terminate()


if __name__ == "__main__":
    # TEST Code
    import pathlib

    import docopt

    import my_lib.config
    import my_lib.logger

    args = docopt.docopt(__doc__)

    config_file = args["-c"]
    message = args["-m"]
    speaker_id = int(args["-s"])
    out_file = args["-o"]
    debug_mode = args["-D"]

    my_lib.logger.init("my-lib.config", level=logging.DEBUG if debug_mode else logging.INFO)

    config = my_lib.config.load(config_file)

    wav_data = synthesize(config, message, speaker_id)

    with pathlib.Path(out_file).open("wb") as f:
        f.write(wav_data)

    play(wav_data)
