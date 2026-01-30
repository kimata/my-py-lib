#!/usr/bin/env python3
"""
InfluxDB からデータを取得します。

Usage:
  sensor_data.py [-c CONFIG] [-m MODE] [-i DB_SPEC] [-s SENSOR_SPEC] [-f FIELD] [-e EVERY] [-w WINDOW]
                 [-p HOURS] [-D]

Options:
  -c CONFIG         : CONFIG を設定ファイルとして読み込んで実行します。
                      [default: tests/fixtures/config.example.yaml]
  -m MODE           : データ取得モード。(data, day_sum, hour_sum, minute_sum のいずれか) [default: data]
  -i DB_SPEC        : 設定ファイルの中で InfluxDB の設定が書かれているパス。[default: sensor.influxdb]
  -s SENSOR_SPEC    : 設定ファイルの中で取得対象のデータの設定が書かれているパス。[default: sensor.lux]
  -f FIELD          : 取得するフィールド。[default: lux]
  -e EVERY          : 何分ごとのデータを取得するか。[default: 1]
  -w WINDOWE        : 算出に使うウィンドウ。[default: 5]
  -p PERIOD         : 積算(sum)モードの場合に、過去どのくらいの分を取得するか。[default: 1]
  -D                : デバッグモードで動作します。
"""

from __future__ import annotations

import asyncio
import datetime
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Self


@dataclass(frozen=True)
class InfluxDBConfig:
    """InfluxDB 接続設定"""

    url: str
    token: str
    org: str
    bucket: str

    @classmethod
    def parse(cls, data: dict[str, Any]) -> Self:
        return cls(
            url=data["url"],
            token=data["token"],
            org=data["org"],
            bucket=data["bucket"],
        )


import influxdb_client  # noqa: E402
from influxdb_client.client.flux_table import TableList  # noqa: E402

import my_lib.time  # noqa: E402


@dataclass(frozen=True)
class SensorDataResult:
    """センサーデータ取得結果

    Attributes:
        value: センサー値のリスト
        time: タイムスタンプのリスト
        valid: データが有効かどうか
        raw_record_count: 取得した生レコード数（処理前）
        null_count: None だったレコード数
        error_message: エラー発生時のメッセージ
    """

    value: list[float] = field(default_factory=list)
    time: list[datetime.datetime] = field(default_factory=list)
    valid: bool = False
    raw_record_count: int = 0
    null_count: int = 0
    error_message: str | None = None

    def get_diagnostic_message(self) -> str:
        """診断メッセージを生成"""
        if self.error_message:
            return f"接続エラー: {self.error_message}"
        if self.raw_record_count == 0:
            return "データなし: クエリ結果が空でした"
        if self.null_count == self.raw_record_count:
            return f"全データがNone: {self.raw_record_count}件すべてがNoneでした"
        if self.null_count > 0:
            return (
                f"一部データがNone: {self.raw_record_count}件中{self.null_count}件がNone、"
                f"有効データ{len(self.value)}件"
            )
        return f"データ取得成功: {len(self.value)}件"


@dataclass(frozen=True)
class DataRequest:
    """センサーデータ取得リクエスト"""

    measure: str
    hostname: str
    field: str
    start: str = "-30h"
    stop: str = "now()"
    every_min: int = 1
    window_min: int = 3
    create_empty: bool = True
    last: bool = False


# NOTE: データが欠損している期間も含めてデータを敷き詰めるため、
# timedMovingAverage を使う。timedMovingAverage の計算の結果、データが後ろに
# ずれるので、あらかじめ offset を使って前にずらしておく。
FLUX_QUERY = """
from(bucket: "{bucket}")
|> range(start: {start}, stop: {stop})
    |> filter(fn:(r) => r._measurement == "{measure}")
    |> filter(fn: (r) => r.hostname == "{hostname}")
    |> filter(fn: (r) => r["_field"] == "{field}")
    |> aggregateWindow(every: {window}m, offset:-{window}m, fn: mean, createEmpty: {create_empty})
    |> fill(usePrevious: true)
    |> timedMovingAverage(every: {every}m, period: {window}m)
"""

FLUX_QUERY_WITHOUT_AGGREGATION = """
from(bucket: "{bucket}")
|> range(start: {start}, stop: {stop})
    |> filter(fn:(r) => r._measurement == "{measure}")
    |> filter(fn: (r) => r.hostname == "{hostname}")
    |> filter(fn: (r) => r["_field"] == "{field}")
    |> fill(usePrevious: true)
"""

FLUX_SUM_QUERY = """
from(bucket: "{bucket}")
    |> range(start: {start}, stop: {stop})
    |> filter(fn:(r) => r._measurement == "{measure}")
    |> filter(fn: (r) => r.hostname == "{hostname}")
    |> filter(fn: (r) => r["_field"] == "{field}")
    |> aggregateWindow(every: {every}m, offset:-{every}m, fn: mean, createEmpty: {create_empty})
    |> filter(fn: (r) => exists r._value)
    |> fill(usePrevious: true)
    |> reduce(
        fn: (r, accumulator) => ({{sum: r._value + accumulator.sum, count: accumulator.count + 1}}),
        identity: {{sum: 0.0, count: 0}},
    )
"""

FLUX_EVENT_QUERY = """
from(bucket: "{bucket}")
    |> range(start: {start})
    |> filter(fn: (r) => r._measurement == "{measure}")
    |> filter(fn: (r) => r.hostname == "{hostname}")
    |> filter(fn: (r) => r["_field"] == "{field}")
    |> map(fn: (r) => ({{ r with _value: if r._value then 1 else 0 }}))
    |> difference()
    |> filter(fn: (r) => r._value == 1)
    |> sort(columns: ["_time"], desc: true)
    |> limit(n: 1)
"""


def _process_query_results(
    table_list: list[Any], create_empty: bool, last: bool, every_min: int, window_min: int
) -> SensorDataResult:
    """共通のクエリ結果処理ロジック"""
    data_list = []
    time_list = []
    localtime_offset = datetime.timedelta(hours=9)

    # 診断情報
    raw_record_count = 0
    null_count = 0

    if len(table_list) != 0:
        raw_record_count = len(table_list[0].records)
        for record in table_list[0].records:
            # NOTE: aggregateWindow(createEmpty: true) と fill(usePrevious: true) の組み合わせ
            # だとタイミングによって、先頭に None が入る
            if record.get_value() is None:
                logging.debug("DELETE %s", record.get_time() + localtime_offset)
                null_count += 1
                continue

            data_list.append(record.get_value())
            time_list.append(record.get_time() + localtime_offset)

    if create_empty and not last:
        # NOTE: aggregateWindow(createEmpty: true) と timedMovingAverage を使うと、
        # 末尾に余分なデータが入るので取り除く
        every_min = int(every_min)
        window_min = int(window_min)
        if window_min > every_min:
            trim_count = window_min - every_min
            # データが十分にある場合のみ切り詰め
            if len(data_list) > trim_count:
                data_list = data_list[:-trim_count]
                time_list = time_list[:-trim_count]
            else:
                logging.warning(
                    "Insufficient data to trim: data_count=%d, trim_count=%d",
                    len(data_list),
                    trim_count,
                )

    logging.debug("data count = %s", len(time_list))
    return SensorDataResult(
        value=data_list,
        time=time_list,
        valid=len(time_list) != 0,
        raw_record_count=raw_record_count,
        null_count=null_count,
    )


def _fetch_data_impl(
    db_config: InfluxDBConfig,
    template: str,
    measure: str,
    hostname: str,
    field: str,
    start: str,
    stop: str,
    every: int,
    window: int,
    create_empty: bool,
    last: bool = False,
) -> TableList:
    client = None
    try:
        token = os.environ.get("INFLUXDB_TOKEN", db_config.token)

        query = template.format(
            bucket=db_config.bucket,
            measure=measure,
            hostname=hostname,
            field=field,
            start=start,
            stop=stop,
            every=every,
            window=window,
            create_empty=str(create_empty).lower(),
        )
        if last:
            query += " |> last()"

        logging.debug("Flux query = %s", query)
        client = influxdb_client.InfluxDBClient(url=db_config.url, token=token, org=db_config.org)  # pyright: ignore[reportPrivateImportUsage]
        query_api = client.query_api()

        return query_api.query(query=query)
    except Exception:
        logging.exception("Failed to fetch data")
        raise
    finally:
        if client is not None:
            client.close()


async def _fetch_data_impl_async(
    db_config: InfluxDBConfig,
    template: str,
    measure: str,
    hostname: str,
    field: str,
    start: str,
    stop: str,
    every: int,
    window: int,
    create_empty: bool,
    last: bool = False,
) -> TableList:
    """非同期版のデータ取得実装"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None,
        _fetch_data_impl,
        db_config,
        template,
        measure,
        hostname,
        field,
        start,
        stop,
        every,
        window,
        create_empty,
        last,
    )


def fetch_data(
    db_config: InfluxDBConfig,
    measure: str,
    hostname: str,
    field: str,
    start: str = "-30h",
    stop: str = "now()",
    every_min: int = 1,
    window_min: int = 3,
    create_empty: bool = True,
    last: bool = False,
) -> SensorDataResult:
    time_start = time.time()
    logging.debug(
        (
            "Fetch data (measure: %s, host: %s, field: %s, "
            "start: %s, stop: %s, every: %dmin, window: %dmin, "
            "create_empty: %s, last: %s)"
        ),
        measure,
        hostname,
        field,
        start,
        stop,
        every_min,
        window_min,
        create_empty,
        last,
    )

    try:
        template = FLUX_QUERY_WITHOUT_AGGREGATION if window_min == 0 else FLUX_QUERY

        table_list = _fetch_data_impl(
            db_config,
            template,
            measure,
            hostname,
            field,
            start,
            stop,
            every_min,
            window_min,
            create_empty,
            last,
        )
        time_fetched = time.time()

        result = _process_query_results(table_list, create_empty, last, every_min, window_min)

        time_finish = time.time()
        if ((time_fetched - time_start) > 1) or ((time_finish - time_fetched) > 0.1):
            logging.warning(
                "It's taking too long to retrieve the data. (fetch: %.2f sec, modify: %.2f sec)",
                time_fetched - time_start,
                time_finish - time_fetched,
            )

        return result
    except Exception as e:
        logging.exception("Failed to fetch data")

        return SensorDataResult(error_message=str(e))


async def fetch_data_async(
    db_config: InfluxDBConfig,
    measure: str,
    hostname: str,
    field: str,
    start: str = "-30h",
    stop: str = "now()",
    every_min: int = 1,
    window_min: int = 3,
    create_empty: bool = True,
    last: bool = False,
) -> SensorDataResult:
    """非同期版のfetch_data"""
    time_start = time.time()
    logging.debug(
        (
            "Fetch data async (measure: %s, host: %s, field: %s, "
            "start: %s, stop: %s, every: %dmin, window: %dmin, "
            "create_empty: %s, last: %s)"
        ),
        measure,
        hostname,
        field,
        start,
        stop,
        every_min,
        window_min,
        create_empty,
        last,
    )

    try:
        template = FLUX_QUERY_WITHOUT_AGGREGATION if window_min == 0 else FLUX_QUERY

        table_list = await _fetch_data_impl_async(
            db_config,
            template,
            measure,
            hostname,
            field,
            start,
            stop,
            every_min,
            window_min,
            create_empty,
            last,
        )
        time_fetched = time.time()

        result = _process_query_results(table_list, create_empty, last, every_min, window_min)

        time_finish = time.time()
        if ((time_fetched - time_start) > 1) or ((time_finish - time_fetched) > 0.1):
            logging.warning(
                "It's taking too long to retrieve the data. (fetch: %.2f sec, modify: %.2f sec)",
                time_fetched - time_start,
                time_finish - time_fetched,
            )

        return result
    except Exception as e:
        logging.exception("Failed to fetch data")

        return SensorDataResult(error_message=str(e))


async def fetch_data_parallel(
    db_config: InfluxDBConfig, requests: list[DataRequest]
) -> list[SensorDataResult | BaseException]:
    """
    複数のデータ取得リクエストを並列実行

    Args:
    ----
        db_config: InfluxDBの設定（全リクエスト共通）
        requests: DataRequest のリスト

    Returns:
    -------
        各リクエストの結果を含むリスト

    """
    tasks = []
    for req in requests:
        task = fetch_data_async(
            db_config,
            req.measure,
            req.hostname,
            req.field,
            req.start,
            req.stop,
            req.every_min,
            req.window_min,
            req.create_empty,
            req.last,
        )
        tasks.append(task)

    return await asyncio.gather(*tasks, return_exceptions=True)


def get_equip_on_minutes(
    config: InfluxDBConfig,
    measure: str,
    hostname: str,
    field: str,
    threshold: float,
    start: str = "-30h",
    stop: str = "now()",
    every_min: int = 1,
    window_min: int = 5,
    create_empty: bool = True,
) -> int:
    logging.info(
        (
            "Get 'ON' minutes (type: %s, host: %d, field: %d{field}, "
            "threshold: %.2f, start: %s, stop: %s, every: %smin, "
            "window: %dmin, create_empty: %s)"
        ),
        measure,
        hostname,
        field,
        threshold,
        start,
        stop,
        every_min,
        window_min,
        create_empty,
    )

    try:
        table_list = _fetch_data_impl(
            config,
            FLUX_QUERY,
            measure,
            hostname,
            field,
            start,
            stop,
            every_min,
            window_min,
            create_empty,
        )

        if len(table_list) == 0:
            return 0

        count = 0

        every_min = int(every_min)
        window_min = int(window_min)
        record_num = len(table_list[0].records)
        for i, record in enumerate(table_list[0].records):
            if create_empty and (window_min > every_min) and (i > record_num - 1 - (window_min - every_min)):
                # NOTE: timedMovingAverage を使うと、末尾に余分なデータが入るので取り除く
                continue

            # NOTE: aggregateWindow(createEmpty: true) と fill(usePrevious: true) の組み合わせ
            # だとタイミングによって、先頭に None が入る
            if record.get_value() is None:
                continue
            if record.get_value() >= threshold:
                count += 1

        return count * int(every_min)
    except Exception:
        logging.exception("Failed to fetch data")
        return 0


def get_equip_mode_period(
    config: InfluxDBConfig,
    measure: str,
    hostname: str,
    field: str,
    threshold_list: list[float],
    start: str = "-30h",
    stop: str = "now()",
    every_min: int = 10,
    window_min: int = 10,
    create_empty: bool = True,
) -> list[list[Any]]:
    logging.info(
        "Get equipment mode period (type: %s, host: %s, field: %s, "
        "threshold: %s, start: %s, stop: %s, every: %dmin, "
        "window: %dmin, create_empty: %s)",
        measure,
        hostname,
        field,
        f"[{','.join(f'{v:.1f}' for v in threshold_list)}]",
        start,
        stop,
        every_min,
        window_min,
        create_empty,
    )

    try:
        table_list = _fetch_data_impl(
            config,
            FLUX_QUERY,
            measure,
            hostname,
            field,
            start,
            stop,
            every_min,
            window_min,
            create_empty,
        )

        if len(table_list) == 0:
            return []

        # NOTE: 常時冷却と間欠冷却の期間を求める
        on_range = []
        state = -1
        start_time = None
        prev_time = None
        localtime_offset = datetime.timedelta(hours=9)

        for record in table_list[0].records:
            # NOTE: aggregateWindow(createEmpty: true) と fill(usePrevious: true) の組み合わせ
            # だとタイミングによって、先頭に None が入る
            if record.get_value() is None:
                logging.debug("DELETE %s", record.get_time() + localtime_offset)
                continue

            is_idle = True
            for i in range(len(threshold_list)):
                if record.get_value() > threshold_list[i]:
                    if state != i:
                        if state != -1:
                            assert start_time is not None  # noqa: S101
                            assert prev_time is not None  # noqa: S101
                            on_range.append(
                                [
                                    start_time + localtime_offset,
                                    prev_time + localtime_offset,
                                    state,
                                ]
                            )
                        state = i
                        start_time = record.get_time()
                    is_idle = False
                    break
            if is_idle and state != -1:
                assert start_time is not None  # noqa: S101
                assert prev_time is not None  # noqa: S101
                on_range.append(
                    [
                        start_time + localtime_offset,
                        prev_time + localtime_offset,
                        state,
                    ]
                )
                state = -1
                start_time = record.get_time()

            prev_time = record.get_time()

        if state != -1:
            assert start_time is not None  # noqa: S101
            on_range.append(
                [
                    start_time + localtime_offset,
                    table_list[0].records[-1].get_time() + localtime_offset,
                    state,
                ]
            )
        return on_range
    except Exception:
        logging.exception("Failed to fetch data")
        return []


def get_sum(
    config: InfluxDBConfig,
    measure: str,
    hostname: str,
    field: str,
    start: str = "-3m",
    stop: str = "now()",
    every_min: int = 1,
    window_min: int = 3,
) -> float:
    try:
        table_list = _fetch_data_impl(
            config, FLUX_SUM_QUERY, measure, hostname, field, start, stop, every_min, window_min, True
        )

        value_list = table_list.to_values(columns=["count", "sum"])

        if len(value_list) == 0:
            return 0
        else:
            sum_value = value_list[0][1]
            if isinstance(sum_value, int | float):
                return float(sum_value)
            logging.warning("Unexpected sum value type: %s (value=%s)", type(sum_value).__name__, sum_value)
            return 0
    except Exception:
        logging.exception("Failed to fetch data")
        return 0


def get_day_sum(
    config: InfluxDBConfig,
    measure: str,
    hostname: str,
    field: str,
    days: int,
    day_before: int = 0,
    day_offset: int = 0,
    every_min: int = 1,
    window_min: int = 5,
) -> float:
    now = my_lib.time.now()

    if day_before == 0:
        start = f"-{day_offset + days - 1}d{now.hour}h{now.minute}m"
        stop = f"-{day_offset}d"
    else:
        start = f"-{day_before + day_offset + days - 1}d{now.hour}h{now.minute}m"
        stop = f"-{day_before + day_offset - 1}d{now.hour}h{now.minute}m"

    return get_sum(config, measure, hostname, field, start, stop, every_min, window_min)


def get_hour_sum(
    config: InfluxDBConfig,
    measure: str,
    hostname: str,
    field: str,
    hours: int,
    day_offset: int = 0,
    every_min: int = 1,
    window_min: int = 1,
) -> float:
    start = f"-{day_offset * 24 + hours}h"
    stop = f"-{day_offset * 24}h"

    return get_sum(config, measure, hostname, field, start, stop, every_min, window_min)


def get_minute_sum(
    config: InfluxDBConfig,
    measure: str,
    hostname: str,
    field: str,
    minutes: int,
    day_offset: int = 0,
    every_min: int = 1,
    window_min: int = 1,
) -> float:
    start = f"-{day_offset * 24 * 60 + minutes}m"
    stop = f"-{day_offset * 24 * 60}m"

    return get_sum(config, measure, hostname, field, start, stop, every_min, window_min)


def get_last_event(
    config: InfluxDBConfig, measure: str, hostname: str, field: str, start: str = "-7d"
) -> datetime.datetime | None:
    try:
        table_list = _fetch_data_impl(
            config, FLUX_EVENT_QUERY, measure, hostname, field, start, "now()", 0, 0, False
        )

        value_list = table_list.to_values(columns=["_time"])

        if len(value_list) == 0:
            return None
        else:
            time_value = value_list[0][0]
            if isinstance(time_value, datetime.datetime):
                return time_value
            logging.warning(
                "Unexpected time value type: %s (value=%s)", type(time_value).__name__, time_value
            )
            return None
    except Exception:
        logging.exception("Failed to fetch data")
        return None


def dump_data(data: SensorDataResult) -> None:
    for i in range(len(data.time)):
        logging.info("%s: %s", data.time[i], data.value[i])


if __name__ == "__main__":
    # TEST Code
    import docopt

    import my_lib.config
    import my_lib.logger
    import my_lib.pretty

    def get_config(config, dotted_key):
        keys = dotted_key.split(".")
        value = config

        for key in keys:
            value = value[key]

        return value

    assert __doc__ is not None  # noqa: S101
    args = docopt.docopt(__doc__)

    config_file = args["-c"]
    mode = args["-m"]
    every = args["-e"]
    window = args["-w"]
    infxlux_db_spec = args["-i"]
    sensor_spec = args["-s"]
    field_name = args["-f"]
    period = int(args["-p"])
    debug_mode = args["-D"]

    my_lib.logger.init("test", level=logging.DEBUG if debug_mode else logging.INFO)

    config = my_lib.config.load(config_file)

    db_config = InfluxDBConfig.parse(get_config(config, infxlux_db_spec))
    sensor_config = get_config(config, sensor_spec)

    logging.info("DB config: %s", my_lib.pretty.format(db_config))
    logging.info("Sensor config: %s", my_lib.pretty.format(sensor_config))

    result: SensorDataResult | float
    if mode == "data":
        result = fetch_data(
            db_config,
            sensor_config["measure"],
            sensor_config["hostname"],
            field_name,
            start="-10m",
            stop="now()",
            every_min=1,
            window_min=3,
            create_empty=True,
            last=False,
        )
    elif mode == "day_sum":
        result = get_day_sum(
            db_config, sensor_config["measure"], sensor_config["hostname"], field_name, period
        )
    elif mode == "hour_sum":
        result = get_hour_sum(
            db_config, sensor_config["measure"], sensor_config["hostname"], field_name, period
        )
    elif mode == "minute_sum":
        result = get_minute_sum(
            db_config, sensor_config["measure"], sensor_config["hostname"], field_name, period
        )
    else:
        logging.error("Unknown mode: %s", mode)
        result = 0.0

    logging.info(my_lib.pretty.format(result))
