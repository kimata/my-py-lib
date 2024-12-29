#!/usr/bin/env python3
"""
InfluxDB から電子機器の使用時間を取得します．

Usage:
  sensor_data.py [-c CONFIG]  [-e EVERY] [-w WINDOW]

Options:
  -c CONFIG    : CONFIG を設定ファイルとして読み込んで実行します．[default: config.yaml]
  -e EVERY     : 何分ごとのデータを取得するか [default: 1]
  -w WINDOWE   : 算出に使うウィンドウ [default: 5]
"""

import datetime
import logging
import os
import time

import influxdb_client
from docopt import docopt

# NOTE: データが欠損している期間も含めてデータを敷き詰めるため，
# timedMovingAverage を使う．timedMovingAverage の計算の結果，データが後ろに
# ずれるので，あらかじめ offset を使って前にずらしておく．
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


def fetch_data_impl(  # noqa: PLR0913
    db_config, template, measure, hostname, field, start, stop, every, window, create_empty, last=False
):
    try:
        token = os.environ.get("INFLUXDB_TOKEN", db_config["token"])

        query = template.format(
            bucket=db_config["bucket"],
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
        client = influxdb_client.InfluxDBClient(url=db_config["url"], token=token, org=db_config["org"])
        query_api = client.query_api()

        return query_api.query(query=query)
    except Exception:
        logging.exception("Failed to fetch data")
        raise


def fetch_data(  # noqa: PLR0913
    db_config,
    measure,
    hostname,
    field,
    start="-30h",
    stop="now()",
    every_min=1,
    window_min=3,
    create_empty=True,
    last=False,
):
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

        table_list = fetch_data_impl(
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

        data_list = []
        time_list = []
        localtime_offset = datetime.timedelta(hours=9)

        if len(table_list) != 0:
            for record in table_list[0].records:
                # NOTE: aggregateWindow(createEmpty: true) と fill(usePrevious: true) の組み合わせ
                # だとタイミングによって，先頭に None が入る
                if record.get_value() is None:
                    logging.debug("DELETE %s", record.get_time() + localtime_offset)
                    continue

                data_list.append(record.get_value())
                time_list.append(record.get_time() + localtime_offset)

        if create_empty and not last:
            # NOTE: aggregateWindow(createEmpty: true) と timedMovingAverage を使うと，
            # 末尾に余分なデータが入るので取り除く
            every_min = int(every_min)
            window_min = int(window_min)
            if window_min > every_min:
                data_list = data_list[: (every_min - window_min)]
                time_list = time_list[: (every_min - window_min)]

        logging.debug("data count = %s", len(time_list))

        time_finish = time.time()
        if ((time_fetched - time_start) > 1) or ((time_finish - time_fetched) > 0.1):
            logging.warning(
                "It's taking too long to retrieve the data. (fetch: %.2f sec, modify: %.2f sec)",
                time_fetched - time_start,
                time_finish - time_fetched,
            )

        return {"value": data_list, "time": time_list, "valid": len(time_list) != 0}
    except Exception:
        logging.exception("Failed to fetch data")

        return {"value": [], "time": [], "valid": False}


def get_equip_on_minutes(  # noqa: PLR0913
    config,
    measure,
    hostname,
    field,
    threshold,
    start="-30h",
    stop="now()",
    every_min=1,
    window_min=5,
    create_empty=True,
):  # def get_equip_on_minutes
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
        table_list = fetch_data_impl(
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
                # NOTE: timedMovingAverage を使うと，末尾に余分なデータが入るので取り除く
                continue

            # NOTE: aggregateWindow(createEmpty: true) と fill(usePrevious: true) の組み合わせ
            # だとタイミングによって，先頭に None が入る
            if record.get_value() is None:
                continue
            if record.get_value() >= threshold:
                count += 1

        return count * int(every_min)
    except Exception:
        logging.exception("Failed to fetch data")
        return 0


def get_equip_mode_period(  # noqa: C901, PLR0913
    config,
    measure,
    hostname,
    field,
    threshold_list,
    start="-30h",
    stop="now()",
    every_min=10,
    window_min=10,
    create_empty=True,
):  # def get_equip_mode_period
    logging.info(
        (
            "Get equipment mode period (type: %s, host: %s, field: %s, "
            "threshold: %.2f, start: %s, stop: %s, every: %dmin, "
            "window: %dmin, create_empty: %s)",
        ),
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
        table_list = fetch_data_impl(
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
            # だとタイミングによって，先頭に None が入る
            if record.get_value() is None:
                logging.debug("DELETE %s", datetime=record.get_time() + localtime_offset)
                continue

            is_idle = True
            for i in range(len(threshold_list)):
                if record.get_value() > threshold_list[i]:
                    if state != i:
                        if state != -1:
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


def get_day_sum(config, measure, hostname, field, days=1, day_before=0, day_offset=0):  # noqa:  PLR0913
    try:
        every_min = 1
        window_min = 5

        now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=+9), "JST"))

        if day_before == 0:
            start = f"-{day_offset+days-1}d{now.hour}h{now.minute}m"
            stop = f"-{day_offset}d"
        else:
            start = f"-{day_before+ day_offset + days - 1 }d{now.hour}h{now.minute}m"
            stop = f"-{day_before + day_offset - 1}d{now.hour}h{now.minute}m"

        table_list = fetch_data_impl(
            config, FLUX_SUM_QUERY, measure, hostname, field, start, stop, every_min, window_min, True
        )

        value_list = table_list.to_values(columns=["count", "sum"])

        if len(value_list) == 0:
            return 0
        else:
            return value_list[0][1]
    except Exception:
        logging.exception("Failed to fetch data")
        return 0


def get_sum(config, measure, hostname, field, start="-30h", stop="now()", every_min=1, window_min=3):  # noqa:  PLR0913
    try:
        table_list = fetch_data_impl(
            config, FLUX_SUM_QUERY, measure, hostname, field, start, stop, every_min, window_min, True
        )

        value_list = table_list.to_values(columns=["count", "sum"])

        if len(value_list) == 0:
            return 0
        else:
            return value_list[0][1]
    except Exception:
        logging.exception("Failed to fetch data")
        return 0


def get_last_event(config, measure, hostname, field, start="-7d"):
    try:
        table_list = fetch_data_impl(
            config, FLUX_EVENT_QUERY, measure, hostname, field, start, "now()", 0, 0, False
        )

        value_list = table_list.to_values(columns=["_time"])

        if len(value_list) == 0:
            return None
        else:
            return value_list[0][0]
    except Exception:
        logging.exception("Failed to fetch data")
        return None


def dump_data(data):
    for i in range(len(data["time"])):
        logging.info("%s: %s", data["time"][i], data["value"][i])


if __name__ == "__main__":
    import json

    import logger
    from config import get_db_config, load_config

    args = docopt(__doc__)

    logger.init("test", logging.DEBUG)

    config = load_config(args["-c"])
    every = args["-e"]
    window = args["-w"]

    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=+9), "JST"))
    measure = config["USAGE"]["TARGET"]["TYPE"]
    hostname = config["USAGE"]["TARGET"]["HOST"]
    param = config["USAGE"]["TARGET"]["PARAM"]
    threshold = config["USAGE"]["TARGET"]["THRESHOLD"]["WORK"]
    start = "-" + config["GRAPH"]["PARAM"]["PERIOD"]

    db_config = get_db_config(config)

    dump_data(fetch_data(db_config, measure, hostname, param, start, "now()", every, window))

    start = f"-{now.hour}h{now.minute}m"

    logging.info(
        "Today ON minutes (%s) = %s min",
        start,
        get_equip_on_minutes(
            db_config,
            measure,
            hostname,
            param,
            threshold,
            start,
            "now()",
            every,
            window,
        ),
    )

    measure = config["GRAPH"]["VALVE"]["TYPE"]
    hostname = config["GRAPH"]["VALVE"]["HOST"]
    param = config["GRAPH"]["VALVE"]["PARAM"]
    threshold = [
        # NOTE: 閾値が高いものから並べる
        config["GRAPH"]["VALVE"]["THRESHOLD"]["FULL"],
        config["GRAPH"]["VALVE"]["THRESHOLD"]["INTERM"],
    ]
    start = "-" + config["GRAPH"]["PARAM"]["PERIOD"]

    logging.info(
        "Valve on period = %s",
        json.dumps(
            get_equip_mode_period(db_config, measure, hostname, param, threshold, start, "now()"),
            indent=2,
            default=str,
        ),
    )

    logging.info(
        "Amount of cooling water used today = {get_day_sum(db_config, measure, hostname, param):.2f} L"
    )
