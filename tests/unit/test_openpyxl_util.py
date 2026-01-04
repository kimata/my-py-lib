#!/usr/bin/env python3
# ruff: noqa: S101
"""openpyxl_util.py のテスト"""

from __future__ import annotations

import unittest.mock
from typing import Any

import pytest

openpyxl = pytest.importorskip("openpyxl")

import my_lib.openpyxl_util  # noqa: E402


class TestGenTextPos:
    """_gen_text_pos 関数のテスト"""

    def test_returns_a1_for_row1_col1(self):
        """行1、列1 で A1 を返す"""
        result = my_lib.openpyxl_util._gen_text_pos(1, 1)
        assert result == "A1"

    def test_returns_b2_for_row2_col2(self):
        """行2、列2 で B2 を返す"""
        result = my_lib.openpyxl_util._gen_text_pos(2, 2)
        assert result == "B2"

    def test_returns_z10_for_row10_col26(self):
        """行10、列26 で Z10 を返す"""
        result = my_lib.openpyxl_util._gen_text_pos(10, 26)
        assert result == "Z10"


class TestSetHeaderCellStyle:
    """_set_header_cell_style 関数のテスト"""

    def test_sets_cell_value(self):
        """セルに値を設定する"""
        wb = openpyxl.Workbook()
        ws = wb.active

        style = {
            "border": openpyxl.styles.Border(),
            "fill": openpyxl.styles.PatternFill(),
        }

        my_lib.openpyxl_util._set_header_cell_style(ws, 1, 1, "Test", None, style)

        assert ws.cell(1, 1).value == "Test"

    def test_sets_column_width(self):
        """列幅を設定する"""
        wb = openpyxl.Workbook()
        ws = wb.active

        style = {
            "border": openpyxl.styles.Border(),
            "fill": openpyxl.styles.PatternFill(),
        }

        my_lib.openpyxl_util._set_header_cell_style(ws, 1, 1, "Test", 20.0, style)

        assert ws.column_dimensions["A"].width == 20.0


class TestGenItemCellStyle:
    """_gen_item_cell_style 関数のテスト"""

    def test_copies_base_style(self):
        """ベーススタイルをコピーする"""
        base_style = {"border": "test_border", "fill": "test_fill"}
        cell_def = {}

        result = my_lib.openpyxl_util._gen_item_cell_style(base_style, cell_def)

        assert result["border"] == "test_border"
        assert result["fill"] == "test_fill"

    def test_adds_format(self):
        """フォーマットを追加する"""
        base_style = {}
        cell_def = {"format": "0.00"}

        result = my_lib.openpyxl_util._gen_item_cell_style(base_style, cell_def)

        assert result["text_format"] == "0.00"

    def test_adds_wrap(self):
        """ラップを追加する"""
        base_style = {}
        cell_def = {"wrap": True}

        result = my_lib.openpyxl_util._gen_item_cell_style(base_style, cell_def)

        assert result["text_wrap"] is True

    def test_default_wrap_is_false(self):
        """デフォルトのラップは False"""
        base_style = {}
        cell_def = {}

        result = my_lib.openpyxl_util._gen_item_cell_style(base_style, cell_def)

        assert result["text_wrap"] is False


class TestSetItemCellStyle:
    """_set_item_cell_style 関数のテスト"""

    def test_sets_cell_value(self):
        """セルに値を設定する"""
        wb = openpyxl.Workbook()
        ws = wb.active

        style = {
            "border": openpyxl.styles.Border(),
            "text_wrap": False,
        }

        my_lib.openpyxl_util._set_item_cell_style(ws, 1, 1, "Test Value", style)

        assert ws.cell(1, 1).value == "Test Value"

    def test_sets_number_format(self):
        """数値フォーマットを設定する"""
        wb = openpyxl.Workbook()
        ws = wb.active

        style = {
            "border": openpyxl.styles.Border(),
            "text_wrap": False,
            "text_format": "#,##0",
        }

        my_lib.openpyxl_util._set_item_cell_style(ws, 1, 1, 1000, style)

        assert ws.cell(1, 1).number_format == "#,##0"


class TestInsertTableHeader:
    """_insert_table_header 関数のテスト"""

    def test_inserts_simple_header(self):
        """シンプルなヘッダーを挿入する"""
        wb = openpyxl.Workbook()
        ws = wb.active

        sheet_def = {
            "TABLE_HEADER": {
                "col": {
                    "name": {"pos": 1, "label": "Name", "width": 20},
                }
            }
        }
        base_style = {
            "border": openpyxl.styles.Border(),
            "fill": openpyxl.styles.PatternFill(),
        }

        my_lib.openpyxl_util._insert_table_header(ws, 1, sheet_def, base_style)

        assert ws.cell(1, 1).value == "Name"

    def test_inserts_category_headers(self):
        """カテゴリーヘッダーを挿入する"""
        wb = openpyxl.Workbook()
        ws = wb.active

        sheet_def = {
            "TABLE_HEADER": {
                "col": {
                    "category": {"pos": 1, "label": "Category", "length": 3},
                }
            }
        }
        base_style = {
            "border": openpyxl.styles.Border(),
            "fill": openpyxl.styles.PatternFill(),
        }

        my_lib.openpyxl_util._insert_table_header(ws, 1, sheet_def, base_style)

        assert ws.cell(1, 1).value == "Category (1)"
        assert ws.cell(1, 2).value == "Category (2)"
        assert ws.cell(1, 3).value == "Category (3)"


class TestInsertTableCellImage:
    """_insert_table_cell_image 関数のテスト"""

    def test_does_nothing_for_none_path(self):
        """パスが None の場合は何もしない"""
        wb = openpyxl.Workbook()
        ws = wb.active

        my_lib.openpyxl_util._insert_table_cell_image(ws, 1, 1, None, 100, 100)

    def test_does_nothing_for_nonexistent_path(self, temp_dir):
        """存在しないパスの場合は何もしない"""
        wb = openpyxl.Workbook()
        ws = wb.active

        nonexistent = temp_dir / "nonexistent.png"

        my_lib.openpyxl_util._insert_table_cell_image(ws, 1, 1, nonexistent, 100, 100)


class TestSettingTableView:
    """_setting_table_view 関数のテスト"""

    def test_sets_freeze_panes(self):
        """フリーズペインを設定する"""
        wb = openpyxl.Workbook()
        ws = wb.active

        sheet_def = {
            "TABLE_HEADER": {
                "row": {"pos": 1},
                "col": {
                    "price": {"pos": 2},
                    "image": {"pos": 1},
                    "name": {"pos": 3},
                },
            }
        }

        my_lib.openpyxl_util._setting_table_view(ws, sheet_def, 10, False)

        assert ws.freeze_panes == "C2"

    def test_sets_auto_filter(self):
        """オートフィルターを設定する"""
        wb = openpyxl.Workbook()
        ws = wb.active

        sheet_def = {
            "TABLE_HEADER": {
                "row": {"pos": 1},
                "col": {
                    "price": {"pos": 2},
                    "image": {"pos": 1},
                    "name": {"pos": 3},
                },
            }
        }

        my_lib.openpyxl_util._setting_table_view(ws, sheet_def, 10, False)

        assert ws.auto_filter.ref is not None


class TestInsertTableItem:
    """_insert_table_item 関数のテスト"""

    def test_calls_warning_handler_for_missing_key(self):
        """キーが存在しない場合に warning_handler が呼ばれる"""
        wb = openpyxl.Workbook()
        ws = wb.active

        sheet_def = {
            "TABLE_HEADER": {
                "col": {
                    "name": {"pos": 1, "label": "Name"},
                    "missing_key": {"pos": 2, "label": "Missing"},
                },
                "row": {"height": {"default": 50}},
            }
        }
        base_style = {
            "border": openpyxl.styles.Border(),
            "fill": openpyxl.styles.PatternFill(),
        }

        item = {"name": "Test Item"}
        warnings_received: list[tuple[Any, str]] = []

        def warning_handler(item: Any, message: str) -> None:
            warnings_received.append((item, message))

        my_lib.openpyxl_util._insert_table_item(
            ws, 1, item, False, None, sheet_def, base_style, warning_handler
        )

        assert len(warnings_received) == 1
        assert warnings_received[0][0] is item
        assert "missing_key" in warnings_received[0][1]

    def test_calls_logging_warning_when_no_handler(self):
        """warning_handler がない場合は logging.warning が呼ばれる"""
        wb = openpyxl.Workbook()
        ws = wb.active

        sheet_def = {
            "TABLE_HEADER": {
                "col": {
                    "name": {"pos": 1, "label": "Name"},
                    "missing_key": {"pos": 2, "label": "Missing"},
                },
                "row": {"height": {"default": 50}},
            }
        }
        base_style = {
            "border": openpyxl.styles.Border(),
            "fill": openpyxl.styles.PatternFill(),
        }

        item = {"name": "Test Item"}

        with unittest.mock.patch("my_lib.openpyxl_util.logging") as mock_logging:
            my_lib.openpyxl_util._insert_table_item(ws, 1, item, False, None, sheet_def, base_style, None)

            mock_logging.warning.assert_called()
            call_args = mock_logging.warning.call_args[0][0]
            assert "missing_key" in call_args

    def test_calls_warning_handler_for_missing_formal_key(self):
        """formal_key が存在しない場合に warning_handler が呼ばれる"""
        wb = openpyxl.Workbook()
        ws = wb.active

        sheet_def = {
            "TABLE_HEADER": {
                "col": {
                    "display_name": {"pos": 1, "label": "Name", "formal_key": "actual_name"},
                },
                "row": {"height": {"default": 50}},
            }
        }
        base_style = {
            "border": openpyxl.styles.Border(),
            "fill": openpyxl.styles.PatternFill(),
        }

        item = {"other_key": "value"}
        warnings_received: list[tuple[Any, str]] = []

        def warning_handler(item: Any, message: str) -> None:
            warnings_received.append((item, message))

        my_lib.openpyxl_util._insert_table_item(
            ws, 1, item, False, None, sheet_def, base_style, warning_handler
        )

        assert len(warnings_received) == 1
        assert "formal_key" in warnings_received[0][1]
        assert "actual_name" in warnings_received[0][1]


class TestGenerateListSheet:
    """generate_list_sheet 関数のテスト"""

    def test_creates_sheet(self):
        """シートを作成する"""
        wb = openpyxl.Workbook()

        sheet_def = {
            "SHEET_TITLE": "Test",
            "TABLE_HEADER": {
                "row": {
                    "pos": 1,
                    "height": {"default": 50, "without_thumb": 20},
                },
                "col": {
                    "name": {"pos": 1, "label": "Name"},
                    "price": {"pos": 2, "label": "Price"},
                    "image": {"pos": 3, "label": "Image", "width": 100},
                },
            },
        }

        item_list: list[Any] = [{"name": "Item1", "price": 100}]

        def thumb_path_func(item):
            return None

        def set_status_func(status):
            pass

        def update_func():
            pass

        result = my_lib.openpyxl_util.generate_list_sheet(
            wb,
            item_list,
            sheet_def,
            is_need_thumb=False,
            thumb_path_func=thumb_path_func,
            set_status_func=set_status_func,
            update_seq_func=update_func,
            update_item_func=update_func,
        )

        assert result.title == "Testアイテム一覧"

    def test_passes_warning_handler_to_insert_table_item(self):
        """warning_handler が _insert_table_item に渡される"""
        wb = openpyxl.Workbook()

        sheet_def = {
            "SHEET_TITLE": "Test",
            "TABLE_HEADER": {
                "row": {
                    "pos": 1,
                    "height": {"default": 50, "without_thumb": 20},
                },
                "col": {
                    "name": {"pos": 1, "label": "Name"},
                    "missing_field": {"pos": 2, "label": "Missing"},
                    "price": {"pos": 3, "label": "Price"},
                    "image": {"pos": 4, "label": "Image", "width": 100},
                },
            },
        }

        item_list: list[Any] = [{"name": "Item1", "price": 100}]
        warnings_received: list[tuple[Any, str]] = []

        def warning_handler(item: Any, message: str) -> None:
            warnings_received.append((item, message))

        def thumb_path_func(item):
            return None

        def set_status_func(status):
            pass

        def update_func():
            pass

        my_lib.openpyxl_util.generate_list_sheet(
            wb,
            item_list,
            sheet_def,
            is_need_thumb=False,
            thumb_path_func=thumb_path_func,
            set_status_func=set_status_func,
            update_seq_func=update_func,
            update_item_func=update_func,
            warning_handler=warning_handler,
        )

        assert len(warnings_received) == 1
        assert "missing_field" in warnings_received[0][1]
