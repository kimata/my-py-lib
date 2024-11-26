#!/usr/bin/env python3
import datetime
import logging
import re
import ssl
import urllib.request

from lxml import html


def fetch_page(url, encoding="UTF-8"):
    logging.debug("fetch %s", url)

    # NOTE: 環境省のページはこれをしないとエラーになる
    ctx = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
    ctx.options |= 0x4  # OP_LEGACY_SERVER_CONNECT

    data = urllib.request.urlopen(url, context=ctx)  # noqa: S310

    if encoding is not None:
        return html.fromstring(data.read().decode(encoding))
    else:
        return html.fromstring(data.read())


def parse_weather_yahoo(content):
    return {
        "text": content.text_content().strip(),
        "icon_url": content.xpath("img/@src")[0].replace("_g.", "."),
    }


def parse_wind_yahoo(content):
    direction, speed = content.text_content().split()

    return {"dir": direction, "speed": int(speed)}


def parse_date_yahoo(content, index):
    date_text = content.xpath(f'(//h3/span[@class="yjSt"])[{index}]')[0].text_content().strip()
    date_text = re.search(r"\d{1,2}月\d{1,2}日", date_text).group(0)

    return datetime.datetime.strptime(date_text, "%m月%d日").replace(year=datetime.datetime.now().year)  # noqa: DTZ005, DTZ007


def parse_table_yahoo(content, index):
    ROW_LIST = ["hour", "weather", "temp", "humi", "precip", "wind"]

    day_info_by_type = {}
    table_xpath = f'(//table[@class="yjw_table2"])[{index}]'
    for row, label in enumerate(ROW_LIST):
        td_content_list = content.xpath(table_xpath + f"//tr[{row+1}]/td")
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

    day_data_list = []
    for i in range(len(day_info_by_type[ROW_LIST[0]])):
        day_info = {}
        for label in ROW_LIST:
            day_info[label] = day_info_by_type[label][i]
        day_data_list.append(day_info)

    return day_data_list


def parse_clothing_yahoo(content, index):
    table_xpath = (
        '(//dl[contains(@class, "indexList_item-clothing")])[{index}]' + "//dd/p[1]/@class"
    ).format(index=index)

    return int(content.xpath(table_xpath)[0].split("-", 1)[1])


def get_weather_yahoo(yahoo_config):
    content = fetch_page(yahoo_config["url"])

    return {
        "today": {"date": parse_date_yahoo(content, 1), "data": parse_table_yahoo(content, 1)},
        "tomorrow": {"date": parse_date_yahoo(content, 2), "data": parse_table_yahoo(content, 2)},
    }


def get_clothing_yahoo(yahoo_config):
    content = fetch_page(yahoo_config["url"])

    return {
        "today": {"date": parse_date_yahoo(content, 1), "data": parse_clothing_yahoo(content, 1)},
        "tomorrow": {"date": parse_date_yahoo(content, 1), "data": parse_clothing_yahoo(content, 2)},
    }


def parse_wbgt_current(content):
    wbgt = content.xpath('//span[contains(@class, "present_num")]')

    if len(wbgt) == 0:
        return None
    else:
        return float(wbgt[0].text_content().strip())


def parse_wbgt_daily(content, wbgt_measured_today):
    wbgt_col_list = content.xpath('//table[contains(@class, "forecast3day")]//td[contains(@class, "day")]')

    if len(wbgt_col_list) != 35:
        logging.warning("Invalid format")
        return {"today": None, "tomorro": None}

    wbgt_col_list = wbgt_col_list[8:]
    wbgt_list = []
    # NOTE: 0, 3, ..., 21 時のデータが入るようにする．0 時はダミーで可．
    for i in range(27):
        if i % 9 == 0:
            # NOTE: 日付を取得しておく
            m = re.search(r"(\d+)日", wbgt_col_list[i].text_content())
            wbgt_list.append(int(m.group(1)))
        else:
            val = wbgt_col_list[i].text_content().strip()
            if len(val) == 0:
                wbgt_list.append(None)
            else:
                wbgt_list.append(int(val))

    if (
        wbgt_list[0]
        == datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=+9), "JST")).date().day
    ):
        # NOTE: 日付が入っている部分は誤解を招くので None で上書きしておく
        wbgt_list[0] = None
        wbgt_list[9] = None

        # NOTE: 当日の過去データは実測値で差し替える
        for i in range(9):
            if wbgt_list[i] is None:
                wbgt_list[i] = wbgt_measured_today[i]

        return {
            "today": wbgt_list[0:9],
            "tomorrow": wbgt_list[9:18],
        }
    else:
        # NOTE: 昨日のデータが本日として表示されている

        # NOTE: 日付が入っている部分は誤解を招くので None で上書きしておく
        wbgt_list[9] = None
        wbgt_list[18] = None
        return {
            "today": wbgt_list[9:18],
            "tomorrow": wbgt_list[18:27],
        }


def get_wbgt_measured_today(wbgt_config):
    content = fetch_page(wbgt_config["data"]["env_go"]["url"].replace("graph_ref_td.php", "day_list.php"))
    wbgt_col_list = content.xpath(
        '//table[contains(@class, "asc_tbl_daylist")]//td[contains(@class, "asc_body")]'
    )

    wbgt_list = [None]
    for i, col in enumerate(wbgt_col_list):
        if i % 12 != 9:
            continue
        # NOTE: 0, 3, ..., 21 時のデータが入るようにする．0 時はダミーで可．
        val = col.text_content().strip()
        if val == "---":
            wbgt_list.append(None)
        else:
            wbgt_list.append(float(val))

    return wbgt_list


def get_wbgt(wbgt_config):
    # NOTE: 夏季にしか提供されないので冬は取りに行かない
    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=+9), "JST"))

    if (now.month < 3) or ((now.month == 4) and (now.day < 20)) or (now.month > 9):
        return {"current": None, "daily": {"today": None, "tomorrow": None}}

    # NOTE: 当日の過去時間のデータは表示されず，
    # 別ページに実測値があるので，それを取ってくる．
    wbgt_measured_today = get_wbgt_measured_today(wbgt_config)

    content = fetch_page(wbgt_config["data"]["env_go"]["url"])

    return {
        "current": parse_wbgt_current(content),
        "daily": parse_wbgt_daily(content, wbgt_measured_today),
    }


def get_sunset_url_nao(sunset_config, date):
    return "https://eco.mtk.nao.ac.jp/koyomi/dni/{year}/s{pref:02d}{month:02d}.html".format(
        year=date.year, month=date.month, pref=sunset_config["data"]["nao"]["pref"]
    )


def get_sunset_date_nao(sunset_config, date):
    # NOTE: XHTML で encoding が指定されているので，decode しないようにする
    content = fetch_page(get_sunset_url_nao(sunset_config, date), None)

    sun_data = content.xpath('//table[contains(@class, "result")]//td')

    sun_info = [
        {
            "day": sun_data[i + 0].text_content().strip(),
            "rise": sun_data[i + 1].text_content().strip(),
            "set": sun_data[i + 5].text_content().strip(),
        }
        for i in range(0, len(sun_data), 7)
    ]

    return sun_info[date.day - 1]["set"]


def get_sunset_nao(sunset_config):
    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=+9), "JST"))

    return {
        "today": get_sunset_date_nao(sunset_config, now),
        "tomorrow": get_sunset_date_nao(sunset_config, now + datetime.timedelta(days=1)),
    }


def parse_table_tenki(content, index):
    ROW_LIST = [
        {"label": "temp", "index": 6, "type": "float"},
        {"label": "precip", "index": 9, "type": "int"},
        {"label": "humi", "index": 10, "type": "int"},
    ]

    day_info_by_type = {}
    table_xpath = f'(//table[@class="forecast-point-1h"])[{index}]'
    for row_info in ROW_LIST:
        td_content_list = content.xpath(table_xpath + f'//tr[{row_info["index"]}]/td')

        match row_info["type"]:
            case "int":
                day_info_by_type[row_info["label"]] = [int(c.text_content()) for c in td_content_list]
            case "float":
                day_info_by_type[row_info["label"]] = [float(c.text_content()) for c in td_content_list]
            case _:  # pragma: no cover
                pass

    day_data_list = []
    for i in range(24):
        day_info = {}
        for row_info in ROW_LIST:
            day_info[row_info["label"]] = day_info_by_type[row_info["label"]][i]
        day_data_list.append(day_info)

    return day_data_list


def parse_date_tenki(content, index):
    date_text = (
        content.xpath(f'(((//table[@class="forecast-point-1h"])[{index}]/tr)[1]/td)[1]')[0]
        .text_content()
        .strip()
    )
    date_text = re.search(r"\d{4}年\d{1,2}月\d{1,2}日", date_text).group(0)

    return datetime.datetime.strptime(date_text, "%Y年%m月%d日")  # noqa: DTZ007


def get_precip_by_hour_tenki(tenki_config):
    content = fetch_page(tenki_config["url"])

    return {
        "today": {"date": parse_date_tenki(content, 1), "data": parse_table_tenki(content, 1)},
        "tommorow": {"date": parse_date_tenki(content, 2), "data": parse_table_tenki(content, 2)},
    }
