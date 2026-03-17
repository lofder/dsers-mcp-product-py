"""
Source URL Resolver — Normalise various product link formats.
源链接解析器 —— 标准化各种商品链接格式

Handles three resolution strategies:
  1. Direct — the URL already points to a supported supplier (e.g. AliExpress).
  2. Forced direct — the caller explicitly marks the URL as a known source.
  3. Accio best-effort — fetches the HTML of an Accio aggregator page and
     extracts the embedded supplier URL via regex.

处理三种解析策略：
  1. 直接识别 —— URL 已直接指向支持的供应商（如 AliExpress）。
  2. 强制直接 —— 调用方明确标记该 URL 为已知来源。
  3. Accio 尽力解析 —— 抓取 Accio 聚合页面的 HTML，通过正则表达式
     提取嵌入的供应商链接。
"""
from __future__ import annotations

import re
from typing import Any, Dict, List
from urllib.parse import unquote, urlparse

import httpx

# Regex patterns to match AliExpress product URLs in plain text or HTML.
# 正则表达式：在纯文本或 HTML 中匹配 AliExpress 商品链接。
ALIEXPRESS_PATTERNS = [
    re.compile(r"https?://(?:www\.)?aliexpress\.com/[^\s\"'<>]+", re.IGNORECASE),
    re.compile(r"https?://(?:[a-z]+\.)?aliexpress\.us/[^\s\"'<>]+", re.IGNORECASE),
]

# URL-encoded variant, needed when Accio pages embed links in query parameters.
# URL 编码变体，适用于 Accio 页面将链接嵌入到查询参数中的情况。
ENCODED_ALIEXPRESS_PATTERN = re.compile(
    r"https?%3A%2F%2F(?:www%2E)?aliexpress(?:%2Ecom|%2Eus)%2F[^\"'<> ]+",
    re.IGNORECASE,
)


async def resolve_source_url(source_url: str, source_hint: str) -> Dict[str, Any]:
    """
    Resolve a user-provided URL into a canonical supplier URL.
    将用户提供的 URL 解析为规范的供应商链接。

    Returns a dict with: resolved_url, source_hint, resolver_mode, warnings.
    返回字典包含：resolved_url（解析后链接）、source_hint（来源提示）、
    resolver_mode（解析模式）、warnings（警告信息）。
    """
    parsed = urlparse(source_url)
    host = (parsed.netloc or "").lower()
    warnings: List[str] = []

    # Fast path: URL is already an AliExpress link.
    # 快速路径：URL 已经是 AliExpress 链接。
    if "aliexpress." in host:
        return {
            "resolved_url": source_url,
            "source_hint": "aliexpress",
            "resolver_mode": "direct",
            "warnings": warnings,
        }

    # Caller explicitly says this is an AliExpress URL — trust them.
    # 调用方明确指定这是 AliExpress URL —— 信任调用方。
    if source_hint == "aliexpress":
        return {
            "resolved_url": source_url,
            "source_hint": "aliexpress",
            "resolver_mode": "forced_direct",
            "warnings": warnings,
        }

    # Not an Accio page either — pass through unchanged.
    # 也不是 Accio 页面 —— 原样透传。
    if "accio.com" not in host and source_hint != "accio":
        return {
            "resolved_url": source_url,
            "source_hint": source_hint or "unknown",
            "resolver_mode": "passthrough",
            "warnings": warnings,
        }

    # Accio page: fetch HTML and attempt to extract an AliExpress link.
    # Accio 页面：抓取 HTML 并尝试提取 AliExpress 链接。
    html = await _fetch_html(source_url)
    resolved = _extract_aliexpress_url(html)
    if resolved:
        warnings.append("Resolved a supplier URL from the Accio page using best-effort HTML extraction.")
        return {
            "resolved_url": resolved,
            "source_hint": "aliexpress",
            "resolver_mode": "accio_best_effort",
            "warnings": warnings,
        }

    raise ValueError("Could not resolve a supplier URL from the Accio page. Please provide a direct supplier link.")


async def _fetch_html(source_url: str) -> str:
    """
    Fetch the raw HTML of a page with a generic user-agent.
    使用通用 User-Agent 抓取页面原始 HTML。
    """
    async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
        response = await client.get(source_url, headers={"User-Agent": "Mozilla/5.0"})
        response.raise_for_status()
        return response.text


def _extract_aliexpress_url(html: str) -> str:
    """
    Best-effort regex extraction of an AliExpress URL from raw HTML.
    Falls back to URL-decoded matching if plain-text patterns fail.

    从原始 HTML 中尽力通过正则提取 AliExpress 链接。
    如果纯文本模式未命中，会回退到 URL 解码匹配。
    """
    for pattern in ALIEXPRESS_PATTERNS:
        match = pattern.search(html)
        if match:
            return match.group(0)

    encoded = ENCODED_ALIEXPRESS_PATTERN.search(html)
    if encoded:
        return unquote(encoded.group(0))

    return ""
