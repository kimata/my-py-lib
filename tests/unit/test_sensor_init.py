#!/usr/bin/env python3
# ruff: noqa: S101
"""sensor/__init__.py のテスト"""

from __future__ import annotations

import unittest.mock

import pytest


class MockSensor:
    """テスト用のモックセンサー"""

    def __init__(self, name: str = "MockSensor", sensor_type: str = "I2C", dev_addr: int = 0x42):
        self.NAME = name
        self.TYPE = sensor_type
        self.dev_addr = dev_addr
        self.required = False
        self.consecutive_fails = 0
        self._ping_result = True
        self._values: dict[str, float] = {}

    def ping(self) -> bool:
        return self._ping_result

    def get_value_map(self) -> dict[str, float]:
        return self._values


@pytest.fixture
def mock_smbus():
    """smbus2 をモックする"""
    mock = unittest.mock.MagicMock()
    with unittest.mock.patch.dict("sys.modules", {"smbus2": mock}):
        yield mock


class TestSensorInfo:
    """sensor_info 関数のテスト"""

    def test_i2c_sensor_info(self, mock_smbus):
        """I2C センサーの情報を返す"""
        from my_lib.sensor import sensor_info

        sensor = MockSensor(name="SHT35", sensor_type="I2C", dev_addr=0x44)
        info = sensor_info(sensor)

        assert info == "SHT35 (I2C: 0x44)"

    def test_non_i2c_sensor_info(self, mock_smbus):
        """非 I2C センサーの情報を返す"""
        from my_lib.sensor import sensor_info

        sensor = MockSensor(name="RG-15", sensor_type="UART", dev_addr=0x00)
        info = sensor_info(sensor)

        assert info == "RG-15 (UART)"


class TestPing:
    """ping 関数のテスト"""

    def test_returns_active_sensors(self, mock_smbus):
        """応答があるセンサーは active に、応答がないセンサーは inactive に分類される"""
        from my_lib.sensor import ping

        sensor1 = MockSensor(name="Sensor1")
        sensor1._ping_result = True
        sensor2 = MockSensor(name="Sensor2")
        sensor2._ping_result = True

        active, inactive = ping([sensor1, sensor2])

        assert len(active) == 2
        assert sensor1 in active
        assert sensor2 in active
        assert inactive == []

    def test_filters_inactive_sensors(self, mock_smbus):
        """応答がないセンサーは inactive リストに入る"""
        from my_lib.sensor import ping

        sensor1 = MockSensor(name="Sensor1")
        sensor1._ping_result = True
        sensor2 = MockSensor(name="Sensor2")
        sensor2._ping_result = False

        active, inactive = ping([sensor1, sensor2])

        assert active == [sensor1]
        assert inactive == [sensor2]

    def test_raises_for_required_missing_sensor(self, mock_smbus):
        """必須センサーが見つからない場合は例外を発生"""
        from my_lib.sensor import ping

        sensor = MockSensor(name="RequiredSensor")
        sensor._ping_result = False
        sensor.required = True

        with pytest.raises(RuntimeError, match="必須センサー"):
            ping([sensor])

    def test_empty_list_returns_empty(self, mock_smbus):
        """空のリストを渡すと空のタプルを返す"""
        from my_lib.sensor import ping

        active, inactive = ping([])

        assert active == []
        assert inactive == []


class TestRetryInactive:
    """retry_inactive 関数のテスト"""

    def test_empty_inactive_returns_zero(self, mock_smbus):
        """inactive が空なら 0 を返して何もしない"""
        from my_lib.sensor import retry_inactive

        active: list = []
        inactive: list = []

        next_index = retry_inactive(active, inactive, 5)

        assert next_index == 0
        assert active == []
        assert inactive == []

    def test_promotes_sensor_when_ping_succeeds(self, mock_smbus):
        """ping 成功時は sensor を active に移す"""
        from my_lib.sensor import retry_inactive

        sensor1 = MockSensor(name="Sensor1")
        sensor1._ping_result = True
        sensor2 = MockSensor(name="Sensor2")
        sensor2._ping_result = False

        active: list = []
        inactive = [sensor1, sensor2]

        next_index = retry_inactive(active, inactive, 0)

        assert active == [sensor1]
        assert inactive == [sensor2]
        # NOTE: リストが縮んだので次回は同じ index から
        assert next_index == 0

    def test_keeps_inactive_when_ping_fails(self, mock_smbus):
        """ping 失敗時は inactive に残し、index を進める"""
        from my_lib.sensor import retry_inactive

        sensor1 = MockSensor(name="Sensor1")
        sensor1._ping_result = False
        sensor2 = MockSensor(name="Sensor2")
        sensor2._ping_result = False

        active: list = []
        inactive = [sensor1, sensor2]

        next_index = retry_inactive(active, inactive, 0)

        assert active == []
        assert inactive == [sensor1, sensor2]
        assert next_index == 1

    def test_index_wraps_around(self, mock_smbus):
        """index が範囲外なら先頭に巻き戻す"""
        from my_lib.sensor import retry_inactive

        sensor1 = MockSensor(name="Sensor1")
        sensor1._ping_result = False
        sensor2 = MockSensor(name="Sensor2")
        sensor2._ping_result = False

        active: list = []
        inactive = [sensor1, sensor2]

        next_index = retry_inactive(active, inactive, 5)

        # NOTE: 5 % 2 = 1 の sensor2 を ping、失敗で次は 2
        assert active == []
        assert inactive == [sensor1, sensor2]
        assert next_index == 2

    def test_resets_consecutive_fails_on_recovery(self, mock_smbus):
        """復帰したセンサーの consecutive_fails を 0 にリセットする"""
        from my_lib.sensor import retry_inactive

        sensor = MockSensor(name="Sensor")
        sensor._ping_result = True
        sensor.consecutive_fails = 3

        active: list = []
        inactive = [sensor]

        retry_inactive(active, inactive, 0)

        assert active == [sensor]
        assert sensor.consecutive_fails == 0

    def test_round_robin_sequence(self, mock_smbus):
        """複数回呼び出しでラウンドロビンする"""
        from my_lib.sensor import retry_inactive

        sensor1 = MockSensor(name="Sensor1")
        sensor1._ping_result = False
        sensor2 = MockSensor(name="Sensor2")
        sensor2._ping_result = False
        sensor3 = MockSensor(name="Sensor3")
        sensor3._ping_result = False

        active: list = []
        inactive = [sensor1, sensor2, sensor3]

        ping_order = []
        original_ping1 = sensor1.ping
        original_ping2 = sensor2.ping
        original_ping3 = sensor3.ping

        def make_tracker(name, original):
            def tracker():
                ping_order.append(name)
                return original()

            return tracker

        sensor1.ping = make_tracker("Sensor1", original_ping1)  # type: ignore
        sensor2.ping = make_tracker("Sensor2", original_ping2)  # type: ignore
        sensor3.ping = make_tracker("Sensor3", original_ping3)  # type: ignore

        idx = 0
        for _ in range(5):
            idx = retry_inactive(active, inactive, idx)

        assert ping_order == ["Sensor1", "Sensor2", "Sensor3", "Sensor1", "Sensor2"]


class TestSense:
    """sense 関数のテスト"""

    def test_collects_values_from_sensors(self, mock_smbus):
        """センサーから値を収集する"""
        from my_lib.sensor import sense

        sensor1 = MockSensor(name="Sensor1")
        sensor1._values = {"temp": 25.0}
        sensor2 = MockSensor(name="Sensor2")
        sensor2._values = {"humidity": 60.0}

        value_map, is_success, failed = sense([sensor1, sensor2])

        assert value_map == {"temp": 25.0, "humidity": 60.0}
        assert is_success is True
        assert failed == []

    def test_returns_false_on_exception(self, mock_smbus):
        """例外が発生した場合は is_success が False"""
        from my_lib.sensor import sense

        sensor = MockSensor(name="FailingSensor")

        def raise_error():
            raise OSError("Sensor error")

        sensor.get_value_map = raise_error  # type: ignore

        _, is_success, _ = sense([sensor])

        assert is_success is False

    def test_continues_after_exception(self, mock_smbus):
        """例外が発生しても他のセンサーの値を収集する"""
        from my_lib.sensor import sense

        sensor1 = MockSensor(name="FailingSensor")

        def raise_error():
            raise OSError("Sensor error")

        sensor1.get_value_map = raise_error  # type: ignore

        sensor2 = MockSensor(name="WorkingSensor")
        sensor2._values = {"temp": 25.0}

        value_map, is_success, _ = sense([sensor1, sensor2])

        assert value_map == {"temp": 25.0}
        assert is_success is False

    def test_empty_list_returns_empty(self, mock_smbus):
        """空のリストを渡すと空の値マップを返す"""
        from my_lib.sensor import sense

        value_map, is_success, failed = sense([])

        assert value_map == {}
        assert is_success is True
        assert failed == []

    def test_resets_counter_on_success(self, mock_smbus):
        """成功時は consecutive_fails を 0 にリセットする"""
        from my_lib.sensor import sense

        sensor = MockSensor(name="Sensor")
        sensor._values = {"temp": 25.0}
        sensor.consecutive_fails = 5

        sense([sensor])

        assert sensor.consecutive_fails == 0

    def test_increments_counter_on_failure(self, mock_smbus):
        """失敗時は consecutive_fails を増やす"""
        from my_lib.sensor import sense

        sensor = MockSensor(name="FailingSensor")
        sensor.get_value_map = unittest.mock.MagicMock(side_effect=OSError)

        sense([sensor])

        assert sensor.consecutive_fails == 1

    def test_emits_failed_sensor_only_when_threshold_reached(self, mock_smbus):
        """連続失敗回数が threshold に到達した瞬間のみ failed_sensor を返す"""
        from my_lib.sensor import sense

        sensor = MockSensor(name="FailingSensor")
        sensor.get_value_map = unittest.mock.MagicMock(side_effect=OSError("boom"))

        active = [sensor]

        # 1 回目: まだ threshold に達していないので failed は空
        _, _, failed1 = sense(active, fail_threshold=2)
        assert sensor.consecutive_fails == 1
        assert failed1 == []
        # センサーは active に残る
        assert active == [sensor]

        # 2 回目: ちょうど threshold に到達 → 通知用に返る
        _, _, failed2 = sense(active, fail_threshold=2)
        assert sensor.consecutive_fails == 2
        assert len(failed2) == 1
        assert failed2[0].sensor is sensor
        assert "boom" in failed2[0].traceback
        # 降格はしない
        assert active == [sensor]

        # 3 回目以降: 連続失敗は続くが再通知しない
        _, _, failed3 = sense(active, fail_threshold=2)
        assert sensor.consecutive_fails == 3
        assert failed3 == []
        _, _, failed4 = sense(active, fail_threshold=2)
        assert sensor.consecutive_fails == 4
        assert failed4 == []

    def test_re_emits_after_recovery_and_fail_again(self, mock_smbus):
        """一度成功で counter リセット後、再度 2 連続失敗したら再通知する"""
        from my_lib.sensor import sense

        sensor = MockSensor(name="FailingSensor")

        # 2 連続失敗 → 通知
        sensor.get_value_map = unittest.mock.MagicMock(side_effect=OSError("first"))
        sense([sensor])
        _, _, failed_first = sense([sensor])
        assert len(failed_first) == 1

        # 成功 → counter リセット
        sensor.get_value_map = unittest.mock.MagicMock(return_value={"temp": 1.0})
        sense([sensor])
        assert sensor.consecutive_fails == 0

        # 再度 2 連続失敗 → 再通知
        sensor.get_value_map = unittest.mock.MagicMock(side_effect=OSError("second"))
        sense([sensor])
        _, _, failed_second = sense([sensor])
        assert len(failed_second) == 1
        assert "second" in failed_second[0].traceback


class TestLoad:
    """load 関数のテスト"""

    @pytest.fixture
    def mock_sensor_module(self, mock_smbus):
        """my_lib.sensor モジュールをモックする"""
        mock_sensor_class = unittest.mock.MagicMock()
        mock_sensor_instance = MockSensor()
        mock_sensor_class.return_value = mock_sensor_instance

        with unittest.mock.patch("my_lib.sensor.my_lib.sensor") as mock_module:
            mock_module.sht35 = mock_sensor_class

            mock_i2cbus = unittest.mock.MagicMock()
            mock_i2cbus.I2CBUS.ARM = 0x1
            mock_module.i2cbus = mock_i2cbus

            yield mock_module, mock_sensor_class, mock_sensor_instance

    def test_loads_i2c_sensor(self, mock_sensor_module):
        """I2C センサーをロードする"""
        from my_lib.sensor import load

        mock_module, mock_sensor_class, mock_sensor_instance = mock_sensor_module

        sensor_def_list = [
            {"name": "sht35"},
        ]

        result = load(sensor_def_list)

        assert len(result) == 1

    def test_sets_required_flag(self, mock_sensor_module):
        """required フラグを設定する"""
        from my_lib.sensor import load

        mock_module, mock_sensor_class, mock_sensor_instance = mock_sensor_module

        sensor_def_list = [
            {"name": "sht35", "required": True},
        ]

        result = load(sensor_def_list)

        assert result[0].required is True
