# CLAUDE.md

このファイルは Claude Code がこのリポジトリで作業する際のガイダンスを提供します。

## 重要な注意事項

### プロジェクト設定ファイルの管理

**pyproject.toml をはじめとする一般的なプロジェクト管理ファイルは `../py-project` で一元管理しています。**

- プロジェクト設定ファイル（pyproject.toml、.gitlab-ci.yml、.pre-commit-config.yaml 等）を直接編集しないでください
- 設定を変更したい場合は、`../py-project` のテンプレートを更新し、このリポジトリに適用してください
- 変更を行う前に、何を変更したいのかを説明し、ユーザーの確認を取ってください

### ドキュメントの更新

コードを更新した際は、以下のドキュメントの更新が必要かどうか検討してください：

- **README.md**: 機能追加・変更、使用方法の変更、依存関係の変更があった場合
- **CLAUDE.md**: アーキテクチャの変更、開発コマンドの変更、重要なパターンの追加があった場合
- **CHANGELOG.md**: タグを打つ際に必ず更新（詳細は「開発ワークフロー規約」を参照）

## 開発コマンド

### 依存関係の管理

- **依存関係のインストール**: `uv sync`（本番・開発両方の依存関係をインストール）
- **新しい依存関係の追加**: `uv add <パッケージ名>`
- **開発用依存関係の追加**: `uv add --dev <パッケージ名>`
- **ロックファイルの更新**: `uv lock`

### テスト

- **全テストの実行**: `uv run pytest`（並列実行はデフォルトで有効）
- **特定テストの実行**: `uv run pytest tests/unit/test_xxx.py::TestClass::test_method`
- **カバレッジレポート**: テスト実行時に自動生成 → `reports/coverage/`
- **HTMLレポート**: `reports/pytest.html`

### コード品質

- **型チェック（pyright）**: `uv run pyright`
- **型チェック（mypy）**: `uv run mypy src/`
- **フォーマット**: `rye fmt`
- **リント**: `rye lint`

### ビルド

- **パッケージビルド**: `rye build`

## アーキテクチャ概要

IoT、自動化、データ収集アプリケーション向けの個人用ユーティリティライブラリです。
特に Raspberry Pi 環境での利用に最適化されています。

### ディレクトリ構造

```
src/my_lib/
├── sensor/              # ハードウェアセンサードライバ（19種類以上）
│   ├── base.py          # SensorBase, I2CSensorBase 抽象クラス
│   ├── exceptions.py    # SensorError, SensorCommunicationError
│   ├── i2cbus.py        # I2C バスラッパー（SMBus2）
│   ├── sht35.py         # 温湿度センサー
│   ├── scd4x.py         # CO2センサー
│   ├── ads1115.py       # 16bit ADC
│   └── ...
│
├── notify/              # 通知システム
│   ├── slack.py         # Slack 通知（WebClient、画像アップロード対応）
│   ├── line.py          # LINE Bot 通知
│   └── mail.py          # メール通知
│
├── webapp/              # Web フレームワークユーティリティ
│   ├── config.py        # グローバル設定
│   ├── base.py          # Flask ブループリント
│   └── log.py           # ロギング
│
├── store/               # E コマーススクレイピング
│   ├── amazon/          # Amazon（API、ログイン、CAPTCHA）
│   └── mercari/         # メルカリ
│
├── config.py            # YAML + JSON Schema 設定管理
├── sensor_data.py       # InfluxDB 時系列データ統合
├── flask_util.py        # Flask デコレータ（gzip、ETag）
├── logger.py            # 構造化ロギング（ローテーション、圧縮）
├── healthz.py           # ヘルスチェックエンドポイント
├── selenium_util.py     # Selenium ヘルパー
├── sqlite_util.py       # SQLite ユーティリティ
├── rpi.py               # Raspberry Pi GPIO ユーティリティ
├── footprint.py         # タイムスタンプベースのマーカー
├── serializer.py        # pickle ベースの状態永続化
└── pytest_util.py       # pytest-xdist 並列実行サポート
```

### テスト構造

```
tests/
├── conftest.py          # 共有フィクスチャ、モック設定
├── unit/                # ユニットテスト（20以上のテストファイル）
├── integration/         # 統合テスト
└── fixtures/
    ├── config.example.yaml  # テスト用設定例
    └── chrome/test/     # Selenium プロファイル

reports/                 # テスト実行時に自動生成（.gitignore 対象）
├── pytest.html          # HTML テストレポート
└── coverage/            # カバレッジレポート
```

## 主要パターン

### センサー管理

統一されたインターフェースを持つ抽象基底クラス：

```python
class SensorBase(ABC):
    def ping(self) -> bool:          # センサー応答確認
    def get_value_map(self) -> dict: # 測定値取得
    def _ping_impl(self) -> bool:    # サブクラス実装
```

### 設定駆動設計

YAML 設定 + JSON Schema バリデーション：

```python
config = my_lib.config.load("config.yaml")  # 読み込み＋検証
slack_config = my_lib.notify.slack.parse_config(config["slack"])
```

環境変数の展開をサポート：

```yaml
influxdb:
    token: "${INFLUXDB_TOKEN}"
```

### 通知システム

レート制限とスロットリング：

- `/dev/shm/notify/` にフットプリントを使用
- 通知間隔の制限（デフォルト60秒）
- 複数チャンネル対応（Slack、LINE、メール）

### Flask デコレータ

```python
@my_lib.flask_util.gzipped              # レスポンス圧縮
@my_lib.flask_util.file_etag(...)       # ETag キャッシュ
@my_lib.flask_util.support_jsonp()      # JSONP サポート
```

### pytest-xdist 対応

並列テスト実行時のファイルパス衝突を回避：

```python
# footprint.py, serializer.py で使用
path = my_lib.pytest_util.get_path(path_str)
# PYTEST_XDIST_WORKER 環境変数でサフィックスを付与
```

テストでファイル存在確認時は `my_lib.footprint.exists()` または
`my_lib.pytest_util.get_path()` を使用すること。

## コーディング規約

### データ構造の定義

- **TypedDict は使用しない**: 構造化データには `@dataclass(frozen=True)` を使用
- TypedDict は辞書のような使い勝手だが、属性アクセス（`.属性名`）を使えない
- dataclass は型安全性が高く、IDE のサポートも充実

### メソッド命名規則

| 用途           | メソッド名      | 説明                                       |
| -------------- | --------------- | ------------------------------------------ |
| 辞書からの生成 | `parse()`       | クラスメソッド。`from_dict()` は使用しない |
| 内部実装       | `_メソッド名()` | アンダースコアで始める                     |

### ファイルヘッダー

- **Shebang**: `#!/usr/bin/env python3` を使用（`python` は使用しない）

### 型エイリアスの使用

複合型が3箇所以上で出現する場合は型エイリアスを定義：

```python
from typing import TypeAlias

ETagData: TypeAlias = str | bytes | dict[str, Any]
```

### dataclass の frozen 属性

| 用途            | frozen 設定    | 理由                                 |
| --------------- | -------------- | ------------------------------------ |
| 設定クラス      | `frozen=True`  | 不変性を保証                         |
| 結果/データ転送 | `frozen=True`  | 不変性を保証                         |
| 状態管理        | `frozen=False` | 状態更新が必要。コメントで理由を明示 |

### 例外処理

`except Exception:` は最後の手段。可能な限り具体的な例外型を使用：

```python
# Good
except sqlite3.OperationalError:
except socket.timeout:
except requests.RequestException:

# Avoid（ただしログ出力は必須）
except Exception:
    logging.exception("...")
```

#### ライブラリ別推奨例外型

| ライブラリ | 推奨する例外型                                       |
| ---------- | ---------------------------------------------------- |
| smtplib    | `smtplib.SMTPException`                              |
| linebot    | `linebot.v3.messaging.ApiException`                  |
| slack_sdk  | `slack_sdk.errors.SlackApiError`, `SlackClientError` |
| selenium   | `TimeoutException`, `WebDriverException`             |
| I2C 通信   | `OSError`, `SensorCommunicationError`                |
| urllib     | `urllib.error.URLError`, `urllib.error.HTTPError`    |

### 例外クラスの定義

すべての例外クラスには docstring を記述：

```python
class MyError(Exception):
    """エラーの概要を1行で記述"""
```

### 重複コードの禁止

同一機能のコードが複数ファイルに存在する場合は、1箇所に統合する。

#### リファクタリング時の API 変更

リファクタリング時に既存の API を変更する場合、後方互換性のためのラッパー関数は
作成せず、呼び出し元を直接修正する：

```python
# Bad: 後方互換性のためのラッパー関数を残す
def parse_config(data: dict[str, Any]) -> Config:
    return Config.parse(data)

# Good: 呼び出し元を直接修正
# Before: result = parse_config(data)
# After:  result = Config.parse(data)
```

**理由**:

- コードの重複を避ける
- API の一貫性を保つ
- 将来の混乱を防ぐ

## 設定クラスの実装規約

全プロジェクトで統一された設定管理パターン。

### 基本構造

```python
from __future__ import annotations

import pathlib
from dataclasses import dataclass
from typing import Any, Self

import my_lib.config


@dataclass(frozen=True)  # 必須: 不変性を保証
class SubConfig:
    """ネストされた設定"""
    name: str
    value: int

    @classmethod
    def parse(cls, data: dict[str, Any]) -> Self:
        """辞書からインスタンスを生成"""
        return cls(
            name=data["name"],
            value=data["value"],
        )


@dataclass(frozen=True)
class Config:
    """メイン設定"""
    base_dir: pathlib.Path
    sub: SubConfig
    optional_field: str | None = None

    @classmethod
    def parse(cls, data: dict[str, Any]) -> Self:
        return cls(
            base_dir=pathlib.Path(data["base_dir"]),
            sub=SubConfig.parse(data["sub"]),  # ネストは再帰的に parse()
            optional_field=data.get("optional_field"),
        )


def load(config_path: str, schema_path: str | None = None) -> Config:
    """設定ファイルを読み込んでパースする（module-level 関数）"""
    raw = my_lib.config.load(config_path, schema_path)
    return Config.parse(raw)
```

### ルール

| ルール                 | 説明                                             |
| ---------------------- | ------------------------------------------------ |
| `frozen=True`          | 全ての設定 dataclass に必須。設定の不変性を保証  |
| `@classmethod parse()` | 辞書からインスタンスを生成するファクトリメソッド |
| 戻り値型 `Self`        | `typing.Self` を使用（Python 3.11+）             |
| ネストの処理           | 子クラスの `parse()` を再帰的に呼び出す          |
| `load()` 関数          | module-level で定義。スキーマ検証 → パースの流れ |

### パターン別の実装例

#### リストの処理

```python
@dataclass(frozen=True)
class ParentConfig:
    items: list[ItemConfig]

    @classmethod
    def parse(cls, data: dict[str, Any]) -> Self:
        return cls(
            items=[ItemConfig.parse(item) for item in data["items"]],
        )
```

#### Optional フィールド

```python
@dataclass(frozen=True)
class Config:
    required: str
    optional: SubConfig | None = None

    @classmethod
    def parse(cls, data: dict[str, Any]) -> Self:
        optional_data = data.get("optional")
        return cls(
            required=data["required"],
            optional=SubConfig.parse(optional_data) if optional_data else None,
        )
```

#### デフォルト値

```python
from dataclasses import field

@dataclass(frozen=True)
class Config:
    # シンプルなデフォルト
    timeout: int = 30

    # ミュータブルなデフォルト（list, dict）は field() を使用
    tags: list[str] = field(default_factory=list)

    @classmethod
    def parse(cls, data: dict[str, Any]) -> Self:
        return cls(
            timeout=data.get("timeout", 30),
            tags=data.get("tags", []),
        )
```

#### 型変換

```python
@classmethod
def parse(cls, data: dict[str, Any]) -> Self:
    return cls(
        # pathlib.Path への変換
        path=pathlib.Path(data["path"]),
        # 数値型の明示的変換
        scale=float(data.get("scale", 1.0)),
        offset=int(data.get("offset", 0)),
    )
```

### 検証ロジック

JSON Schema による検証は `my_lib.config.load()` で実施。
追加の検証が必要な場合は `parse()` 内で実装：

```python
@classmethod
def parse(cls, data: dict[str, Any]) -> Self:
    scale = data["scale"]
    if scale not in ("linear", "log"):
        msg = f"scale must be 'linear' or 'log', got {scale}"
        raise ValueError(msg)

    return cls(scale=scale)
```

### アンチパターン（避けるべき実装）

```python
# Bad: frozen なし（ミュータブルになる）
@dataclass
class Config:
    ...

# Bad: parse() を使わず直接コンストラクタ呼び出し
config = Config(**data)  # 型変換やネスト処理が行われない

# Bad: get() のデフォルト値が None になりうる
optional = parse_sub(data.get("optional"))  # None が渡される可能性

# Good: None チェックを明示
optional_data = data.get("optional")
optional = parse_sub(optional_data) if optional_data else None
```

## 例外クラス

### センサー関連

- `SensorError` - 基底例外
- `SensorCommunicationError` - 通信エラー
- `SensorCRCError` - CRC チェックエラー

### 設定関連

- `ConfigValidationError` - スキーマ検証エラー（details 属性あり）
- `ConfigParseError` - YAML パースエラー
- `ConfigFileNotFoundError` - ファイル未発見

### 画像関連（pil_util.py）

- `FontNotFoundError` - フォントファイル未発見
- `ImageNotFoundError` - 画像ファイル未発見

## 開発時の注意

### 型チェック

- mypy と pyright の両方でチェック
- `tests/fixtures/` は除外設定済み

#### 基本方針

**`# type: ignore` コメントは最後の手段とする。** 型エラーが発生した場合は、まずコードを修正して型推論が正しく働くようにする。

対処の優先順位：

1. コードを修正して型推論できるようにする（変数への型注釈、`assert` による型ナローイング等）
2. `Any` 型を明示的に使用する（型情報がないライブラリの場合）
3. `# type: ignore` コメントを使用する（他に手段がない場合のみ）

**例外**: テストコード（`tests/`）では、可読性を優先して `# type: ignore` を許容する。

#### ファイルの git add について

支持されて作成したプログラムやリファクタリングの結果追加されたプログラム以外は
git add しないこと。プログラムが動作するのに必要なデータについては、追加して良いか
確認すること。

#### 型スタブがないライブラリへの対処

型スタブが提供されていないライブラリを使用する場合、`# type: ignore` コメントを大量に記述するのではなく、
戻り値を受け取る変数に `Any` 型注釈を付けて対処する：

```python
from typing import Any

# Good: Any 型注釈で型チェッカーに「このライブラリには型情報がない」ことを明示
resp: Any = api.get_items(request)
if resp.items_result is not None:
    for item in resp.items_result.items:
        ...

# Bad: 各行に type: ignore を記述
resp = api.get_items(request)
if resp.items_result is not None:  # type: ignore[union-attr]
    for item in resp.items_result.items:  # type: ignore[union-attr]
        ...
```

#### import 文の書き方

サブモジュールへのアクセスは、明示的な import を使用する：

```python
# Good: 明示的な import
import selenium.webdriver.support.expected_conditions
import urllib.parse
import urllib.error

# Bad: 暗黙的なサブモジュールアクセス
import selenium
selenium.webdriver.support.expected_conditions  # pyright エラー
```

また、避けようがない場合を除き、下記の形式は使用しないこと。

```python
import xxx as yyy
```

#### docopt の `__doc__` 対応

`docopt` を使用する場合、`__doc__` が `str | None` のため assert で型を絞り込む：

```python
assert __doc__ is not None
args = docopt.docopt(__doc__)
```

### テスト作成

- `@pytest.mark.web` - Web テスト用マーカー（`--run-web` で実行）
- `@pytest.mark.mercari` - メルカリテスト用マーカー
- 一時ファイルは `temp_dir` フィクスチャを使用
- Slack 通知確認は `slack_checker` フィクスチャを使用

### ロギング規約

```python
import logging
logging.debug("詳細情報: %s", value)
logging.info("通常の操作情報")
logging.warning("警告")
logging.error("エラー")
```

## 外部依存

### 主要な依存関係

- **pyyaml** - YAML 設定ファイル
- **jsonschema** - 設定バリデーション
- **slack-sdk** - Slack API
- **line-bot-sdk** - LINE API
- **influxdb-client** - 時系列データベース
- **smbus2** - I2C 通信（Raspberry Pi）
- **selenium** - Web 自動化

### 開発用依存関係

- **pytest**, **pytest-cov**, **pytest-xdist** - テスト
- **mypy**, **pyright** - 型チェック
- **flask** - Web テスト用
- **pillow** - 画像処理テスト用

## 追加規約

### 型エイリアスの定義

型エイリアスには必ず `TypeAlias` 注釈を付ける：

```python
from typing import TypeAlias

# Good
ConfigTypes: TypeAlias = ConfigA | ConfigB | ConfigC

# Bad（型チェッカーが変数と誤認する可能性）
ConfigTypes = ConfigA | ConfigB | ConfigC
```

### Protocol 使用の判断基準

Protocol は以下の場合に使用：

- 複数の異なるクラスが共通のインターフェースを持つ場合
- 構造的部分型付け（Duck Typing）を型安全にしたい場合
- コールバック関数が**3箇所以上**で使用される場合

以下の場合は Protocol を**使用しない**：

- 単純な `| None` のオプショナル値
- 1-2箇所でしか使用されないコールバック関数
- `isinstance` チェックで十分明快な場合

### import エイリアスの使用

業界標準のエイリアスは許容する：

```python
# Good: 業界標準のエイリアス
import numpy as np
import pandas as pd

# Bad: 独自の短縮形
import my_lib.util as util
```

### 後方互換性コードの扱い

後方互換性のための re-export モジュールは：

1. 明確なドキュメント（docstring）で「後方互換性のため」と記載
2. 新規コードでの使用先を明示
3. **削除は慎重に** - 外部依存の影響を確認してから

### 後方互換性コードの削除基準

後方互換性のためのコード（re-export モジュール等）は、以下の条件を満たす場合に削除する：

1. grep で外部からの import がゼロであることを確認
2. テストで使用されていないことを確認
3. ドキュメントで参照されていないことを確認

削除時は git history で復元可能であることを確認しておく。

### 動的ロード用のエイリアス

`getattr()` で動的にロードするためのエイリアス（例: `sensor/__init__.py` の小文字エイリアス）は
後方互換性コードではなく、設計上の意図として維持する。

### 型パターンの使い分け

#### `| None` パターン

- **推奨**: オプショナルな値を表す場合は `X | None` を使用
- **非推奨**: Protocol 化しない（None 値の意味が明示的であり、Protocol 化すると複雑化）

#### isinstance チェック

- **許容**: ランタイムで型チェックが必要な場合（JSON パース、バリデーション等）
- **非推奨**: 静的型チェックのみで十分な場合は Protocol を検討

#### Union 型（3つ以上の列挙）

- **推奨**: TypeAlias で名前を付ける
- **検討**: 共通のインターフェースがあれば Protocol で統一

### dict と dataclass の使い分け

#### dataclass を使用すべき場合

- 構造が固定されている内部データ
- 複数箇所で同じキーを持つ辞書を作成している場合
- 型安全性が重要な場合

#### dict のままで良い場合

- 外部ライブラリのインターフェース
- API レスポンス（JSON 互換性が必要）
- 動的なキーを持つデータ
- インターフェース層（多数の実装に波及する場合）

### スクレイピングコードの例外処理

スクレイピングコードでは、外部サイトの変更により予期しないエラーが発生しやすい：

1. **可能な限り具体的な例外型を使用**
    - `urllib.error.URLError`, `urllib.error.HTTPError`: ネットワークエラー
    - `ValueError`: パースエラー
    - `IndexError`: 要素が見つからない場合

2. **フォールバック値を返す場合は `except Exception:` を許容**
    - 外部サイトの変更で予期しないエラーが発生する可能性があるため
    - ただし、必ず `logging.exception()` でログを出力すること

### 大規模リファクタリングの判断基準

以下の場合、リファクタリングを**見送る**：

1. **インターフェース層の変更**
    - 多数の実装クラスに波及する変更（例: センサー基底クラスの `get_value_map()` 戻り値変更）
    - 外部から呼び出される API の戻り値型変更

2. **既に動作している Protocol 設計**
    - 既存の Protocol が十分機能している場合
    - isinstance チェックがランタイム検証に必要な場合

3. **一括修正のリスク**
    - 多数箇所の例外処理変更など、影響範囲が大きい修正
    - 段階的に対応するか、新規コードから適用

### except Exception: の使用基準

1. **許容される場合**
    - スクレイピングコード（外部サイト変更への対応）
    - フォールバック値を返す場合
    - 必ず `logging.exception()` でログ出力すること

2. **避けるべき場合**
    - 新規コードでの安易な使用
    - ログ出力なしでの使用（サイレント失敗）

## 開発ワークフロー規約

### コミット時の注意

- 今回のセッションで作成し、プロジェクトが機能するのに必要なファイル以外は git add しないこと
- 気になる点がある場合は追加して良いか質問すること

### タグ作成時の注意

タグを打つ際は、必ず CHANGELOG.md を更新すること：

1. **更新タイミング**: タグを打つ前に CHANGELOG.md を更新し、コミットする
2. **記載内容**: 前回のタグからの変更内容を記載
    - 新機能（Added）
    - 変更（Changed）
    - 非推奨（Deprecated）
    - 削除（Removed）
    - バグ修正（Fixed）
    - セキュリティ修正（Security）
3. **フォーマット**: [Keep a Changelog](https://keepachangelog.com/) 形式に従う

### バグ修正の原則

- 憶測に基づいて修正しないこと
- 必ず原因を論理的に確定させた上で修正すること
- 「念のため」の修正でコードを複雑化させないこと

### コード修正時の確認事項

- 関連するテストも修正すること
- 関連するドキュメントも更新すること
- mypy, pyright, ty がパスすることを確認すること
