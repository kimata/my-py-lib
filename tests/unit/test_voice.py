#!/usr/bin/env python3
# ruff: noqa: S101, SIM117
"""voice.py のテスト"""

from __future__ import annotations

import io
import unittest.mock
import wave

import pytest

np = pytest.importorskip("numpy")

import my_lib.voice  # noqa: E402


class TestGetQueryUrl:
    """get_query_url 関数のテスト"""

    def test_builds_url(self):
        """URLを構築する"""
        config = my_lib.voice.VoiceConfig.parse({"server": {"url": "http://localhost:50021"}})

        result = my_lib.voice.get_query_url(config, "テスト", 1)

        assert "audio_query" in result
        assert "text=" in result
        assert "speaker=1" in result

    def test_encodes_text(self):
        """テキストをエンコードする"""
        config = my_lib.voice.VoiceConfig.parse({"server": {"url": "http://localhost:50021"}})

        result = my_lib.voice.get_query_url(config, "こんにちは", 1)

        assert "%E3%81%93%E3%82%93%E3%81%AB%E3%81%A1%E3%81%AF" in result or "こんにちは" not in result


class TestGetSynthesisUrl:
    """get_synthesis_url 関数のテスト"""

    def test_builds_url(self):
        """URLを構築する"""
        config = my_lib.voice.VoiceConfig.parse({"server": {"url": "http://localhost:50021"}})

        result = my_lib.voice.get_synthesis_url(config, 3)

        assert "synthesis" in result
        assert "speaker=3" in result


class TestConvertWavData:
    """convert_wav_data 関数のテスト"""

    def _create_wav_bytes(self, framerate=24000, channels=1, sampwidth=2, duration_ms=100):
        """テスト用の WAV データを作成する"""
        buf = io.BytesIO()

        n_frames = int(framerate * duration_ms / 1000)
        t = np.linspace(0, duration_ms / 1000, n_frames)
        audio = (np.sin(2 * np.pi * 440 * t) * 32767).astype(np.int16)

        if channels == 2:
            audio = np.column_stack((audio, audio)).flatten()

        with wave.open(buf, "wb") as wav:
            wav.setnchannels(channels)
            wav.setsampwidth(sampwidth)
            wav.setframerate(framerate)
            wav.writeframes(audio.tobytes())

        return buf.getvalue()

    def test_converts_mono_wav(self):
        """モノラル WAV を変換する"""
        wav_data = self._create_wav_bytes(framerate=24000, channels=1)

        result = my_lib.voice.convert_wav_data(wav_data)

        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_converts_stereo_to_mono(self):
        """ステレオをモノラルに変換する"""
        wav_data = self._create_wav_bytes(framerate=24000, channels=2)

        result = my_lib.voice.convert_wav_data(wav_data)

        with wave.open(io.BytesIO(result), "rb") as wav:
            assert wav.getnchannels() == 1

    def test_resamples_to_44100(self):
        """44100Hz にリサンプリングする"""
        wav_data = self._create_wav_bytes(framerate=24000, channels=1)

        result = my_lib.voice.convert_wav_data(wav_data)

        with wave.open(io.BytesIO(result), "rb") as wav:
            assert wav.getframerate() == 44100

    def test_handles_44100_input(self):
        """44100Hz の入力をそのまま処理する"""
        wav_data = self._create_wav_bytes(framerate=44100, channels=1)

        result = my_lib.voice.convert_wav_data(wav_data)

        with wave.open(io.BytesIO(result), "rb") as wav:
            assert wav.getframerate() == 44100

    def test_handles_unsupported_sampwidth(self):
        """サポートされていないサンプル幅を処理する"""
        buf = io.BytesIO()

        with wave.open(buf, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(3)
            wav.setframerate(24000)
            audio = np.zeros(100, dtype=np.int32)
            audio_bytes = audio.view(np.uint8).reshape(-1, 4)[:, :3].tobytes()
            wav.writeframes(audio_bytes)

        wav_data = buf.getvalue()

        result = my_lib.voice.convert_wav_data(wav_data)
        assert isinstance(result, bytes)


class TestSynthesize:
    """synthesize 関数のテスト"""

    def _create_mock_wav(self) -> bytes:
        """モック用の WAV データを作成する"""
        buf = io.BytesIO()
        n_frames = 4410  # 0.1秒分
        audio = (np.sin(2 * np.pi * 440 * np.linspace(0, 0.1, n_frames)) * 32767).astype(np.int16)
        with wave.open(buf, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(44100)
            wav.writeframes(audio.tobytes())
        return buf.getvalue()

    def test_raises_for_empty_text(self):
        """空のテキストでエラーを発生させる"""
        config = my_lib.voice.VoiceConfig.parse({"server": {"url": "http://localhost:50021"}})

        with pytest.raises(ValueError, match="Text must be a non-empty string"):
            my_lib.voice.synthesize(config, "")

    def test_raises_for_whitespace_only_text(self):
        """空白のみのテキストでエラーを発生させる"""
        config = my_lib.voice.VoiceConfig.parse({"server": {"url": "http://localhost:50021"}})

        with pytest.raises(ValueError, match="Text must be a non-empty string"):
            my_lib.voice.synthesize(config, "   ")

    def test_raises_for_negative_speaker_id(self):
        """負のスピーカー ID でエラーを発生させる"""
        config = my_lib.voice.VoiceConfig.parse({"server": {"url": "http://localhost:50021"}})

        with pytest.raises(ValueError, match="Speaker ID must be a non-negative integer"):
            my_lib.voice.synthesize(config, "test", speaker_id=-1)

    def test_raises_for_negative_volume(self):
        """負の音量でエラーを発生させる"""
        config = my_lib.voice.VoiceConfig.parse({"server": {"url": "http://localhost:50021"}})

        with pytest.raises(ValueError, match="Volume must be a non-negative number"):
            my_lib.voice.synthesize(config, "test", volume=-1)

    def test_raises_for_invalid_url(self):
        """無効な URL でエラーを発生させる"""
        config = my_lib.voice.VoiceConfig.parse({"server": {"url": "invalid_url"}})

        with pytest.raises(ValueError, match="Invalid server URL"):
            my_lib.voice.synthesize(config, "test")

    def test_synthesizes_audio(self):
        """音声を合成する"""
        config = my_lib.voice.VoiceConfig.parse({"server": {"url": "http://localhost:50021"}})

        mock_query_response = io.BytesIO(b'{"volumeScale": 1.0, "speedScale": 1.0}')
        mock_wav_data = self._create_mock_wav()
        mock_synthesis_response = io.BytesIO(mock_wav_data)

        with unittest.mock.patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = [mock_query_response, mock_synthesis_response]

            result = my_lib.voice.synthesize(config, "テスト", speaker_id=3, volume=2)

            assert isinstance(result, bytes)
            assert len(result) > 0

    def test_raises_runtime_error_on_url_error(self):
        """URL エラー時に RuntimeError を発生させる"""
        import urllib.error

        config = my_lib.voice.VoiceConfig.parse({"server": {"url": "http://localhost:50021"}})

        with unittest.mock.patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = urllib.error.URLError("Connection refused")

            with pytest.raises(RuntimeError, match="Failed to communicate"):
                my_lib.voice.synthesize(config, "テスト")

    def test_raises_runtime_error_on_invalid_json(self):
        """無効な JSON 応答時に RuntimeError を発生させる"""
        config = my_lib.voice.VoiceConfig.parse({"server": {"url": "http://localhost:50021"}})

        mock_response = io.BytesIO(b"not valid json")

        with unittest.mock.patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value = mock_response

            with pytest.raises(RuntimeError, match="Invalid response"):
                my_lib.voice.synthesize(config, "テスト")


class TestPlay:
    """play 関数のテスト"""

    def _create_mock_wav(self, framerate=44100, channels=1) -> bytes:
        """モック用の WAV データを作成する"""
        buf = io.BytesIO()
        n_frames = int(framerate * 0.1)  # 0.1秒分
        audio = (np.sin(2 * np.pi * 440 * np.linspace(0, 0.1, n_frames)) * 32767).astype(np.int16)
        if channels == 2:
            audio = np.column_stack((audio, audio)).flatten()
        with wave.open(buf, "wb") as wav:
            wav.setnchannels(channels)
            wav.setsampwidth(2)
            wav.setframerate(framerate)
            wav.writeframes(audio.tobytes())
        return buf.getvalue()

    def test_plays_audio(self):
        """音声を再生する"""
        wav_data = self._create_mock_wav()

        mock_stream = unittest.mock.MagicMock()
        mock_pyaudio = unittest.mock.MagicMock()
        mock_pyaudio.open.return_value = mock_stream

        with unittest.mock.patch("pyaudio.PyAudio", return_value=mock_pyaudio):
            my_lib.voice.play(wav_data)

            mock_pyaudio.open.assert_called_once()
            mock_stream.stop_stream.assert_called_once()
            mock_stream.close.assert_called_once()
            mock_pyaudio.terminate.assert_called_once()

    def test_converts_non_standard_wav(self):
        """非標準の WAV を変換して再生する"""
        # 24000Hz stereo WAV
        wav_data = self._create_mock_wav(framerate=24000, channels=2)

        mock_stream = unittest.mock.MagicMock()
        mock_pyaudio = unittest.mock.MagicMock()
        mock_pyaudio.open.return_value = mock_stream

        with unittest.mock.patch("pyaudio.PyAudio", return_value=mock_pyaudio):
            my_lib.voice.play(wav_data)

            mock_pyaudio.open.assert_called_once()

    def test_respects_duration_limit(self):
        """再生時間の制限を尊重する"""
        wav_data = self._create_mock_wav()

        mock_stream = unittest.mock.MagicMock()
        mock_pyaudio = unittest.mock.MagicMock()
        mock_pyaudio.open.return_value = mock_stream

        with unittest.mock.patch("pyaudio.PyAudio", return_value=mock_pyaudio):
            with unittest.mock.patch("time.time") as mock_time:
                # 最初の呼び出しで0を返し、次の呼び出しで0.5を返す
                mock_time.side_effect = [0.0, 0.5]

                my_lib.voice.play(wav_data, duration_sec=0.1)

                mock_stream.stop_stream.assert_called_once()
                mock_stream.close.assert_called_once()

    def test_handles_int8_format(self):
        """int8 フォーマットを処理する"""
        buf = io.BytesIO()
        audio = (np.sin(2 * np.pi * 440 * np.linspace(0, 0.1, 4410)) * 127).astype(np.int8)
        with wave.open(buf, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(1)
            wav.setframerate(44100)
            wav.writeframes(audio.tobytes())
        wav_data = buf.getvalue()

        mock_stream = unittest.mock.MagicMock()
        mock_pyaudio = unittest.mock.MagicMock()
        mock_pyaudio.open.return_value = mock_stream

        with unittest.mock.patch("pyaudio.PyAudio", return_value=mock_pyaudio):
            my_lib.voice.play(wav_data)

            mock_pyaudio.open.assert_called_once()
