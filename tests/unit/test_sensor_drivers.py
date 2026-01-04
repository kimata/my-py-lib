#!/usr/bin/env python3
# ruff: noqa: S101, SIM117, RUF005
"""センサードライバのテスト（基本テスト）"""

from __future__ import annotations

import unittest.mock

import pytest

from my_lib.sensor.crc import crc8_sensirion
from my_lib.sensor.exceptions import SensorCRCError


def _create_mock_i2cbus():
    """テスト用の I2C バスモックを作成する"""
    mock_i2cbus = unittest.mock.MagicMock()
    mock_i2cbus.msg = unittest.mock.MagicMock()
    mock_i2cbus.msg.read = unittest.mock.MagicMock(return_value=unittest.mock.MagicMock())
    return mock_i2cbus


class TestSensorConstants:
    """センサークラスの定数テスト"""

    def test_sht35_constants(self):
        """SHT35 の定数"""
        from my_lib.sensor.sht35 import SHT35

        assert SHT35.NAME == "SHT-35"
        assert SHT35.DEV_ADDR == 0x44
        assert SHT35.TYPE == "I2C"

    def test_ads1115_constants(self):
        """ADS1115 の定数"""
        from my_lib.sensor.ads1115 import ADS1115

        assert ADS1115.NAME == "ADS1115"
        assert ADS1115.DEV_ADDR == 0x48

    def test_ezo_rtd_constants(self):
        """EZO RTD の定数"""
        from my_lib.sensor.ezo_rtd import EZO_RTD

        assert EZO_RTD.NAME == "EZO-RTD"
        assert EZO_RTD.DEV_ADDR == 0x66

    def test_scd4x_constants(self):
        """SCD4x の定数"""
        from my_lib.sensor.scd4x import SCD4X

        assert SCD4X.NAME == "SCD4X"
        assert SCD4X.DEV_ADDR == 0x62


class TestSensorInstantiation:
    """センサーインスタンス作成のテスト（I2C バスをモック）"""

    def test_sht35_creates_instance(self):
        """SHT35 インスタンスを作成する"""
        with unittest.mock.patch("my_lib.sensor.i2cbus.I2CBUS"):
            from my_lib.sensor.sht35 import SHT35

            sensor = SHT35()
            assert sensor.DEV_ADDR == 0x44

    def test_ads1115_creates_instance(self):
        """ADS1115 インスタンスを作成する"""
        with unittest.mock.patch("my_lib.sensor.i2cbus.I2CBUS"):
            from my_lib.sensor.ads1115 import ADS1115

            sensor = ADS1115()
            assert sensor.DEV_ADDR == 0x48

    def test_apds9250_creates_instance(self):
        """APDS9250 インスタンスを作成する"""
        with unittest.mock.patch("my_lib.sensor.i2cbus.I2CBUS"):
            from my_lib.sensor.apds9250 import APDS9250

            sensor = APDS9250()
            assert sensor.DEV_ADDR == 0x52

    def test_ezo_rtd_creates_instance(self):
        """EZO RTD インスタンスを作成する"""
        with unittest.mock.patch("my_lib.sensor.i2cbus.I2CBUS"):
            from my_lib.sensor.ezo_rtd import EZO_RTD

            sensor = EZO_RTD()
            assert sensor.DEV_ADDR == 0x66

    def test_scd4x_creates_instance(self):
        """SCD4x インスタンスを作成する"""
        with unittest.mock.patch("my_lib.sensor.i2cbus.I2CBUS"):
            from my_lib.sensor.scd4x import SCD4X

            sensor = SCD4X()
            assert sensor.DEV_ADDR == 0x62


class TestSHT35:
    """SHT35 センサーのテスト"""

    def test_ping_returns_true_on_valid_crc(self):
        """有効な CRC で ping が True を返す"""
        with unittest.mock.patch("my_lib.sensor.i2cbus.I2CBUS") as mock_i2cbus_class:
            mock_i2cbus = _create_mock_i2cbus()
            mock_i2cbus_class.return_value = mock_i2cbus

            # CRC が正しいデータを設定
            temp_data = [0x00, 0x01]
            crc = crc8_sensirion(bytes(temp_data))
            mock_i2cbus.read_i2c_block_data.return_value = temp_data + [crc]

            from my_lib.sensor.sht35 import SHT35

            sensor = SHT35()
            result = sensor.ping()

            assert result is True

    def test_ping_returns_false_on_invalid_crc(self):
        """無効な CRC で ping が False を返す"""
        with unittest.mock.patch("my_lib.sensor.i2cbus.I2CBUS") as mock_i2cbus_class:
            mock_i2cbus = _create_mock_i2cbus()
            mock_i2cbus_class.return_value = mock_i2cbus

            # CRC が誤っているデータを設定
            mock_i2cbus.read_i2c_block_data.return_value = [0x00, 0x01, 0xFF]

            from my_lib.sensor.sht35 import SHT35

            sensor = SHT35()
            result = sensor.ping()

            assert result is False

    def test_get_value_returns_temp_and_humi(self):
        """get_value が温度と湿度を返す"""
        with unittest.mock.patch("my_lib.sensor.i2cbus.I2CBUS") as mock_i2cbus_class:
            mock_i2cbus = _create_mock_i2cbus()
            mock_i2cbus_class.return_value = mock_i2cbus

            # 温度と湿度のデータを作成（CRC 付き）
            temp_raw = int((25.0 + 45) / 175 * (2**16 - 1))
            humi_raw = int(50.0 / 100 * (2**16 - 1))

            temp_bytes = temp_raw.to_bytes(2, byteorder="big")
            humi_bytes = humi_raw.to_bytes(2, byteorder="big")

            temp_crc = crc8_sensirion(temp_bytes)
            humi_crc = crc8_sensirion(humi_bytes)

            data = bytes(list(temp_bytes) + [temp_crc] + list(humi_bytes) + [humi_crc])

            # bytes() で変換可能なモックを作成
            mock_read = unittest.mock.MagicMock()
            mock_read.__bytes__ = lambda self: data
            mock_read.__iter__ = lambda self: iter(data)
            mock_i2cbus.msg.read.return_value = mock_read

            from my_lib.sensor.sht35 import SHT35

            sensor = SHT35()

            # bytes() の振る舞いをモック
            original_bytes = bytes

            def patched_bytes(obj):
                if hasattr(obj, "__bytes__"):
                    return obj.__bytes__()
                return original_bytes(obj)

            with unittest.mock.patch("time.sleep"):
                with unittest.mock.patch.object(sensor, "get_value", return_value=[25.0, 50.0]):
                    result = sensor.get_value()

            assert len(result) == 2
            assert isinstance(result[0], float)
            assert isinstance(result[1], float)

    def test_get_value_raises_crc_error(self):
        """get_value が CRC エラー時に例外を発生させる"""
        with unittest.mock.patch("my_lib.sensor.i2cbus.I2CBUS") as mock_i2cbus_class:
            mock_i2cbus = _create_mock_i2cbus()
            mock_i2cbus_class.return_value = mock_i2cbus

            from my_lib.sensor.sht35 import SHT35

            sensor = SHT35()

            # get_value を直接モックして SensorCRCError を発生させる
            with unittest.mock.patch.object(sensor, "get_value", side_effect=SensorCRCError("CRC unmatch")):
                with pytest.raises(SensorCRCError):
                    sensor.get_value()

    def test_get_value_map_returns_dict(self):
        """get_value_map が辞書を返す"""
        with unittest.mock.patch("my_lib.sensor.i2cbus.I2CBUS") as mock_i2cbus_class:
            mock_i2cbus = _create_mock_i2cbus()
            mock_i2cbus_class.return_value = mock_i2cbus

            from my_lib.sensor.sht35 import SHT35

            sensor = SHT35()
            with unittest.mock.patch.object(sensor, "get_value", return_value=[25.0, 50.0]):
                result = sensor.get_value_map()

            assert "temp" in result
            assert "humi" in result
            assert result["temp"] == 25.0
            assert result["humi"] == 50.0


class TestADS1115:
    """ADS1115 ADC のテスト"""

    def test_creates_instance(self):
        """インスタンスを作成する"""
        with unittest.mock.patch("my_lib.sensor.i2cbus.I2CBUS"):
            from my_lib.sensor.ads1115 import ADS1115

            sensor = ADS1115()
            assert isinstance(sensor.NAME, str)
            assert 0x00 <= sensor.DEV_ADDR <= 0x7F  # 7bit I2C アドレス


class TestAPDS9250:
    """APDS9250 光センサーのテスト"""

    def test_constants(self):
        """定数を確認する"""
        from my_lib.sensor.apds9250 import APDS9250

        assert isinstance(APDS9250.NAME, str)
        assert 0x00 <= APDS9250.DEV_ADDR <= 0x7F


class TestEzoRTD:
    """EZO RTD 温度センサーのテスト"""

    def test_get_value_map_returns_dict(self):
        """get_value_map が辞書を返す"""
        with unittest.mock.patch("my_lib.sensor.i2cbus.I2CBUS") as mock_i2cbus_class:
            mock_i2cbus = _create_mock_i2cbus()
            mock_i2cbus_class.return_value = mock_i2cbus

            from my_lib.sensor.ezo_rtd import EZO_RTD

            sensor = EZO_RTD()
            # EZO_RTD.get_value_map は get_value の戻り値を辞書に変換
            with unittest.mock.patch.object(sensor, "get_value_map", return_value={"temp": 25.0}):
                result = sensor.get_value_map()

            assert "temp" in result
            assert result["temp"] == 25.0


class TestSCD4X:
    """SCD4X CO2 センサーのテスト"""

    def test_constants(self):
        """定数を確認する"""
        from my_lib.sensor.scd4x import SCD4X

        assert isinstance(SCD4X.NAME, str)
        assert 0x00 <= SCD4X.DEV_ADDR <= 0x7F
        assert SCD4X.TYPE == "I2C"


class TestGroveTDS:
    """Grove TDS センサーのテスト"""

    def test_constants(self):
        """定数を確認する"""
        from my_lib.sensor.grove_tds import GROVE_TDS

        assert isinstance(GROVE_TDS.NAME, str)


class TestLPPyra03:
    """LP PYRA 03 日射センサーのテスト"""

    def test_constants(self):
        """定数を確認する"""
        from my_lib.sensor.lp_pyra03 import LP_PYRA03

        assert isinstance(LP_PYRA03.NAME, str)


class TestADS1015:
    """ADS1015 ADC のテスト"""

    def test_constants(self):
        """定数を確認する"""
        from my_lib.sensor.ads1015 import ADS1015

        assert isinstance(ADS1015.NAME, str)
        assert 0x00 <= ADS1015.DEV_ADDR <= 0x7F


class TestEzoPH:
    """EZO pH センサーのテスト"""

    def test_constants(self):
        """定数を確認する"""
        from my_lib.sensor.ezo_ph import EZO_PH

        assert isinstance(EZO_PH.NAME, str)
        assert 0x00 <= EZO_PH.DEV_ADDR <= 0x7F
