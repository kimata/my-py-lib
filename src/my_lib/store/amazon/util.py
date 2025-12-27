#!/usr/bin/env python3
"""
Amazon ユーティリティ関数
"""

AMAZON_JP_BASE_URL = "https://www.amazon.co.jp"


def get_item_url(asin: str) -> str:
    """ASIN から Amazon 商品ページの URL を生成

    Args:
        asin: Amazon Standard Identification Number

    Returns:
        商品ページの URL
    """
    return f"{AMAZON_JP_BASE_URL}/dp/{asin}"
