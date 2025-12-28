# my-py-lib

IoT、自動化、データ収集アプリケーション向けの包括的なPythonユーティリティライブラリ。特にRaspberry Pi環境に最適化されています。

[![Test Status](https://github.com/kimata/my-py-lib/actions/workflows/regression.yaml/badge.svg)](https://github.com/kimata/my-py-lib/actions/workflows/regression.yaml)
[![Test Report](https://img.shields.io/badge/Test_Report-pytest.html-blue)](https://kimata.github.io/my-py-lib/pytest.html)
[![Coverage Status](https://coveralls.io/repos/github/kimata/my-py-lib/badge.svg?branch=main)](https://coveralls.io/github/kimata/my-py-lib?branch=main)

## 概要

my-py-libは、ハードウェア統合、データ処理、通知システム、Web自動化のための豊富なツールセットを提供するモジュラーPythonライブラリです。センサー、データストレージ、通知、Webサービスの標準化されたインターフェースを提供することで、IoTプロジェクトの開発を簡素化します。

## 主な機能

### 🔧 ハードウェアセンサー統合

- **19種類以上のセンサードライバー**（統一API）
- 環境センサー（温度、湿度、CO2、光、pH）
- エネルギー監視・スマートメーター統合
- I2C/SPIバス管理とGPIO制御
- 自動センサー検出とエラーハンドリング

### 📊 データパイプライン＆ストレージ

- **InfluxDB**統合による時系列データ管理
- 複雑なデータ集計と分析
- 時間窓での監視機能
- 自動データ検証とエラー回復

### 📢 マルチチャネル通知

- **Slack**、**LINE**、**Email**対応
- レート制限とインテリジェントなスロットリング
- リッチフォーマットとテンプレート対応
- スレッドセーフな動作

### 🌐 Webフレームワークユーティリティ

- Flaskベースのダッシュボード・APIユーティリティ
- JSONスキーマ検証付きYAML設定
- ヘルスチェックエンドポイントと監視
- リクエスト圧縮と最適化されたロギング

### 🤖 Web自動化

- ECサイトスクレイピング（Amazon、メルカリ）
- Selenium WebDriverユーティリティ
- CAPTCHA処理機能
- Chromeプロファイル管理

## インストール

### uv を使用（推奨）

```bash
# リポジトリをクローン
git clone <repository-url>
cd my-py-lib

# 依存関係をインストール
uv sync

# テストを実行
uv run pytest
```

### pip を使用

```bash
# ソースからインストール
pip install -e .
```

## クイックスタート

### 基本的なセンサー読み取り

```python
import my_lib.sensor
import my_lib.logger

# ロギングを初期化
my_lib.logger.init("my_app")

# 温湿度センサーを作成・使用
sensor = my_lib.sensor.sht35(bus_id=1, dev_addr=0x44)

if sensor.ping():
    data = sensor.get_value_map()
    print(f"温度: {data['temp']}°C")
    print(f"湿度: {data['humi']}%")
```

### InfluxDBでのデータ保存

```python
import my_lib.sensor_data
import my_lib.config

# 設定を読み込み
config = my_lib.config.load("config.yaml")

# センサーデータハンドラーを初期化
sensor_data = my_lib.sensor_data.SensorData(config)

# センサー測定値を保存
sensor_data.put("temperature", 23.5, {"location": "リビング"})

# 最近のデータを取得
recent_data = sensor_data.get_recent("temperature", minutes=60)
```

### 通知の送信

```python
import my_lib.notify.slack
import my_lib.config

config = my_lib.config.load("config.yaml")

# Slack通知を送信
slack = my_lib.notify.slack.Slack(config)
slack.send("🌡️ 温度アラート: 30°Cを超えました！")
```

### Webアプリケーション

```python
import flask
import my_lib.webapp.config
import my_lib.flask_util

app = flask.Flask(__name__)

# webapp設定を初期化
config = my_lib.config.load("config.yaml")
my_lib.webapp.config.init(config)

@app.route("/health")
def health():
    return {"status": "healthy"}

@app.route("/data")
@my_lib.flask_util.gzipped  # gzip圧縮を有効化
def get_data():
    # データエンドポイントのロジック
    return {"temperature": 23.5, "humidity": 60}

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
```

## 設定

このライブラリはJSONスキーマ検証付きのYAML設定ファイルを使用します。設定例：

```yaml
# config.yaml
sensor:
    influxdb:
        url: "http://localhost:8086"
        org: "my_org"
        bucket: "sensor_data"
        token: "${INFLUXDB_TOKEN}" # 環境変数

notify:
    slack:
        webhook_url: "${SLACK_WEBHOOK_URL}"
    line:
        channel_token: "${LINE_CHANNEL_TOKEN}"

webapp:
    log_dir: "./logs"
    compress_types:
        - "text/html"
        - "application/json"
```

## 対応センサー

### 環境センサー

| センサー | 説明                 | 測定項目                    | インターフェース | I2Cアドレス |
| -------- | -------------------- | --------------------------- | ---------------- | ----------- |
| SHT35    | 高精度温湿度センサー | 温度(°C)、湿度(%)           | I2C              | 0x44        |
| SCD4X    | CO2センサー          | CO2(ppm)、温度(°C)、湿度(%) | I2C              | 0x62        |

### 光センサー

| センサー  | 説明                   | 測定項目     | インターフェース  | I2Cアドレス |
| --------- | ---------------------- | ------------ | ----------------- | ----------- |
| APDS9250  | デジタル環境光センサー | 照度(lux)    | I2C               | 0x52        |
| SM9561    | デジタル照度センサー   | 照度(lux)    | I2C→RS485         | 0x4D        |
| LP_PYRA03 | 日射計                 | 日射量(W/m²) | I2C (ADS1115経由) | 0x48        |

### 水質センサー

| センサー  | 説明               | 測定項目 | インターフェース  | I2Cアドレス |
| --------- | ------------------ | -------- | ----------------- | ----------- |
| EZO_PH    | pH測定モジュール   | pH値     | I2C               | 0x64        |
| EZO_RTD   | 水温測定モジュール | 温度(°C) | I2C               | 0x66        |
| GROVE_TDS | TDSセンサー        | TDS(ppm) | I2C (ADS1115経由) | 0x4A        |

### 流量・降雨センサー

| センサー | 説明                  | 測定項目                 | インターフェース | I2Cアドレス |
| -------- | --------------------- | ------------------------ | ---------------- | ----------- |
| FD_Q10C  | KEYENCE製流量センサー | 流量(L/min)              | IO-Link          | -           |
| RG_15    | 雨量計                | 降雨量(mm/min)、降雨状態 | シリアル         | -           |

### エネルギー監視

| センサー      | 説明                 | 測定項目    | インターフェース      | I2Cアドレス |
| ------------- | -------------------- | ----------- | --------------------- | ----------- |
| EchonetEnergy | スマートメーター     | 瞬時電力(W) | シリアル (BP35A1経由) | -           |
| BP35A1        | Wi-SUN通信モジュール | -           | シリアル              | -           |

### ADCコンバーター

| センサー | 説明        | 測定項目 | インターフェース | I2Cアドレス |
| -------- | ----------- | -------- | ---------------- | ----------- |
| ADS1015  | 12ビットADC | 電圧(mV) | I2C              | 0x4A        |
| ADS1115  | 16ビットADC | 電圧(mV) | I2C              | 0x48        |

### 通信・ユーティリティ

| モジュール  | 説明                    | 用途                   |
| ----------- | ----------------------- | ---------------------- |
| I2CBUS      | I2Cバスラッパー         | デバッグ・ロギング     |
| ECHONETLite | ECHONET Liteプロトコル  | ホームオートメーション |
| LTC2874     | IO-Linkインターフェース | IO-Link通信            |

## 開発

### テストの実行

```bash
# 全テストを実行（並列実行・カバレッジはデフォルトで有効）
uv run pytest

# 特定のテストを実行
uv run pytest tests/unit/test_sensor.py::test_sht35
```

### プロジェクト構成

```
my-py-lib/
├── src/my_lib/
│   ├── sensor/          # ハードウェアセンサードライバー
│   ├── notify/          # 通知モジュール
│   ├── webapp/          # Webフレームワークユーティリティ
│   ├── store/           # ECサイト自動化
│   ├── config.py        # 設定管理
│   ├── logger.py        # ロギングユーティリティ
│   ├── sensor_data.py   # データパイプライン
│   └── ...              # その他のユーティリティ
├── tests/               # テストスイート
├── pyproject.toml       # プロジェクト設定
└── CLAUDE.md           # AIアシスタント用指示
```

## 必要条件

- **Python**: 3.10以上
- **ハードウェア**: Raspberry Pi（センサー機能用）
- **サービス**: InfluxDB（データストレージ用）
- **システム**: I2C/SPI有効化済みLinux

## 📄 ライセンス

**Apache License 2.0** - 詳細は [LICENSE](LICENSE) ファイルをご覧ください。

---

<div align="center">

**⭐ このプロジェクトが役に立った場合は、Star をお願いします！**

[🐛 Issue 報告](https://github.com/kimata/my-py-lib/issues) | [💡 Feature Request](https://github.com/kimata/my-py-lib/issues/new?template=feature_request.md) | [📖 Wiki](https://github.com/kimata/my-py-lib/wiki)

</div>
