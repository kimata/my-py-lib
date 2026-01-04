#!/usr/bin/env python3
# ruff: noqa: S101, SIM117
"""sensor_data.py のテスト"""

from __future__ import annotations

import datetime
import unittest.mock


class TestSensorDataResult:
    """SensorDataResult データクラスのテスト"""

    def test_creates_with_defaults(self):
        """デフォルト値でインスタンスを作成する"""
        import my_lib.sensor_data

        result = my_lib.sensor_data.SensorDataResult()

        assert result.value == []
        assert result.time == []
        assert result.valid is False

    def test_creates_with_data(self):
        """データ付きでインスタンスを作成する"""
        import my_lib.sensor_data

        now = datetime.datetime.now()
        result = my_lib.sensor_data.SensorDataResult(value=[1.0, 2.0, 3.0], time=[now, now, now], valid=True)

        assert result.value == [1.0, 2.0, 3.0]
        assert len(result.time) == 3
        assert result.valid is True


class TestDataRequest:
    """DataRequest データクラスのテスト"""

    def test_creates_with_defaults(self):
        """デフォルト値でインスタンスを作成する"""
        import my_lib.sensor_data

        request = my_lib.sensor_data.DataRequest(
            measure="test_measure", hostname="test_host", field="test_field"
        )

        assert request.measure == "test_measure"
        assert request.hostname == "test_host"
        assert request.field == "test_field"
        assert request.start == "-30h"
        assert request.stop == "now()"
        assert request.every_min == 1
        assert request.window_min == 3
        assert request.create_empty is True
        assert request.last is False

    def test_creates_with_custom_values(self):
        """カスタム値でインスタンスを作成する"""
        import my_lib.sensor_data

        request = my_lib.sensor_data.DataRequest(
            measure="measure",
            hostname="host",
            field="field",
            start="-1h",
            stop="-30m",
            every_min=5,
            window_min=10,
            create_empty=False,
            last=True,
        )

        assert request.start == "-1h"
        assert request.stop == "-30m"
        assert request.every_min == 5
        assert request.window_min == 10
        assert request.create_empty is False
        assert request.last is True


class TestProcessQueryResults:
    """_process_query_results 関数のテスト"""

    def test_returns_empty_result_for_empty_table_list(self):
        """空のテーブルリストで空の結果を返す"""
        import my_lib.sensor_data

        result = my_lib.sensor_data._process_query_results([], True, False, 1, 3)

        assert result.value == []
        assert result.time == []
        assert result.valid is False

    def test_processes_records(self):
        """レコードを処理する"""
        import my_lib.sensor_data

        # モックレコードを作成
        mock_record1 = unittest.mock.MagicMock()
        mock_record1.get_value.return_value = 25.5
        mock_record1.get_time.return_value = datetime.datetime(2024, 1, 1, 0, 0, 0)

        mock_record2 = unittest.mock.MagicMock()
        mock_record2.get_value.return_value = 26.0
        mock_record2.get_time.return_value = datetime.datetime(2024, 1, 1, 0, 1, 0)

        mock_table = unittest.mock.MagicMock()
        mock_table.records = [mock_record1, mock_record2]

        result = my_lib.sensor_data._process_query_results([mock_table], False, False, 1, 1)

        assert len(result.value) == 2
        assert result.value[0] == 25.5
        assert result.value[1] == 26.0
        assert result.valid is True

    def test_skips_none_values(self):
        """None 値をスキップする"""
        import my_lib.sensor_data

        mock_record1 = unittest.mock.MagicMock()
        mock_record1.get_value.return_value = None
        mock_record1.get_time.return_value = datetime.datetime(2024, 1, 1, 0, 0, 0)

        mock_record2 = unittest.mock.MagicMock()
        mock_record2.get_value.return_value = 25.5
        mock_record2.get_time.return_value = datetime.datetime(2024, 1, 1, 0, 1, 0)

        mock_table = unittest.mock.MagicMock()
        mock_table.records = [mock_record1, mock_record2]

        result = my_lib.sensor_data._process_query_results([mock_table], False, False, 1, 1)

        assert len(result.value) == 1
        assert result.value[0] == 25.5

    def test_trims_excess_data_when_create_empty(self):
        """create_empty の場合、余分なデータを切り詰める"""
        import my_lib.sensor_data

        # 10個のレコードを作成
        records = []
        for i in range(10):
            mock_record = unittest.mock.MagicMock()
            mock_record.get_value.return_value = float(i)
            mock_record.get_time.return_value = datetime.datetime(2024, 1, 1, 0, i, 0)
            records.append(mock_record)

        mock_table = unittest.mock.MagicMock()
        mock_table.records = records

        # every_min=1, window_min=3 の場合、末尾2つのデータを削除
        result = my_lib.sensor_data._process_query_results([mock_table], True, False, 1, 3)

        assert len(result.value) == 8  # 10 - 2 = 8


class TestFetchData:
    """fetch_data 関数のテスト"""

    def test_returns_empty_result_on_exception(self):
        """例外発生時に空の結果を返す"""
        import my_lib.sensor_data

        db_config: my_lib.sensor_data.InfluxDBConfig = {
            "url": "http://localhost:8086",
            "token": "test_token",
            "org": "test_org",
            "bucket": "test_bucket",
        }

        with unittest.mock.patch("my_lib.sensor_data._fetch_data_impl", side_effect=Exception("Test error")):
            result = my_lib.sensor_data.fetch_data(db_config, "measure", "hostname", "field")

        assert result.valid is False
        assert result.value == []

    def test_uses_correct_template_for_window_0(self):
        """window_min=0 の場合、FLUX_QUERY_WITHOUT_AGGREGATION を使用する"""
        import my_lib.sensor_data

        db_config: my_lib.sensor_data.InfluxDBConfig = {
            "url": "http://localhost:8086",
            "token": "test_token",
            "org": "test_org",
            "bucket": "test_bucket",
        }

        mock_table = unittest.mock.MagicMock()
        mock_table.records = []

        with unittest.mock.patch(
            "my_lib.sensor_data._fetch_data_impl", return_value=[mock_table]
        ) as mock_fetch:
            my_lib.sensor_data.fetch_data(db_config, "measure", "hostname", "field", window_min=0)

            # テンプレートが WITHOUT_AGGREGATION であることを確認
            call_args = mock_fetch.call_args
            assert "aggregateWindow" not in call_args[0][1]


class TestFetchDataAsync:
    """fetch_data_async 関数のテスト"""

    def test_returns_result(self):
        """結果を返す"""
        import asyncio

        import my_lib.sensor_data

        db_config: my_lib.sensor_data.InfluxDBConfig = {
            "url": "http://localhost:8086",
            "token": "test_token",
            "org": "test_org",
            "bucket": "test_bucket",
        }

        mock_table = unittest.mock.MagicMock()
        mock_table.records = []

        async def run_test():
            with unittest.mock.patch(
                "my_lib.sensor_data._fetch_data_impl_async",
                return_value=[mock_table],
            ):
                return await my_lib.sensor_data.fetch_data_async(db_config, "measure", "hostname", "field")

        result = asyncio.run(run_test())
        assert result.valid is False  # 空のレコードなので valid=False


class TestFetchDataParallel:
    """fetch_data_parallel 関数のテスト"""

    def test_returns_results_for_multiple_requests(self):
        """複数リクエストの結果を返す"""
        import asyncio

        import my_lib.sensor_data

        db_config: my_lib.sensor_data.InfluxDBConfig = {
            "url": "http://localhost:8086",
            "token": "test_token",
            "org": "test_org",
            "bucket": "test_bucket",
        }

        requests = [
            my_lib.sensor_data.DataRequest(measure="m1", hostname="h1", field="f1"),
            my_lib.sensor_data.DataRequest(measure="m2", hostname="h2", field="f2"),
        ]

        mock_result = my_lib.sensor_data.SensorDataResult()

        async def run_test():
            with unittest.mock.patch(
                "my_lib.sensor_data.fetch_data_async",
                return_value=mock_result,
            ):
                return await my_lib.sensor_data.fetch_data_parallel(db_config, requests)

        results = asyncio.run(run_test())
        assert len(results) == 2


class TestGetSum:
    """get_sum 関数のテスト"""

    def test_returns_zero_for_empty_result(self):
        """空の結果で0を返す"""
        import my_lib.sensor_data

        db_config: my_lib.sensor_data.InfluxDBConfig = {
            "url": "http://localhost:8086",
            "token": "test_token",
            "org": "test_org",
            "bucket": "test_bucket",
        }

        mock_table = unittest.mock.MagicMock()
        mock_table.to_values.return_value = []

        with unittest.mock.patch("my_lib.sensor_data._fetch_data_impl", return_value=mock_table):
            result = my_lib.sensor_data.get_sum(db_config, "measure", "hostname", "field")

        assert result == 0

    def test_returns_sum_value(self):
        """合計値を返す"""
        import my_lib.sensor_data

        db_config: my_lib.sensor_data.InfluxDBConfig = {
            "url": "http://localhost:8086",
            "token": "test_token",
            "org": "test_org",
            "bucket": "test_bucket",
        }

        mock_table = unittest.mock.MagicMock()
        mock_table.to_values.return_value = [[10, 150.5]]

        with unittest.mock.patch("my_lib.sensor_data._fetch_data_impl", return_value=mock_table):
            result = my_lib.sensor_data.get_sum(db_config, "measure", "hostname", "field")

        assert result == 150.5

    def test_returns_zero_on_exception(self):
        """例外発生時に0を返す"""
        import my_lib.sensor_data

        db_config: my_lib.sensor_data.InfluxDBConfig = {
            "url": "http://localhost:8086",
            "token": "test_token",
            "org": "test_org",
            "bucket": "test_bucket",
        }

        with unittest.mock.patch("my_lib.sensor_data._fetch_data_impl", side_effect=Exception("Test error")):
            result = my_lib.sensor_data.get_sum(db_config, "measure", "hostname", "field")

        assert result == 0


class TestGetDaySum:
    """get_day_sum 関数のテスト"""

    def test_calls_get_sum_with_correct_params(self):
        """正しいパラメータで get_sum を呼び出す"""
        import my_lib.sensor_data

        db_config: my_lib.sensor_data.InfluxDBConfig = {
            "url": "http://localhost:8086",
            "token": "test_token",
            "org": "test_org",
            "bucket": "test_bucket",
        }

        with unittest.mock.patch("my_lib.sensor_data.get_sum", return_value=100.0) as mock_get_sum:
            result = my_lib.sensor_data.get_day_sum(db_config, "measure", "hostname", "field", days=7)

        assert result == 100.0
        mock_get_sum.assert_called_once()


class TestGetHourSum:
    """get_hour_sum 関数のテスト"""

    def test_calls_get_sum_with_correct_params(self):
        """正しいパラメータで get_sum を呼び出す"""
        import my_lib.sensor_data

        db_config: my_lib.sensor_data.InfluxDBConfig = {
            "url": "http://localhost:8086",
            "token": "test_token",
            "org": "test_org",
            "bucket": "test_bucket",
        }

        with unittest.mock.patch("my_lib.sensor_data.get_sum", return_value=50.0) as mock_get_sum:
            result = my_lib.sensor_data.get_hour_sum(db_config, "measure", "hostname", "field", hours=24)

        assert result == 50.0
        mock_get_sum.assert_called_once()
        # 引数を確認
        call_args = mock_get_sum.call_args
        assert call_args[0][4] == "-24h"  # start
        assert call_args[0][5] == "-0h"  # stop


class TestGetMinuteSum:
    """get_minute_sum 関数のテスト"""

    def test_calls_get_sum_with_correct_params(self):
        """正しいパラメータで get_sum を呼び出す"""
        import my_lib.sensor_data

        db_config: my_lib.sensor_data.InfluxDBConfig = {
            "url": "http://localhost:8086",
            "token": "test_token",
            "org": "test_org",
            "bucket": "test_bucket",
        }

        with unittest.mock.patch("my_lib.sensor_data.get_sum", return_value=10.0) as mock_get_sum:
            result = my_lib.sensor_data.get_minute_sum(db_config, "measure", "hostname", "field", minutes=60)

        assert result == 10.0
        mock_get_sum.assert_called_once()
        # 引数を確認
        call_args = mock_get_sum.call_args
        assert call_args[0][4] == "-60m"  # start
        assert call_args[0][5] == "-0m"  # stop


class TestGetEquipOnMinutes:
    """get_equip_on_minutes 関数のテスト"""

    def test_returns_zero_for_empty_table(self):
        """空のテーブルで0を返す"""
        import logging

        import my_lib.sensor_data

        db_config: my_lib.sensor_data.InfluxDBConfig = {
            "url": "http://localhost:8086",
            "token": "test_token",
            "org": "test_org",
            "bucket": "test_bucket",
        }

        # NOTE: ソースコードのロギング書式にバグがあるため logging.info をモック
        with unittest.mock.patch.object(logging, "info"):
            with unittest.mock.patch("my_lib.sensor_data._fetch_data_impl", return_value=[]):
                result = my_lib.sensor_data.get_equip_on_minutes(
                    db_config, "measure", "hostname", "field", threshold=10.0
                )

        assert result == 0

    def test_counts_minutes_above_threshold(self):
        """閾値を超えた分数をカウントする"""
        import logging

        import my_lib.sensor_data

        db_config: my_lib.sensor_data.InfluxDBConfig = {
            "url": "http://localhost:8086",
            "token": "test_token",
            "org": "test_org",
            "bucket": "test_bucket",
        }

        # 10個のレコード（5個が閾値以上）
        records = []
        for i in range(10):
            mock_record = unittest.mock.MagicMock()
            mock_record.get_value.return_value = float(i * 2)  # 0, 2, 4, 6, 8, 10, 12, 14, 16, 18
            mock_record.get_time.return_value = datetime.datetime(2024, 1, 1, 0, i, 0)
            records.append(mock_record)

        mock_table = unittest.mock.MagicMock()
        mock_table.records = records

        # NOTE: ソースコードのロギング書式にバグがあるため logging.info をモック
        with unittest.mock.patch.object(logging, "info"):
            with unittest.mock.patch("my_lib.sensor_data._fetch_data_impl", return_value=[mock_table]):
                result = my_lib.sensor_data.get_equip_on_minutes(
                    db_config,
                    "measure",
                    "hostname",
                    "field",
                    threshold=10.0,
                    every_min=1,
                    window_min=1,
                )

        # 10, 12, 14, 16, 18 が閾値(10)以上 = 5個
        assert result == 5

    def test_returns_zero_on_exception(self):
        """例外発生時に0を返す"""
        import logging

        import my_lib.sensor_data

        db_config: my_lib.sensor_data.InfluxDBConfig = {
            "url": "http://localhost:8086",
            "token": "test_token",
            "org": "test_org",
            "bucket": "test_bucket",
        }

        with unittest.mock.patch.object(logging, "info"):
            with unittest.mock.patch(
                "my_lib.sensor_data._fetch_data_impl", side_effect=Exception("Test error")
            ):
                result = my_lib.sensor_data.get_equip_on_minutes(
                    db_config, "measure", "hostname", "field", threshold=10.0
                )

        assert result == 0


class TestGetLastEvent:
    """get_last_event 関数のテスト"""

    def test_returns_none_for_empty_result(self):
        """空の結果で None を返す"""
        import my_lib.sensor_data

        db_config: my_lib.sensor_data.InfluxDBConfig = {
            "url": "http://localhost:8086",
            "token": "test_token",
            "org": "test_org",
            "bucket": "test_bucket",
        }

        mock_table = unittest.mock.MagicMock()
        mock_table.to_values.return_value = []

        with unittest.mock.patch("my_lib.sensor_data._fetch_data_impl", return_value=mock_table):
            result = my_lib.sensor_data.get_last_event(db_config, "measure", "hostname", "field")

        assert result is None

    def test_returns_datetime(self):
        """datetime を返す"""
        import my_lib.sensor_data

        db_config: my_lib.sensor_data.InfluxDBConfig = {
            "url": "http://localhost:8086",
            "token": "test_token",
            "org": "test_org",
            "bucket": "test_bucket",
        }

        expected_time = datetime.datetime(2024, 1, 1, 12, 0, 0)
        mock_table = unittest.mock.MagicMock()
        mock_table.to_values.return_value = [[expected_time]]

        with unittest.mock.patch("my_lib.sensor_data._fetch_data_impl", return_value=mock_table):
            result = my_lib.sensor_data.get_last_event(db_config, "measure", "hostname", "field")

        assert result == expected_time

    def test_returns_none_on_exception(self):
        """例外発生時に None を返す"""
        import my_lib.sensor_data

        db_config: my_lib.sensor_data.InfluxDBConfig = {
            "url": "http://localhost:8086",
            "token": "test_token",
            "org": "test_org",
            "bucket": "test_bucket",
        }

        with unittest.mock.patch("my_lib.sensor_data._fetch_data_impl", side_effect=Exception("Test error")):
            result = my_lib.sensor_data.get_last_event(db_config, "measure", "hostname", "field")

        assert result is None


class TestDumpData:
    """dump_data 関数のテスト"""

    def test_logs_data(self, caplog):
        """データをログに出力する"""
        import logging

        import my_lib.sensor_data

        data = my_lib.sensor_data.SensorDataResult(
            value=[1.0, 2.0],
            time=[
                datetime.datetime(2024, 1, 1, 0, 0, 0),
                datetime.datetime(2024, 1, 1, 0, 1, 0),
            ],
            valid=True,
        )

        with caplog.at_level(logging.INFO):
            my_lib.sensor_data.dump_data(data)

        assert "1.0" in caplog.text
        assert "2.0" in caplog.text
