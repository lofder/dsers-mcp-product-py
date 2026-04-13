"""
SKU Matcher — variant-level matching between store products and candidate suppliers.
SKU 匹配器 —— 店铺商品与候选供应商之间的变体级匹配

Simplified Python port of the TypeScript sku-matcher engine.  Three signal
layers are combined into a 0-100 confidence score per variant pair:

  1. Text matching   — option-value comparison with synonym expansion
  2. Image matching   — perceptual dHash comparison (optional, requires Pillow)
  3. Price proximity   — relative price distance

匹配引擎将三个信号层合并为每对变体 0-100 的置信度分数：

  1. 文本匹配  — 选项值对比 + 同义词扩展
  2. 图像匹配  — 感知 dHash 对比（可选，需要 Pillow）
  3. 价格接近度 — 相对价格距离
"""
from __future__ import annotations

import asyncio
import re
import threading
from collections import OrderedDict
from dataclasses import dataclass, field
from io import BytesIO
from typing import Any, Dict, List, Optional, Tuple

from .logger import log

# ---------------------------------------------------------------------------
# Constants / 常量
# ---------------------------------------------------------------------------

# Score weight allocation when image data is available / 有图时的权重分配
_WEIGHT_TEXT = 0.60
_WEIGHT_IMAGE = 0.30
_WEIGHT_PRICE = 0.10

# When images are unavailable, redistribute to text / 无图时权重重新分配给文本
_WEIGHT_TEXT_NO_IMG = 0.85
_WEIGHT_PRICE_NO_IMG = 0.15

# dHash thresholds / dHash 阈值
_DHASH_PERFECT = 0
_DHASH_GOOD = 5
_DHASH_FAIR = 10
_DHASH_MAX = 15

# Image hash cache capacity / 图像哈希缓存容量
_HASH_CACHE_MAX = 200

# ---------------------------------------------------------------------------
# Synonym map / 同义词映射
# TODO(PY-P3-08): The synonym table is small and only covers basic
# size/colour abbreviations.  Consider expanding with common apparel
# and electronics terminology, or loading from an external data file.
# ---------------------------------------------------------------------------

SYNONYMS: Dict[str, str] = {
    "s": "small",
    "m": "medium",
    "l": "large",
    "xl": "extra large",
    "xxl": "2xl",
    "xxxl": "3xl",
    "blk": "black",
    "wht": "white",
    "rd": "red",
    "bl": "blue",
    "grn": "green",
}

# ---------------------------------------------------------------------------
# Dataclasses / 数据类
# ---------------------------------------------------------------------------


@dataclass
class VariantForMatch:
    """A single variant prepared for matching.
    用于匹配的单个变体。"""

    variant_ref: str
    title: str
    option_values: List[Dict[str, str]]  # [{option_name, value_name}]
    supplier_price: Optional[float] = None
    stock: Optional[int] = None
    image_url: Optional[str] = None


@dataclass
class MatchResult:
    """One matched pair with confidence and reasoning.
    一对已匹配变体及其置信度与理由。"""

    store_idx: int
    candidate_idx: int
    confidence: int  # 0-100
    reasons: List[str] = field(default_factory=list)


@dataclass
class SkuMatchOutput:
    """Full matching result across all variants.
    所有变体的完整匹配结果。"""

    matches: List[MatchResult] = field(default_factory=list)
    unmatched_store: List[int] = field(default_factory=list)
    unmatched_candidate: List[int] = field(default_factory=list)


# ---------------------------------------------------------------------------
# LRU cache for image hashes / 图像哈希 LRU 缓存
# ---------------------------------------------------------------------------


class _LRUCache:
    """Thread-safe, bounded OrderedDict-based LRU cache.
    线程安全、有容量限制的 LRU 缓存。"""

    def __init__(self, capacity: int = _HASH_CACHE_MAX) -> None:
        self._data: OrderedDict[str, str] = OrderedDict()
        self._capacity = capacity
        self._lock = threading.Lock()

    def get(self, key: str) -> Optional[str]:
        with self._lock:
            if key not in self._data:
                return None
            self._data.move_to_end(key)
            return self._data[key]

    def put(self, key: str, value: str) -> None:
        with self._lock:
            if key in self._data:
                self._data.move_to_end(key)
            self._data[key] = value
            if len(self._data) > self._capacity:
                self._data.popitem(last=False)


_hash_cache = _LRUCache()

# ---------------------------------------------------------------------------
# Pillow availability (lazy import) / Pillow 可用性（延迟导入）
# ---------------------------------------------------------------------------

_pillow_available: Optional[bool] = None


def _check_pillow() -> bool:
    """Return True if Pillow can be imported; result is cached.
    返回 Pillow 是否可用，结果会缓存。"""
    global _pillow_available
    if _pillow_available is None:
        try:
            import PIL.Image  # noqa: F401
            _pillow_available = True
        except ImportError:
            _pillow_available = False
            log.info("Pillow not installed — image matching disabled")
    return _pillow_available


# ---------------------------------------------------------------------------
# Text normalisation / 文本标准化
# ---------------------------------------------------------------------------

_PUNCT_RE = re.compile(r"[^\w\s]", re.UNICODE)


def _strip_value(raw: str) -> str:
    """Lowercase, strip whitespace, remove punctuation (no synonym expansion).
    小写、去空白、去标点（不展开同义词）。"""
    v = raw.strip().lower()
    return _PUNCT_RE.sub("", v).strip()


def _normalize_value(raw: str) -> str:
    """Lowercase, strip, remove punctuation, apply synonym map.
    小写、去空白、去标点、应用同义词映射。"""
    v = _strip_value(raw)
    return SYNONYMS.get(v, v)


# ---------------------------------------------------------------------------
# Text scoring / 文本评分
# ---------------------------------------------------------------------------


def _text_score_single(store_val: str, cand_val: str) -> Tuple[int, str]:
    """Compare two option values, return (score 0-100, reason).
    比较两个选项值，返回 (0-100 分, 原因)。"""

    # Exact match / 精确匹配
    if store_val == cand_val:
        return 100, "exact"

    s_strip = _strip_value(store_val)
    c_strip = _strip_value(cand_val)

    # Normalised match (case/whitespace/punctuation only) / 标准化匹配
    if s_strip == c_strip:
        return 90, "normalised"

    # Synonym match / 同义词匹配
    s_syn = SYNONYMS.get(s_strip, s_strip)
    c_syn = SYNONYMS.get(c_strip, c_strip)
    if s_syn == c_syn:
        return 80, "synonym"

    # Contains match (use synonym-expanded forms) / 包含匹配（使用同义词展开形式）
    if s_syn in c_syn or c_syn in s_syn:
        return 60, "contains"

    return 0, "none"


def _text_score(
    store_v: VariantForMatch,
    cand_v: VariantForMatch,
) -> Tuple[float, List[str]]:
    """Score option-value text across all dimensions.
    对所有选项维度的文本进行评分。

    Returns (normalised 0-100 score, list of reason strings).
    """
    if not store_v.option_values or not cand_v.option_values:
        # If either side has no options, fall back to title contains / 无选项时退回到标题包含
        s_title = _normalize_value(store_v.title)
        c_title = _normalize_value(cand_v.title)
        if s_title == c_title:
            return 100.0, ["title-exact"]
        if s_title in c_title or c_title in s_title:
            return 60.0, ["title-contains"]
        return 0.0, ["title-none"]

    # Build lookup from candidate / 构建候选值索引
    cand_by_opt: Dict[str, str] = {}
    for ov in cand_v.option_values:
        key = _normalize_value(ov.get("option_name", ""))
        cand_by_opt[key] = ov.get("value_name", "")

    total = 0.0
    count = 0
    reasons: List[str] = []

    for ov in store_v.option_values:
        opt_key = _normalize_value(ov.get("option_name", ""))
        store_val = ov.get("value_name", "")

        # Try matching by option name first, then best-effort / 先按选项名匹配，再最佳匹配
        cand_val = cand_by_opt.get(opt_key)
        if cand_val is not None:
            sc, reason = _text_score_single(store_val, cand_val)
            total += sc
            count += 1
            reasons.append(f"{opt_key}:{reason}({sc})")
        else:
            # Try all candidate values for best match / 对所有候选值取最佳匹配
            best_sc = 0
            best_reason = "none"
            for cv in cand_v.option_values:
                sc, reason = _text_score_single(store_val, cv.get("value_name", ""))
                if sc > best_sc:
                    best_sc = sc
                    best_reason = reason
            total += best_sc
            count += 1
            reasons.append(f"{opt_key}:{best_reason}({best_sc})")

    avg = total / count if count > 0 else 0.0
    return avg, reasons


# ---------------------------------------------------------------------------
# dHash image matching / dHash 图像匹配
# ---------------------------------------------------------------------------


async def _compute_dhash(image_url: str) -> Optional[str]:
    """Download image, resize to 9x8, compute difference hash.
    下载图像，缩放至 9x8，计算差异哈希。

    Returns a 64-character binary string or None on failure.
    """
    if not _check_pillow():
        return None

    # Validate URL to prevent SSRF
    from .security import validate_url
    try:
        validate_url(image_url)
    except ValueError:
        return None

    cached = _hash_cache.get(image_url)
    if cached is not None:
        return cached

    try:
        import httpx
        import PIL.Image

        # Download with httpx (async, non-blocking)
        # 使用 httpx 下载（异步，非阻塞）
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                image_url,
                headers={"User-Agent": "dsers-sku-matcher/1.0"},
            )
            resp.raise_for_status()
            img_bytes = resp.content

        # Pillow image processing is CPU-bound — run in executor
        # Pillow 图像处理是 CPU 密集型操作 —— 在执行器中运行
        def _compute_hash(data: bytes) -> Optional[str]:
            try:
                img = PIL.Image.open(BytesIO(data)).convert("L")  # grayscale
                img = img.resize((9, 8), PIL.Image.LANCZOS)
                pixels = list(img.getdata())

                bits: List[str] = []
                for row in range(8):
                    for col in range(8):
                        idx = row * 9 + col
                        bits.append("1" if pixels[idx] > pixels[idx + 1] else "0")

                return "".join(bits)
            except Exception as exc:
                log.debug("dHash image processing failed", {"url": image_url, "err": str(exc)})
                return None

        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, _compute_hash, img_bytes)
        if result is not None:
            _hash_cache.put(image_url, result)
        return result

    except Exception as exc:
        log.debug("dHash computation error", {"url": image_url, "err": str(exc)})
        return None


def _hamming_distance(h1: str, h2: str) -> int:
    """Hamming distance between two equal-length binary strings.
    两个等长二进制字符串之间的汉明距离。"""
    return sum(c1 != c2 for c1, c2 in zip(h1, h2))


def _image_score_from_distance(dist: int) -> float:
    """Map hamming distance to 0-100 score with linear interpolation.
    将汉明距离映射为 0-100 分（线性插值）。"""
    if dist <= _DHASH_PERFECT:
        return 100.0
    if dist <= _DHASH_GOOD:
        # 100 -> 75 over distance 0..5
        return 100.0 - (dist / _DHASH_GOOD) * 25.0
    if dist <= _DHASH_FAIR:
        # 75 -> 50 over distance 5..10
        return 75.0 - ((dist - _DHASH_GOOD) / (_DHASH_FAIR - _DHASH_GOOD)) * 25.0
    if dist <= _DHASH_MAX:
        # 50 -> 0 over distance 10..15
        return 50.0 - ((dist - _DHASH_FAIR) / (_DHASH_MAX - _DHASH_FAIR)) * 50.0
    return 0.0


# ---------------------------------------------------------------------------
# Price scoring / 价格评分
# ---------------------------------------------------------------------------


def _price_score(
    store_price: Optional[float],
    cand_price: Optional[float],
) -> Tuple[float, str]:
    """Compare two supplier prices, return (0-100 score, reason).
    比较两个供应商价格，返回 (0-100 分, 原因)。"""
    if store_price is None or cand_price is None:
        return 0.0, "no-price"
    if store_price <= 0 and cand_price <= 0:
        return 100.0, "both-zero"

    avg = (store_price + cand_price) / 2.0
    if avg == 0:
        return 0.0, "zero-avg"

    diff_ratio = abs(store_price - cand_price) / avg
    if diff_ratio <= 0.20:
        return 100.0, "within-20pct"
    if diff_ratio <= 0.50:
        # Linear 100 -> 50 between 20% and 50% difference
        return 100.0 - ((diff_ratio - 0.20) / 0.30) * 50.0, "within-50pct"
    return 0.0, "too-far"


# ---------------------------------------------------------------------------
# Pair scoring / 配对评分
# ---------------------------------------------------------------------------


async def _score_pair(
    store_v: VariantForMatch,
    cand_v: VariantForMatch,
) -> Tuple[int, List[str]]:
    """Compute a 0-100 confidence score for a (store, candidate) pair.
    为一对（店铺变体, 候选变体）计算 0-100 置信度分数。

    Returns (confidence int, list of reason strings).
    """
    reasons: List[str] = []

    # --- Text ---
    text_raw, text_reasons = _text_score(store_v, cand_v)
    reasons.extend(text_reasons)

    # --- Image ---
    has_images = False
    image_raw = 0.0
    if store_v.image_url and cand_v.image_url and _check_pillow():
        h1, h2 = await asyncio.gather(
            _compute_dhash(store_v.image_url),
            _compute_dhash(cand_v.image_url),
        )
        if h1 is not None and h2 is not None:
            dist = _hamming_distance(h1, h2)
            image_raw = _image_score_from_distance(dist)
            has_images = True
            reasons.append(f"img:dist={dist}({image_raw:.0f})")

    # --- Price ---
    price_raw, price_reason = _price_score(store_v.supplier_price, cand_v.supplier_price)
    if price_reason != "no-price":
        reasons.append(f"price:{price_reason}({price_raw:.0f})")

    # --- Weighted combination / 加权组合 ---
    if has_images:
        score = (
            text_raw * _WEIGHT_TEXT
            + image_raw * _WEIGHT_IMAGE
            + price_raw * _WEIGHT_PRICE
        )
    else:
        score = (
            text_raw * _WEIGHT_TEXT_NO_IMG
            + price_raw * _WEIGHT_PRICE_NO_IMG
        )

    confidence = max(0, min(100, round(score)))
    return confidence, reasons


# ---------------------------------------------------------------------------
# Main entry point / 主入口
# ---------------------------------------------------------------------------


async def match_variants(
    store_variants: List[VariantForMatch],
    candidate_variants: List[VariantForMatch],
    auto_confidence: int = 50,
) -> SkuMatchOutput:
    """Match store variants to candidate variants using greedy assignment.
    使用贪婪分配将店铺变体与候选变体进行匹配。

    1. Build an N x M score matrix.
    2. Sort all pairs by descending score.
    3. Greedily assign pairs where score >= *auto_confidence*.

    Args:
        store_variants: variants currently on the store product.
        candidate_variants: variants from the new supplier.
        auto_confidence: minimum score for auto-matching (0-100).

    Returns:
        SkuMatchOutput with matches, unmatched_store, unmatched_candidate.
    """
    n_store = len(store_variants)
    n_cand = len(candidate_variants)

    if n_store == 0 or n_cand == 0:
        return SkuMatchOutput(
            matches=[],
            unmatched_store=list(range(n_store)),
            unmatched_candidate=list(range(n_cand)),
        )

    log.debug(
        "Building score matrix",
        {"store": n_store, "candidate": n_cand, "threshold": auto_confidence},
    )

    # --- Build score matrix (all pairs concurrently) / 构建分数矩阵（所有配对并发） ---
    from .concurrency import p_limit
    limit = p_limit(10)

    tasks: List[Any] = []
    indices: List[Tuple[int, int]] = []
    for si in range(n_store):
        for ci in range(n_cand):
            tasks.append(limit(lambda _si=si, _ci=ci: _score_pair(store_variants[_si], candidate_variants[_ci])))
            indices.append((si, ci))

    results = await asyncio.gather(*tasks)

    # Flatten into sortable list / 展平为可排序列表
    scored: List[Tuple[int, int, int, List[str]]] = []
    for (si, ci), (conf, reasons) in zip(indices, results):
        scored.append((si, ci, conf, reasons))

    # Sort descending by confidence / 按置信度降序排列
    scored.sort(key=lambda x: x[2], reverse=True)

    # --- Greedy assignment / 贪婪分配 ---
    matched_store: set = set()
    matched_cand: set = set()
    matches: List[MatchResult] = []

    for si, ci, conf, reasons in scored:
        if conf < auto_confidence:
            break  # remaining pairs are below threshold / 剩余配对低于阈值
        if si in matched_store or ci in matched_cand:
            continue
        matches.append(MatchResult(
            store_idx=si,
            candidate_idx=ci,
            confidence=conf,
            reasons=reasons,
        ))
        matched_store.add(si)
        matched_cand.add(ci)

    unmatched_store = [i for i in range(n_store) if i not in matched_store]
    unmatched_cand = [i for i in range(n_cand) if i not in matched_cand]

    log.debug(
        "Matching complete",
        {
            "matched": len(matches),
            "unmatched_store": len(unmatched_store),
            "unmatched_candidate": len(unmatched_cand),
        },
    )

    return SkuMatchOutput(
        matches=matches,
        unmatched_store=unmatched_store,
        unmatched_candidate=unmatched_cand,
    )
