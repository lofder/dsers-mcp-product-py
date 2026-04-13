"""
SKU Remap Service -- orchestrate variant-level supplier replacement.

Simplified Python port of the TypeScript sku-mapping.ts orchestrator.
Coordinates the SKU remap workflow:

  1. Read current mapping for the target product
  2. Path A (strict): import the caller-provided supplier URL as candidate
     Path B (discover): reverse-image search to find the best replacement
  3. Run sku-matcher to build per-variant diffs
  4. preview: return diff + summary; apply: persist the mapping change
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_AUTO_CONFIDENCE = 70
DEFAULT_MAX_CANDIDATES = 5
SEED_IMAGE_LIMIT = 4
ALIEXPRESS_APP_ID = 159831080


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

async def sku_remap(
    provider: Any,
    store: Any,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Replace the supplier on a store product with SKU-level variant matching.

    Two paths:
    - Path A (strict): caller provides new_supplier_url -> import that exact
      supplier.
    - Path B (discover): caller omits new_supplier_url -> reverse-image search
      to find the best replacement.

    Two modes:
    - preview (default): read-only, returns diff + summary.
    - apply: persists the mapping change to DSers.

    Args:
        provider: ImportProvider instance (exposes get_mapping,
            prepare_candidate, find_products, get_pool_product_detail,
            save_mapping).
        store: FileJobStore instance (unused in the current skeleton but kept
            for interface parity with ImportFlowService).
        params: Dict with dsers_product_id, store_id, new_supplier_url (opt),
            mode, country, auto_confidence, max_candidates.

    Returns:
        Dict with path, summary, diffs, warnings, and optionally discovery
        and process_status.
    """
    dsers_product_id: str = str(params.get("dsers_product_id") or "").strip()
    store_id: str = str(params.get("store_id") or "").strip()
    if not dsers_product_id:
        raise ValueError("dsers_product_id is required")
    if not store_id:
        raise ValueError("store_id is required")

    mode: str = str(params.get("mode") or "preview").strip()
    auto_confidence: int = int(params.get("auto_confidence", DEFAULT_AUTO_CONFIDENCE))
    country: str = str(params.get("country") or "US").strip() or "US"
    max_candidates: int = int(params.get("max_candidates", DEFAULT_MAX_CANDIDATES))

    # ------------------------------------------------------------------
    # 1. Read current mapping
    # ------------------------------------------------------------------
    mapping: Dict[str, Any] = await provider.get_mapping(dsers_product_id)
    current_variants: List[Dict[str, Any]] = _extract_current_variants(mapping)
    if not current_variants:
        return {"error": "Current product has no variants in its mapping."}

    # Lazy import -- sku_matcher is a sibling module that may pull heavier
    # dependencies; import only when we actually need it.
    from .sku_matcher import match_variants

    candidate_variants: List[Dict[str, Any]] = []
    top_candidates: Optional[List[Dict[str, Any]]] = None

    if params.get("new_supplier_url"):
        # ==============================================================
        # Path A: strict -- import the provided URL as the sole candidate
        # ==============================================================
        path = "A_strict"
        candidate = await provider.prepare_candidate(
            source_url=str(params["new_supplier_url"]),
            source_hint="auto",
            country=country,
        )
        candidate_variants = _extract_candidate_variants(candidate.get("draft") or {})
        if not candidate_variants:
            return {"path": path, "error": "Candidate supplier has no usable variants."}

        match_output = await match_variants(current_variants, candidate_variants, auto_confidence)
    else:
        # ==============================================================
        # Path B: discover -- search by image, rank candidates
        # ==============================================================
        path = "B_discover"
        seed_images = _get_seed_images(mapping)
        if not seed_images:
            return {"error": "No images found on current product for reverse-image search."}

        search_result = await provider.find_products({
            "image_url": seed_images[0],
            "limit": max_candidates,
        })
        candidates: List[Dict[str, Any]] = search_result.get("items") or []

        if not candidates:
            return {
                "path": path,
                "error": "Image search returned no candidates.",
                "top_candidates": [],
            }

        best_match: Optional[Any] = None
        best_score: float = 0
        best_candidate_variants: List[Dict[str, Any]] = []
        top_candidates = []

        for cand in candidates:
            try:
                product_id = str(cand.get("product_id") or "")
                app_id = int(cand.get("app_id") or ALIEXPRESS_APP_ID)
                detail = await provider.get_pool_product_detail(product_id, app_id, country)
                cand_variants = _extract_candidate_variants(detail)
                if not cand_variants:
                    continue

                m_output = await match_variants(current_variants, cand_variants, auto_confidence)
                avg = _avg_confidence(m_output)

                top_candidates.append({
                    "product_id": product_id,
                    "title": cand.get("title", ""),
                    "avg_score": avg,
                    "matched": len(m_output.matches),
                    "unmatched": len(m_output.unmatched_store),
                })

                if avg > best_score:
                    best_score = avg
                    best_match = m_output
                    best_candidate_variants = cand_variants
            except Exception:
                continue

        if best_match is None:
            return {
                "path": path,
                "error": "No suitable candidate found.",
                "top_candidates": top_candidates,
            }
        match_output = best_match
        candidate_variants = best_candidate_variants

    # ------------------------------------------------------------------
    # 3. Build per-variant diffs
    # ------------------------------------------------------------------
    diffs = _build_diffs(current_variants, candidate_variants, match_output, auto_confidence)

    summary = {
        "swapped": sum(1 for d in diffs if d["decision"] == "swapped"),
        "kept_old": sum(1 for d in diffs if d["decision"] == "kept_old"),
        "unmatched": sum(1 for d in diffs if d["decision"] == "unmatched"),
    }

    result: Dict[str, Any] = {
        "path": path,
        "summary": summary,
        "diffs": diffs,
        "warnings": [],
    }
    if top_candidates is not None:
        result["discovery"] = {"top_candidates": top_candidates}

    # ------------------------------------------------------------------
    # 4. Apply if requested
    # ------------------------------------------------------------------
    if mode == "apply":
        try:
            payload = _build_mapping_payload(mapping, diffs, candidate_variants)
            save_result = await provider.save_mapping(dsers_product_id, payload)
            result["process_status"] = save_result.get("status", "requested")
        except Exception as exc:
            result["errors"] = [str(exc)]

    return result


# ---------------------------------------------------------------------------
# Helper: extract current variants from mapping response
# ---------------------------------------------------------------------------

def _extract_current_variants(mapping: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Extract a list of variant dicts from the raw mapping response.

    The mapping API returns nested structures; we normalise each variant to:
      {
        "variant_ref": str,      -- unique id for this seller variant
        "title": str,            -- option label / variant title
        "option_values": list,   -- [{optionName, valueName}, ...]
        "supplier_price": float | None,
        "stock": int | None,
        "image_url": str,
        "supply_product_id": str,
        "supply_variant_id": str,
      }
    """
    data = mapping.get("data") or mapping
    raw_mapping: List[Dict[str, Any]] = data.get("mapping") or []

    variants: List[Dict[str, Any]] = []
    for entry in raw_mapping:
        # Each mapping entry represents one seller variant
        variant_ref = str(entry.get("sellerVariantId") or entry.get("variant_id") or "")
        if not variant_ref:
            continue

        option_values: List[Dict[str, str]] = []
        for opt in (entry.get("options") or []):
            option_values.append({
                "optionName": str(opt.get("optionName") or ""),
                "valueName": str(opt.get("valueName") or ""),
            })

        title = str(entry.get("sellerVariantTitle") or entry.get("title") or "")
        if not title and option_values:
            title = " / ".join(ov["valueName"] for ov in option_values if ov["valueName"])

        variants.append({
            "variant_ref": variant_ref,
            "title": title,
            "option_values": option_values,
            "supplier_price": _safe_float(entry.get("supplierPrice") or entry.get("cost")),
            "stock": _safe_int(entry.get("stock") or entry.get("quantity")),
            "image_url": str(entry.get("imgUrl") or entry.get("image_url") or ""),
            "supply_product_id": str(entry.get("supplyProductId") or ""),
            "supply_variant_id": str(entry.get("supplyVariantId") or ""),
        })

    return variants


# ---------------------------------------------------------------------------
# Helper: extract candidate variants from import draft / pool detail
# ---------------------------------------------------------------------------

def _extract_candidate_variants(draft: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Extract a list of variant dicts from an import draft or pool product detail.

    Normalises each variant to the same shape as _extract_current_variants for
    the matcher.
    """
    data = draft.get("data") or draft
    raw_variants: List[Dict[str, Any]] = data.get("variants") or []

    variants: List[Dict[str, Any]] = []
    for v in raw_variants:
        variant_ref = str(
            v.get("variantId")
            or v.get("variant_id")
            or v.get("sku_id")
            or ""
        )
        if not variant_ref:
            continue

        option_values: List[Dict[str, str]] = []
        for opt in (v.get("options") or []):
            option_values.append({
                "optionName": str(opt.get("optionName") or opt.get("option_name") or ""),
                "valueName": str(opt.get("valueName") or opt.get("value_name") or ""),
            })

        title = str(v.get("title") or v.get("variant_title") or "")
        if not title and option_values:
            title = " / ".join(ov["valueName"] for ov in option_values if ov["valueName"])

        variants.append({
            "variant_ref": variant_ref,
            "title": title,
            "option_values": option_values,
            "supplier_price": _safe_float(v.get("cost") or v.get("supplier_price")),
            "stock": _safe_int(v.get("stock") or v.get("quantity")),
            "image_url": str(v.get("imgUrl") or v.get("image_url") or ""),
        })

    return variants


# ---------------------------------------------------------------------------
# Helper: seed images for reverse-image search (Path B)
# ---------------------------------------------------------------------------

def _get_seed_images(mapping: Dict[str, Any]) -> List[str]:
    """
    Collect up to SEED_IMAGE_LIMIT product-level and variant-level images
    from the current product for reverse-image search.
    """
    images: List[str] = []
    data = mapping.get("data") or mapping

    # Product-level main image
    main_img = str(data.get("mainImgUrl") or data.get("image") or "").strip()
    if main_img:
        images.append(main_img)

    # Additional product images (medias)
    for media in (data.get("medias") or data.get("images") or []):
        url = str(media if isinstance(media, str) else (media.get("url") or "")).strip()
        if url and url not in images:
            images.append(url)
        if len(images) >= SEED_IMAGE_LIMIT:
            return images

    # Variant-level images as fallback seeds
    for entry in (data.get("mapping") or []):
        url = str(entry.get("imgUrl") or entry.get("image_url") or "").strip()
        if url and url not in images:
            images.append(url)
        if len(images) >= SEED_IMAGE_LIMIT:
            break

    return images


# ---------------------------------------------------------------------------
# Helper: average match confidence
# ---------------------------------------------------------------------------

def _avg_confidence(match_output: Any) -> float:
    """
    Compute the average confidence across all matched pairs.

    The match_output is a SkuMatchOutput dataclass with a ``matches`` list
    where each entry has a ``confidence`` attribute.  Falls back to 0.0
    when there are no matches.
    """
    matches = match_output.matches
    if not matches:
        return 0.0
    total = sum(float(m.confidence) for m in matches)
    return total / len(matches)


# ---------------------------------------------------------------------------
# Helper: build per-variant diffs
# ---------------------------------------------------------------------------

def _build_diffs(
    current: List[Dict[str, Any]],
    candidate: List[Dict[str, Any]],
    match_output: Any,
    threshold: int,
) -> List[Dict[str, Any]]:
    """
    Build per-variant decision diffs.

    For each current (store) variant, decide:
      - swapped:   confident match found above threshold
      - kept_old:  match found but below threshold; keep existing supplier
      - unmatched: no match at all

    match_output is a SkuMatchOutput dataclass with:
      - matches: List[MatchResult]  (each has store_idx, candidate_idx, confidence, reasons)
      - unmatched_store: List[int]  (indices into current)
      - unmatched_candidate: List[int]
    """
    matches = match_output.matches
    unmatched_store_indices: set = set(match_output.unmatched_store)

    # Index matches by store variant index for quick lookup
    match_by_store_idx: Dict[int, Any] = {}
    for m in matches:
        match_by_store_idx[m.store_idx] = m

    # Index candidate variants by ref
    cand_by_ref: Dict[str, Dict[str, Any]] = {}
    for cv in candidate:
        cand_by_ref[cv["variant_ref"]] = cv

    diffs: List[Dict[str, Any]] = []
    for idx, sv in enumerate(current):
        ref = sv["variant_ref"]
        m = match_by_store_idx.get(idx)

        if m is None or idx in unmatched_store_indices:
            diffs.append({
                "index": idx,
                "variant_ref": ref,
                "title": sv.get("title", ""),
                "decision": "unmatched",
                "confidence": None,
                "before": {
                    "supply_product_id": sv.get("supply_product_id", ""),
                    "supply_variant_id": sv.get("supply_variant_id", ""),
                },
                "after": None,
                "reasons": ["no_match"],
            })
            continue

        confidence = float(m.confidence)
        matched_cand_idx = m.candidate_idx
        matched_cand_variant = candidate[matched_cand_idx] if matched_cand_idx < len(candidate) else {}
        matched_ref = matched_cand_variant.get("variant_ref", "")
        matched_cand = cand_by_ref.get(matched_ref, {})

        if confidence >= threshold:
            diffs.append({
                "index": idx,
                "variant_ref": ref,
                "title": sv.get("title", ""),
                "decision": "swapped",
                "confidence": confidence,
                "before": {
                    "supply_product_id": sv.get("supply_product_id", ""),
                    "supply_variant_id": sv.get("supply_variant_id", ""),
                },
                "after": {
                    "supply_variant_id": matched_ref,
                    "supply_variant_title": matched_cand.get("title", ""),
                    "supplier_price": matched_cand.get("supplier_price"),
                },
                "reasons": m.reasons or [],
            })
        else:
            diffs.append({
                "index": idx,
                "variant_ref": ref,
                "title": sv.get("title", ""),
                "decision": "kept_old",
                "confidence": confidence,
                "before": {
                    "supply_product_id": sv.get("supply_product_id", ""),
                    "supply_variant_id": sv.get("supply_variant_id", ""),
                },
                "after": None,
                "reasons": (m.reasons or []) + [f"below_threshold({threshold})"],
            })

    return diffs


# ---------------------------------------------------------------------------
# Helper: build the mapping payload for DSers API
# ---------------------------------------------------------------------------

def _build_mapping_payload(
    mapping: Dict[str, Any],
    diffs: List[Dict[str, Any]],
    candidate_variants: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Build the mapping payload to POST to DSers.

    Only variants with decision='swapped' get their supplier info replaced;
    all others retain the existing mapping entry unchanged.
    """
    data = mapping.get("data") or mapping
    original_mapping: List[Dict[str, Any]] = data.get("mapping") or []

    # Index diffs by variant_ref for lookup
    diff_by_ref: Dict[str, Dict[str, Any]] = {}
    for d in diffs:
        diff_by_ref[d["variant_ref"]] = d

    # Index candidate variants by ref
    cand_by_ref: Dict[str, Dict[str, Any]] = {}
    for cv in candidate_variants:
        cand_by_ref[cv["variant_ref"]] = cv

    new_mapping: List[Dict[str, Any]] = []
    for entry in original_mapping:
        ref = str(entry.get("sellerVariantId") or entry.get("variant_id") or "")
        diff = diff_by_ref.get(ref)

        if diff is not None and diff["decision"] == "swapped" and diff.get("after"):
            # Replace supplier info on this variant
            updated = dict(entry)
            after = diff["after"]
            matched_ref = str(after.get("supply_variant_id") or "")
            matched_cand = cand_by_ref.get(matched_ref, {})

            updated["supplyVariantId"] = matched_ref
            updated["supplyVariantTitle"] = str(after.get("supply_variant_title") or "")
            if matched_cand.get("supplier_price") is not None:
                updated["supplierPrice"] = matched_cand["supplier_price"]
            if matched_cand.get("stock") is not None:
                updated["stock"] = matched_cand["stock"]

            # Carry over candidate option values if available
            if matched_cand.get("option_values"):
                updated["supplyOptions"] = [
                    {
                        "optionName": ov.get("optionName", ""),
                        "valueName": ov.get("valueName", ""),
                    }
                    for ov in matched_cand["option_values"]
                ]

            new_mapping.append(updated)
        else:
            # Keep original entry unchanged
            new_mapping.append(dict(entry))

    return {"mapping": new_mapping}


# ---------------------------------------------------------------------------
# Numeric conversion helpers
# ---------------------------------------------------------------------------

def _safe_float(value: Any) -> Optional[float]:
    """Convert to float, returning None on failure."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_int(value: Any) -> Optional[int]:
    """Convert to int, returning None on failure."""
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
