#!/usr/bin/env python3
"""
Web ページをスクレイピングして、天気に関する情報を取得します

Usage:
  weather.py [-c CONFIG] [-D]

Options:
  -c CONFIG         : CONFIG を設定ファイルとして読み込んで実行します。[default: config.yaml]
  -D                : デバッグモードで動作します。
"""

from __future__ import annotations

import datetime
import logging
import re
import ssl
import urllib.request
from dataclasses import dataclass, field
from typing import Any

import lxml.html

import my_lib.time

TIMEOUT_SEC: int = 5


@dataclass(frozen=True)
class WeatherInfo:
    """天気情報"""

    text: str
    icon_url: str


@dataclass(frozen=True)
class WindInfo:
    """風情報"""

    dir: str
    speed: int


@dataclass(frozen=True)
class HourlyData:
    """時間ごとのデータ"""

    hour: int
    weather: WeatherInfo
    temp: float
    humi: float
    precip: float
    wind: WindInfo


@dataclass(frozen=True)
class DayData:
    """日ごとのデータ"""

    date: datetime.datetime
    data: list[HourlyData] = field(default_factory=list)


@dataclass(frozen=True)
class WeatherResult:
    """天気取得結果"""

    today: DayData
    tomorrow: DayData


@dataclass(frozen=True)
class ClothingData:
    """服装指数データ"""

    date: datetime.datetime
    data: int


@dataclass(frozen=True)
class ClothingResult:
    """服装指数取得結果"""

    today: ClothingData
    tomorrow: ClothingData


@dataclass(frozen=True)
class WbgtDailyData:
    """WBGT 日別データ"""

    today: list[int | None] | None = None
    tomorrow: list[int | None] | None = None


@dataclass(frozen=True)
class WbgtResult:
    """WBGT 取得結果"""

    current: float | None = None
    daily: WbgtDailyData = field(default_factory=WbgtDailyData)


@dataclass(frozen=True)
class SunsetResult:
    """日没時刻取得結果"""

    today: str
    tomorrow: str


@dataclass(frozen=True)
class TenkiHourlyData:
    """tenki.jp 時間ごとのデータ"""

    temp: float
    precip: int
    humi: int


@dataclass(frozen=True)
class TenkiDayData:
    """tenki.jp 日ごとのデータ"""

    date: datetime.datetime
    data: list[TenkiHourlyData] = field(default_factory=list)


@dataclass(frozen=True)
class TenkiResult:
    """tenki.jp 取得結果"""

    today: TenkiDayData
    tomorrow: TenkiDayData


def fetch_page(url: str, encoding: str | None = "UTF-8") -> lxml.html.HtmlElement:
    logging.debug("fetch %s", url)

    # NOTE: 環境省のページはこれをしないとエラーになる
    ctx = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
    ctx.options |= 0x4  # OP_LEGACY_SERVER_CONNECT

    data = urllib.request.urlopen(url, context=ctx, timeout=TIMEOUT_SEC)  # noqa: S310

    if encoding is not None:
        return lxml.html.fromstring(data.read().decode(encoding))
    else:
        return lxml.html.fromstring(data.read())


def parse_weather_yahoo(content: lxml.html.HtmlElement) -> WeatherInfo:
    return WeatherInfo(
        text=content.text_content().strip(),
        icon_url=content.xpath("img/@src")[0].replace("_g.", "."),
    )


def parse_wind_yahoo(content: lxml.html.HtmlElement) -> WindInfo:
    direction, speed = content.text_content().split()

    return WindInfo(dir=direction, speed=int(speed))


def parse_date_yahoo(content: lxml.html.HtmlElement, index: int) -> datetime.datetime:
    date_text = content.xpath(f'(//h3/span[@class="yjSt"])[{index}]')[0].text_content().strip()
    match = re.search(r"\d{1,2}月\d{1,2}日", date_text)
    if match is None:
        raise ValueError(f"Failed to parse date from: {date_text}")
    date_text = match.group(0)

    return datetime.datetime.strptime(date_text, "%m月%d日").replace(year=datetime.datetime.now().year)  # noqa: DTZ005, DTZ007


def parse_table_yahoo(content: lxml.html.HtmlElement, index: int) -> list[HourlyData]:
    ROW_LIST = ["hour", "weather", "temp", "humi", "precip", "wind"]

    day_info_by_type: dict[str, list[Any]] = {}
    table_xpath = f'(//table[@class="yjw_table2"])[{index}]'
    for row, label in enumerate(ROW_LIST):
        td_content_list = content.xpath(table_xpath + f"//tr[{row + 1}]/td")
        td_content_list.pop(0)
        match row:
            case 0:
                day_info_by_type[label] = [
                    int(c.text_content().replace("時", "").strip()) for c in td_content_list
                ]
            case 1:
                day_info_by_type[label] = [parse_weather_yahoo(c) for c in td_content_list]
            case 2 | 3 | 4:
                day_info_by_type[label] = [float(c.text_content().strip()) for c in td_content_list]
            case 5:
                day_info_by_type[label] = [parse_wind_yahoo(c) for c in td_content_list]
            case _:  # pragma: no cover
                pass

    return [
        HourlyData(
            hour=day_info_by_type["hour"][i],
            weather=day_info_by_type["weather"][i],
            temp=day_info_by_type["temp"][i],
            humi=day_info_by_type["humi"][i],
            precip=day_info_by_type["precip"][i],
            wind=day_info_by_type["wind"][i],
        )
        for i in range(len(day_info_by_type[ROW_LIST[0]]))
    ]


def parse_clothing_yahoo(content: lxml.html.HtmlElement, index: int) -> int:
    table_xpath = (
        '(//dl[contains(@class, "indexList_item-clothing")])[{index}]' + "//dd/p[1]/@class"
    ).format(index=index)

    return int(content.xpath(table_xpath)[0].split("-", 1)[1])


def get_weather_yahoo(yahoo_config: dict[str, Any]) -> WeatherResult:
    content = fetch_page(yahoo_config["url"])

    return WeatherResult(
        today=DayData(date=parse_date_yahoo(content, 1), data=parse_table_yahoo(content, 1)),
        tomorrow=DayData(date=parse_date_yahoo(content, 2), data=parse_table_yahoo(content, 2)),
    )


def get_clothing_yahoo(yahoo_config: dict[str, Any]) -> ClothingResult:
    content = fetch_page(yahoo_config["url"])

    return ClothingResult(
        today=ClothingData(date=parse_date_yahoo(content, 1), data=parse_clothing_yahoo(content, 1)),
        tomorrow=ClothingData(date=parse_date_yahoo(content, 1), data=parse_clothing_yahoo(content, 2)),
    )


def parse_wbgt_current(content: lxml.html.HtmlElement) -> float | None:
    wbgt = content.xpath('//span[contains(@class, "present_num")]')

    if len(wbgt) == 0:
        return None
    else:
        return float(wbgt[0].text_content().strip())


def parse_wbgt_daily(
    content: lxml.html.HtmlElement, wbgt_measured_today: list[float | None]
) -> WbgtDailyData:
    wbgt_col_list = content.xpath('//table[contains(@class, "forecast3day")]//td[contains(@class, "day")]')

    if len(wbgt_col_list) != 35:
        logging.warning("Invalid format")
        return WbgtDailyData()

    wbgt_col_list = wbgt_col_list[8:]
    wbgt_list: list[int | None] = []
    # NOTE: 0, 3, ..., 21 時のデータが入るようにする。0 時はダミーで可。
    for i in range(27):
        if i % 9 == 0:
            # NOTE: 日付を取得しておく
            m = re.search(r"(\d+)日", wbgt_col_list[i].text_content())
            if m is None:
                raise ValueError(f"Failed to parse day from: {wbgt_col_list[i].text_content()}")
            wbgt_list.append(int(m.group(1)))
        else:
            val = wbgt_col_list[i].text_content().strip()
            if len(val) == 0:
                wbgt_list.append(None)
            else:
                wbgt_list.append(int(val))

    if wbgt_list[0] == my_lib.time.now().day:
        # NOTE: 日付が入っている部分は誤解を招くので None で上書きしておく
        wbgt_list[0] = None
        wbgt_list[9] = None

        # NOTE: 当日の過去データは実測値で差し替える
        for i in range(9):
            if wbgt_list[i] is None:
                measured = wbgt_measured_today[i]
                wbgt_list[i] = int(measured) if measured is not None else None

        return WbgtDailyData(
            today=wbgt_list[0:9],
            tomorrow=wbgt_list[9:18],
        )
    else:
        # NOTE: 昨日のデータが本日として表示されている

        # NOTE: 日付が入っている部分は誤解を招くので None で上書きしておく
        wbgt_list[9] = None
        wbgt_list[18] = None
        return WbgtDailyData(
            today=wbgt_list[9:18],
            tomorrow=wbgt_list[18:27],
        )


def get_wbgt_measured_today(wbgt_config: dict[str, Any]) -> list[float | None]:
    content = fetch_page(wbgt_config["data"]["env_go"]["url"].replace("graph_ref_td.php", "day_list.php"))
    wbgt_col_list = content.xpath(
        '//table[contains(@class, "asc_tbl_daylist")]//td[contains(@class, "asc_body")]'
    )

    wbgt_list: list[float | None] = [None]
    for i, col in enumerate(wbgt_col_list):
        if i % 12 != 9:
            continue
        # NOTE: 0, 3, ..., 21 時のデータが入るようにする。0 時はダミーで可。
        val = col.text_content().strip()
        if val == "---":
            wbgt_list.append(None)
        else:
            wbgt_list.append(float(val))

    return wbgt_list


def get_wbgt(wbgt_config: dict[str, Any]) -> WbgtResult:
    # NOTE: 夏季にしか提供されないので冬は取りに行かない
    now = my_lib.time.now()

    if (now.month < 3) or ((now.month == 4) and (now.day < 20)) or (now.month > 9):
        return WbgtResult()

    # NOTE: 当日の過去時間のデータは表示されず、
    # 別ページに実測値があるので、それを取ってくる。
    wbgt_measured_today = get_wbgt_measured_today(wbgt_config)

    content = fetch_page(wbgt_config["data"]["env_go"]["url"])

    return WbgtResult(
        current=parse_wbgt_current(content),
        daily=parse_wbgt_daily(content, wbgt_measured_today),
    )


def get_sunset_url_nao(sunset_config: dict[str, Any], date: datetime.datetime) -> str:
    return "https://eco.mtk.nao.ac.jp/koyomi/dni/{year}/s{pref:02d}{month:02d}.html".format(
        year=date.year, month=date.month, pref=sunset_config["data"]["nao"]["pref"]
    )


def get_sunset_date_nao(sunset_config: dict[str, Any], date: datetime.datetime) -> str:
    # NOTE: XHTML で encoding が指定されているので、decode しないようにする
    content = fetch_page(get_sunset_url_nao(sunset_config, date), None)

    sun_data = content.xpath('//table[contains(@class, "result")]//td')

    sun_info: list[dict[str, str]] = [
        {
            "day": sun_data[i + 0].text_content().strip(),
            "rise": sun_data[i + 1].text_content().strip(),
            "set": sun_data[i + 5].text_content().strip(),
        }
        for i in range(0, len(sun_data), 7)
    ]

    return sun_info[date.day - 1]["set"]


def get_sunset_nao(sunset_config: dict[str, Any]) -> SunsetResult:
    now = my_lib.time.now()

    try:
        return SunsetResult(
            today=get_sunset_date_nao(sunset_config, now),
            tomorrow=get_sunset_date_nao(sunset_config, now + datetime.timedelta(days=1)),
        )
    except Exception:
        logging.exception("Faile to fetch sunset info.")

        return SunsetResult(today="?", tomorrow="?")


def parse_table_tenki(content: lxml.html.HtmlElement, index: int) -> list[TenkiHourlyData]:
    ROW_LIST: list[dict[str, str | int]] = [
        {"label": "temp", "index": 6, "type": "float"},
        {"label": "precip", "index": 9, "type": "int"},
        {"label": "humi", "index": 10, "type": "int"},
    ]

    day_info_by_type: dict[str, list[int | float]] = {}
    table_xpath = f'(//table[@class="forecast-point-1h"])[{index}]'
    for row_info in ROW_LIST:
        td_content_list = content.xpath(table_xpath + f"//tr[{row_info['index']}]/td")

        match row_info["type"]:
            case "int":
                day_info_by_type[str(row_info["label"])] = [int(c.text_content()) for c in td_content_list]
            case "float":
                day_info_by_type[str(row_info["label"])] = [float(c.text_content()) for c in td_content_list]
            case _:  # pragma: no cover
                pass

    return [
        TenkiHourlyData(
            temp=float(day_info_by_type["temp"][i]),
            precip=int(day_info_by_type["precip"][i]),
            humi=int(day_info_by_type["humi"][i]),
        )
        for i in range(24)
    ]


def parse_date_tenki(content: lxml.html.HtmlElement, index: int) -> datetime.datetime:
    date_text = (
        content.xpath(f'(((//table[@class="forecast-point-1h"])[{index}]/tr)[1]/td)[1]')[0]
        .text_content()
        .strip()
    )
    match = re.search(r"\d{4}年\d{1,2}月\d{1,2}日", date_text)
    if match is None:
        raise ValueError(f"Failed to parse date from: {date_text}")
    date_text = match.group(0)

    return datetime.datetime.strptime(date_text, "%Y年%m月%d日")  # noqa: DTZ007


def get_precip_by_hour_tenki(tenki_config: dict[str, Any]) -> TenkiResult:
    content = fetch_page(tenki_config["url"])

    return TenkiResult(
        today=TenkiDayData(date=parse_date_tenki(content, 1), data=parse_table_tenki(content, 1)),
        tomorrow=TenkiDayData(date=parse_date_tenki(content, 2), data=parse_table_tenki(content, 2)),
    )


if __name__ == "__main__":
    # TEST Code
    import docopt

    import my_lib.config
    import my_lib.logger
    import my_lib.pretty

    args = docopt.docopt(__doc__)

    config_file = args["-c"]
    debug_mode = args["-D"]

    my_lib.logger.init("test", level=logging.DEBUG if debug_mode else logging.INFO)

    config = my_lib.config.load(config_file)

    sunset_config = config["sunset"]

    logging.info(my_lib.pretty.format(get_sunset_nao(sunset_config)))
