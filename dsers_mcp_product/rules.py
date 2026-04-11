"""
Rule Engine — Validate, normalise, and apply structured import rules.
规则引擎 —— 校验、标准化和应用结构化导入规则

Rules let callers customise how an imported product draft is transformed
before it gets pushed to a store. Three rule families are supported:
  - pricing  : multiplier / fixed-markup pricing adjustments
  - content  : title override / prefix / suffix, description, tags
  - images   : keep-first-N, drop-indexes, (future) translate / remove-logo

All normalisation is done against the provider's declared capabilities,
so unsupported rules produce warnings instead of silent failures.

规则允许调用方在将导入的商品草稿推送到店铺之前，自定义其转换方式。
支持三个规则族：
  - pricing  : 乘数 / 固定加价的价格调整
  - content  : 标题覆盖 / 前缀 / 后缀、描述、标签
  - images   : 保留前 N 张图、按索引删除、（未来）翻译 / 去水印

所有标准化操作都参照提供者声明的能力进行，因此不支持的规则会产生
警告而非静默失败。
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List, Optional, Set

# --- Known keys for each rule family / 各规则族的已知键 ---
_KNOWN_TOP_LEVEL_RULE_KEYS = {"pricing", "content", "images", "variant_overrides", "option_edits", "instruction_text"}
_KNOWN_PRICING_KEYS = {"mode", "multiplier", "fixed_markup", "fixed_price", "round_digits"}
_KNOWN_CONTENT_KEYS = {
    "title_override",
    "title_prefix",
    "title_suffix",
    "description_override_html",
    "description_append_html",
    "tags_add",
}
_KNOWN_IMAGE_KEYS = {"keep_first_n", "drop_indexes", "translate_image_text", "remove_logo"}
_DEFAULT_PRICING_MODES = {"provider_default", "multiplier", "fixed_markup", "fixed_price"}
_KNOWN_VARIANT_OVERRIDE_KEYS = {"match", "sell_price", "compare_at_price", "stock", "title", "image_url"}
_KNOWN_OPTION_EDIT_ACTIONS = {"rename_option", "rename_value", "remove_value", "remove_option"}


# ──────────────────────────────────────────────────────────────
#  Normalisation — turn raw user rules into validated, effective rules
#  标准化 —— 将原始用户规则转换为经过校验的有效规则
# ──────────────────────────────────────────────────────────────

def normalize_rules(rules: Dict[str, Any], rule_capabilities: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Validate user-supplied rules against provider capabilities and
    return effective_rules (safe to apply) along with any warnings/errors.

    根据提供者能力校验用户提供的规则，返回 effective_rules（可安全应用的
    规则）以及任何警告/错误信息。
    """
    requested_rules = deepcopy(rules or {})
    warnings: List[str] = []
    errors: List[str] = []
    effective_rules: Dict[str, Any] = {}

    if requested_rules and not isinstance(requested_rules, dict):
        return {
            "requested_rules": requested_rules,
            "effective_rules": {},
            "warnings": [],
            "errors": ["rules must be an object"],
        }

    requested_rules = requested_rules if isinstance(requested_rules, dict) else {}
    rule_capabilities = rule_capabilities or {}

    for key in sorted(requested_rules):
        if key not in _KNOWN_TOP_LEVEL_RULE_KEYS:
            warnings.append(f"Unknown top-level rule key '{key}' was ignored.")

    pricing = _normalize_pricing_rules(requested_rules.get("pricing"), rule_capabilities.get("pricing"), warnings, errors)
    if pricing:
        effective_rules["pricing"] = pricing

    content = _normalize_content_rules(requested_rules.get("content"), rule_capabilities.get("content"), warnings, errors)
    if content:
        effective_rules["content"] = content

    images = _normalize_image_rules(requested_rules.get("images"), rule_capabilities.get("images"), warnings, errors)
    if images:
        effective_rules["images"] = images

    variant_overrides = _normalize_variant_overrides(requested_rules.get("variant_overrides"), warnings, errors)
    if variant_overrides:
        effective_rules["variant_overrides"] = variant_overrides

    option_edits = _normalize_option_edits(requested_rules.get("option_edits"), warnings, errors)
    if option_edits:
        effective_rules["option_edits"] = option_edits

    # instruction_text is stored for operator context but not auto-applied.
    # instruction_text 仅为操作者上下文存储，不会自动应用。
    instruction_text = requested_rules.get("instruction_text")
    if instruction_text not in (None, ""):
        if isinstance(instruction_text, str):
            effective_rules["instruction_text"] = instruction_text
            warnings.append(
                "instruction_text is stored in the rule snapshot for operator context, but only structured rules are applied automatically."
            )
        else:
            errors.append("instruction_text must be a string when provided.")

    return {
        "requested_rules": requested_rules,
        "effective_rules": effective_rules,
        "warnings": warnings,
        "errors": errors,
    }


# ──────────────────────────────────────────────────────────────
#  Application — mutate the draft according to effective rules
#  应用 —— 根据有效规则修改草稿
# ──────────────────────────────────────────────────────────────

def apply_rules(draft: Dict[str, Any], rules: Dict[str, Any]) -> Dict[str, Any]:
    """
    Apply validated rules to a product draft and return the modified draft
    along with a summary of what was changed.

    将已校验的规则应用到商品草稿，返回修改后的草稿及变更摘要。
    """
    draft = deepcopy(draft)
    summary: Dict[str, Any] = {"applied": [], "warnings": []}

    pricing = rules.get("pricing") or {}
    if pricing:
        _apply_pricing_rules(draft, pricing, summary)

    content = rules.get("content") or {}
    if content:
        _apply_content_rules(draft, content, summary)

    images = rules.get("images") or {}
    if images:
        _apply_image_rules(draft, images, summary)

    variant_overrides = rules.get("variant_overrides")
    if isinstance(variant_overrides, list) and variant_overrides:
        _apply_variant_overrides(draft, variant_overrides, summary)

    option_edits = rules.get("option_edits")
    if isinstance(option_edits, list) and option_edits:
        _apply_option_edits(draft, option_edits, summary)

    # Recalculate total_inventory after option_edits may have removed variants
    variants = draft.get("variants") or []
    if variants:
        draft["total_inventory"] = sum(int(v.get("stock") or 0) for v in variants)

    instruction_text = rules.get("instruction_text")
    if instruction_text:
        summary["warnings"].append(
            "Freeform instruction_text is recorded for operator context, but only structured rules are applied automatically in this MVP."
        )

    return {"draft": draft, "summary": summary}


# ──────────────────────────────────────────────────────────────
#  Pricing rules / 价格规则
# ──────────────────────────────────────────────────────────────

def _normalize_pricing_rules(
    pricing: Any,
    capability: Optional[Dict[str, Any]],
    warnings: List[str],
    errors: List[str],
) -> Dict[str, Any]:
    """
    Validate pricing rules. Supports three modes:
      - provider_default: no price change
      - multiplier: base_price × multiplier
      - fixed_markup: base_price + fixed amount

    校验价格规则。支持三种模式：
      - provider_default：不改价
      - multiplier：底价 × 倍率
      - fixed_markup：底价 + 固定加价
    """
    if pricing in (None, {}):
        return {}
    if not isinstance(pricing, dict):
        errors.append("pricing must be an object when provided.")
        return {}

    capability = capability or {}
    if capability.get("supported") is False:
        warnings.append("Pricing rules were ignored because the current provider does not support pricing edits.")
        return {}

    mode = str(pricing.get("mode") or "provider_default")
    if mode not in _DEFAULT_PRICING_MODES:
        errors.append(f"Unsupported pricing.mode '{mode}'.")
        return {}

    allowed_modes = set(capability.get("modes") or _DEFAULT_PRICING_MODES)
    if mode not in allowed_modes:
        warnings.append(f"Pricing mode '{mode}' is not supported by the current provider and was ignored.")
        return {}

    for key in sorted(pricing):
        if key not in _KNOWN_PRICING_KEYS:
            warnings.append(f"Unknown pricing rule key '{key}' was ignored.")

    normalized: Dict[str, Any] = {"mode": mode}
    if mode == "multiplier":
        multiplier = _as_float(pricing.get("multiplier"), None)
        if multiplier is None:
            errors.append("pricing.multiplier must be a number when pricing.mode='multiplier'.")
            return {}
        if multiplier > 100:
            warnings.append(
                f"pricing.multiplier is {multiplier}x — this will set sell price to {multiplier}x the cost. Is this intentional?"
            )
        normalized["multiplier"] = multiplier
    elif mode == "fixed_markup":
        markup = _as_float(pricing.get("fixed_markup"), None)
        if markup is None:
            errors.append("pricing.fixed_markup must be a number when pricing.mode='fixed_markup'.")
            return {}
        if markup > 500:
            warnings.append(
                f"pricing.fixed_markup is ${markup} — this is an unusually high markup. Is this intentional?"
            )
        normalized["fixed_markup"] = markup
    elif mode == "fixed_price":
        fixed_price = _as_float(pricing.get("fixed_price"), None)
        if fixed_price is None:
            errors.append("pricing.fixed_price must be a number (in dollars) when pricing.mode='fixed_price'.")
            return {}
        if fixed_price < 0:
            errors.append("pricing.fixed_price must be >= 0.")
            return {}
        if fixed_price == 0:
            warnings.append("pricing.fixed_price is $0 — the product will be free. Is this intentional?")
        if fixed_price > 10000:
            warnings.append(
                f"pricing.fixed_price is ${fixed_price} — this is an unusually high price. Is this intentional?"
            )
        normalized["fixed_price"] = fixed_price

    if mode != "provider_default":
        round_digits = pricing.get("round_digits", 2)
        try:
            normalized["round_digits"] = int(round_digits)
        except (TypeError, ValueError):
            errors.append("pricing.round_digits must be an integer when provided.")
            return {}

    return normalized


def _normalize_content_rules(
    content: Any,
    capability: Optional[Dict[str, Any]],
    warnings: List[str],
    errors: List[str],
) -> Dict[str, Any]:
    """
    Validate content rules (title, description, tags).
    校验内容规则（标题、描述、标签）。
    """
    if content in (None, {}):
        return {}
    if not isinstance(content, dict):
        errors.append("content must be an object when provided.")
        return {}

    allowed_keys = _allowed_rule_keys(capability, _KNOWN_CONTENT_KEYS)
    normalized: Dict[str, Any] = {}
    for key in sorted(content):
        if key not in _KNOWN_CONTENT_KEYS:
            warnings.append(f"Unknown content rule key '{key}' was ignored.")
            continue
        if key not in allowed_keys:
            warnings.append(f"Content rule '{key}' is not supported by the current provider and was ignored.")
            continue
        value = content.get(key)
        if key == "tags_add":
            if value in (None, []):
                continue
            if not isinstance(value, list):
                errors.append("content.tags_add must be an array of strings when provided.")
                continue
            tags = []
            for raw_tag in value:
                tag = str(raw_tag).strip()
                if tag and tag not in tags:
                    tags.append(tag)
            if tags:
                normalized[key] = tags
            continue
        if value in (None, ""):
            continue
        sv = str(value)
        if key in ("description_override_html", "description_append_html"):
            from .security import contains_dangerous_html
            if contains_dangerous_html(sv):
                errors.append(
                    f"content.{key} contains potentially dangerous HTML (script, iframe, event handlers, or javascript: URLs). "
                    "This content would be rendered in the storefront and could execute in buyers' browsers. "
                    "Remove dangerous tags and attributes before retrying."
                )
                continue
        normalized[key] = sv

    return normalized


def _normalize_image_rules(
    images: Any,
    capability: Optional[Dict[str, Any]],
    warnings: List[str],
    errors: List[str],
) -> Dict[str, Any]:
    """
    Validate image rules (keep_first_n, drop_indexes, future flags).
    校验图片规则（保留前 N 张、按索引删除、未来功能标志）。
    """
    if images in (None, {}):
        return {}
    if not isinstance(images, dict):
        errors.append("images must be an object when provided.")
        return {}

    allowed_keys = _allowed_rule_keys(capability, _KNOWN_IMAGE_KEYS)
    normalized: Dict[str, Any] = {}
    for key in sorted(images):
        if key not in _KNOWN_IMAGE_KEYS:
            warnings.append(f"Unknown image rule key '{key}' was ignored.")
            continue
        if key not in allowed_keys:
            warnings.append(f"Image rule '{key}' is not supported by the current provider and was ignored.")
            continue

        value = images.get(key)
        if key == "keep_first_n":
            if value is None:
                continue
            try:
                keep_first_n = int(value)
            except (TypeError, ValueError):
                errors.append("images.keep_first_n must be an integer when provided.")
                continue
            if keep_first_n < 0:
                errors.append("images.keep_first_n must be >= 0.")
                continue
            normalized[key] = keep_first_n
            continue

        if key == "drop_indexes":
            if value in (None, []):
                continue
            if not isinstance(value, list):
                errors.append("images.drop_indexes must be an array of integers when provided.")
                continue
            indexes = []
            for raw_index in value:
                try:
                    index = int(raw_index)
                except (TypeError, ValueError):
                    errors.append("images.drop_indexes must contain only integers.")
                    indexes = []
                    break
                if index >= 0 and index not in indexes:
                    indexes.append(index)
            if indexes:
                normalized[key] = sorted(indexes)
            continue

        normalized[key] = bool(value)

    return normalized


# ──────────────────────────────────────────────────────────────
#  Rule application helpers / 规则应用辅助函数
# ──────────────────────────────────────────────────────────────

def _apply_pricing_rules(draft: Dict[str, Any], pricing: Dict[str, Any], summary: Dict[str, Any]) -> None:
    """
    Apply pricing adjustments to all variants in the draft.
    对草稿中的所有变体应用价格调整。
    """
    mode = pricing.get("mode", "provider_default")
    if mode == "provider_default":
        return

    multiplier = _as_float(pricing.get("multiplier"), 1.0)
    markup = _as_float(pricing.get("fixed_markup"), 0.0)
    fixed_price = _as_float(pricing.get("fixed_price"), 0.0)
    round_digits = int(pricing.get("round_digits", 2))

    variants = draft.get("variants") or []
    changed = 0
    for variant in variants:
        if mode == "fixed_price":
            new_price = round(fixed_price, round_digits)
        else:
            base = _first_price(variant)
            if base is None:
                continue
            if mode == "multiplier":
                new_price = round(base * multiplier, round_digits)
            elif mode == "fixed_markup":
                new_price = round(base + markup, round_digits)
            else:
                summary["warnings"].append(f"Unsupported pricing mode '{mode}' was ignored.")
                return
        variant["offer_price"] = new_price
        changed += 1

    summary["applied"].append({"rule_family": "pricing", "mode": mode, "variants_changed": changed})


def _apply_content_rules(draft: Dict[str, Any], content: Dict[str, Any], summary: Dict[str, Any]) -> None:
    """
    Apply content overrides/edits to the draft's title, description, and tags.
    对草稿的标题、描述和标签应用内容覆盖/编辑。
    """
    title = draft.get("title") or ""
    if content.get("title_override"):
        title = str(content["title_override"]).strip()
    if content.get("title_prefix"):
        title = str(content["title_prefix"]) + title
    if content.get("title_suffix"):
        title = title + str(content["title_suffix"])
    if title:
        draft["title"] = title

    if content.get("description_override_html"):
        draft["description_html"] = str(content["description_override_html"])
    elif content.get("description_append_html"):
        existing = draft.get("description_html") or ""
        draft["description_html"] = existing + str(content["description_append_html"])

    if content.get("tags_add"):
        existing_tags = list(draft.get("tags") or [])
        for tag in content.get("tags_add") or []:
            if tag not in existing_tags:
                existing_tags.append(tag)
        draft["tags"] = existing_tags

    summary["applied"].append({"rule_family": "content"})


def _apply_image_rules(draft: Dict[str, Any], images: Dict[str, Any], summary: Dict[str, Any]) -> None:
    """
    Apply image filtering (drop specific indexes, keep first N).
    应用图片筛选（删除指定索引、保留前 N 张）。
    """
    image_list = list(draft.get("images") or [])
    original_count = len(image_list)

    # Drop by index in reverse order to keep remaining indexes stable.
    # 按逆序删除索引，保证剩余索引不发生偏移。
    drop_indexes = sorted(set(images.get("drop_indexes") or []), reverse=True)
    for idx in drop_indexes:
        if 0 <= idx < len(image_list):
            image_list.pop(idx)

    keep_first_n = images.get("keep_first_n")
    if keep_first_n is not None:
        image_list = image_list[: int(keep_first_n)]

    if images.get("translate_image_text"):
        summary["warnings"].append("translate_image_text is not auto-applied in this MVP.")
    if images.get("remove_logo"):
        summary["warnings"].append("remove_logo is not auto-applied in this MVP.")

    draft["images"] = image_list
    summary["applied"].append(
        {"rule_family": "images", "image_count_before": original_count, "image_count_after": len(image_list)}
    )


# ──────────────────────────────────────────────────────────────
#  Variant overrides / 变体覆盖规则
# ──────────────────────────────────────────────────────────────

def _normalize_variant_overrides(overrides: Any, warnings: List[str], errors: List[str]) -> Optional[List[Dict[str, Any]]]:
    if overrides is None:
        return None
    if not isinstance(overrides, list):
        errors.append("variant_overrides must be an array of objects, each with a 'match' field.")
        return None
    if not overrides:
        return None
    result: List[Dict[str, Any]] = []
    for i, entry in enumerate(overrides):
        if not isinstance(entry, dict):
            warnings.append(f"variant_overrides[{i}] is not an object and was skipped.")
            continue
        match = str(entry.get("match") or "").strip()
        if not match:
            errors.append(f"variant_overrides[{i}].match is required (variant title or SKU substring to match).")
            continue
        normalized: Dict[str, Any] = {"match": match}
        for key in sorted(entry):
            if key not in _KNOWN_VARIANT_OVERRIDE_KEYS:
                warnings.append(f"Unknown variant_overrides key '{key}' at index {i} was ignored.")
                continue
            if key == "match":
                continue
            if key in ("sell_price", "compare_at_price"):
                val = _as_float(entry[key], None)
                if val is None or val < 0:
                    errors.append(f"variant_overrides[{i}].{key} must be a non-negative number (in dollars).")
                    continue
                normalized[key] = val
            elif key == "stock":
                val = _as_float(entry[key], None)
                if val is None or val < 0 or int(val) != val:
                    errors.append(f"variant_overrides[{i}].stock must be a non-negative integer.")
                    continue
                normalized[key] = int(val)
            elif key == "title":
                sv = str(entry[key] or "").strip()
                if sv:
                    normalized[key] = sv
            elif key == "image_url":
                sv = str(entry[key] or "").strip()
                if sv:
                    import re as _re
                    if not _re.match(r"^https?://", sv, _re.IGNORECASE):
                        errors.append(f"variant_overrides[{i}].image_url must be a valid URL starting with http:// or https://.")
                        continue
                    normalized[key] = sv
        if len(normalized) > 1:
            result.append(normalized)
    return result if result else None


def _apply_variant_overrides(draft: Dict[str, Any], overrides: List[Dict[str, Any]], summary: Dict[str, Any]) -> None:
    variants = draft.get("variants") or []
    if not variants:
        return
    matched = 0
    for override in overrides:
        pattern = str(override.get("match") or "").lower()
        if not pattern:
            continue
        for v in variants:
            title_lower = str(v.get("title") or "").lower()
            sku_lower = str(v.get("sku") or "").lower()
            if pattern not in title_lower and pattern not in sku_lower:
                continue
            if override.get("sell_price") is not None:
                v["offer_price"] = override["sell_price"]
            if override.get("compare_at_price") is not None:
                v["compare_at_price"] = override["compare_at_price"]
            if override.get("stock") is not None:
                v["stock"] = override["stock"]
            if override.get("title") is not None:
                v["title"] = str(override["title"])
            if override.get("image_url") is not None:
                v["image_url"] = str(override["image_url"])
            matched += 1
    if matched:
        summary["applied"].append({"rule_family": "variant_overrides", "variants_matched": matched})
    else:
        summary["warnings"].append(
            "variant_overrides were provided but no variants matched. Check the 'match' values against variant titles/SKUs."
        )


# ──────────────────────────────────────────────────────────────
#  Option edits / 选项编辑规则
# ──────────────────────────────────────────────────────────────

def _normalize_option_edits(raw: Any, warnings: List[str], errors: List[str]) -> Optional[List[Dict[str, Any]]]:
    if raw is None:
        return None
    if not isinstance(raw, list):
        errors.append("option_edits must be an array of edit actions.")
        return None
    result: List[Dict[str, Any]] = []
    for i, edit in enumerate(raw):
        if not isinstance(edit, dict):
            errors.append(f"option_edits[{i}] must be an object.")
            continue
        action = str(edit.get("action") or "")
        if action not in _KNOWN_OPTION_EDIT_ACTIONS:
            errors.append(f"option_edits[{i}]: unknown action '{action}'. Allowed: {', '.join(sorted(_KNOWN_OPTION_EDIT_ACTIONS))}.")
            continue
        if not edit.get("option_name") or not isinstance(edit.get("option_name"), str):
            errors.append(f"option_edits[{i}]: 'option_name' (string) is required.")
            continue
        if action in ("rename_value", "remove_value") and (not edit.get("value_name") or not isinstance(edit.get("value_name"), str)):
            errors.append(f"option_edits[{i}]: '{action}' requires 'value_name' (string).")
            continue
        if action in ("rename_option", "rename_value") and (not edit.get("new_name") or not isinstance(edit.get("new_name"), str)):
            errors.append(f"option_edits[{i}]: '{action}' requires 'new_name' (string).")
            continue
        result.append(edit)
    return result if result else None


def _apply_option_edits(draft: Dict[str, Any], edits: List[Dict[str, Any]], summary: Dict[str, Any]) -> None:
    options: List[Dict[str, Any]] = draft.get("options") or []
    variants: List[Dict[str, Any]] = draft.get("variants") or []
    variants_removed = 0
    renamed_options: Dict[str, str] = {}

    for edit in edits:
        action = edit["action"]
        option_name = str(edit["option_name"])
        opt = next((o for o in options if o.get("name") == option_name), None)
        if opt is None:
            new_name = renamed_options.get(option_name)
            if new_name:
                summary["warnings"].append(
                    f"option_edits: option '{option_name}' was renamed to '{new_name}' by a prior edit — use '{new_name}' instead."
                )
            else:
                summary["warnings"].append(f"option_edits: option '{option_name}' not found — skipped.")
            continue

        if action == "rename_option":
            new_name = str(edit["new_name"])
            renamed_options[option_name] = new_name
            opt["name"] = new_name
            for v in variants:
                for ov in (v.get("option_values") or []):
                    if ov.get("optionId") == opt.get("id"):
                        ov["optionName"] = new_name

        elif action == "rename_value":
            value_name = str(edit["value_name"])
            new_name = str(edit["new_name"])
            val = next((v for v in (opt.get("values") or []) if v.get("name") == value_name), None)
            if val is None:
                summary["warnings"].append(f"option_edits: value '{value_name}' not found in option '{option_name}' — skipped.")
                continue
            val["name"] = new_name
            for v in variants:
                for ov in (v.get("option_values") or []):
                    if ov.get("optionId") != opt.get("id"):
                        continue
                    id_match = val.get("id") and val["id"] != "" and ov.get("valueId") == val["id"]
                    name_match = ov.get("valueName") == value_name
                    if id_match or name_match:
                        ov["valueName"] = new_name
                _rebuild_variant_title(v)

        elif action == "remove_value":
            value_name = str(edit["value_name"])
            values = opt.get("values") or []
            val_idx = next((i for i, v in enumerate(values) if v.get("name") == value_name), -1)
            if val_idx == -1:
                summary["warnings"].append(f"option_edits: value '{value_name}' not found in option '{option_name}' — skipped.")
                continue
            removed_val = values.pop(val_idx)
            before = len(variants)
            variants[:] = [
                v for v in variants
                if not any(
                    ov.get("optionId") == opt.get("id") and (
                        (removed_val.get("id") and removed_val["id"] != "" and ov.get("valueId") == removed_val["id"])
                        or ov.get("valueName") == value_name
                    )
                    for ov in (v.get("option_values") or [])
                )
            ]
            variants_removed += before - len(variants)

        elif action == "remove_option":
            opt_idx = next((i for i, o in enumerate(options) if o.get("id") == opt.get("id")), -1)
            if opt_idx != -1:
                options.pop(opt_idx)
            for v in variants:
                v["option_values"] = [ov for ov in (v.get("option_values") or []) if ov.get("optionId") != opt.get("id")]
                _rebuild_variant_title(v)

    draft["variants"] = variants
    draft["options"] = options
    entry: Dict[str, Any] = {"rule_family": "option_edits", "edits_count": len(edits)}
    if variants_removed > 0:
        entry["variants_removed"] = variants_removed
        entry["variants_remaining"] = len(variants)
    summary["applied"].append(entry)


def _rebuild_variant_title(v: Dict[str, Any]) -> None:
    option_values = v.get("option_values")
    if not option_values:
        return
    original = str(v.get("title") or "")
    sep = " / " if " / " in original else "-" if "-" in original else " / "
    v["title"] = sep.join(ov.get("valueName", "") for ov in option_values)


# ──────────────────────────────────────────────────────────────
#  Rule merging / 规则合并
# ──────────────────────────────────────────────────────────────

def merge_rules(existing: Dict[str, Any], incoming: Dict[str, Any]) -> Dict[str, Any]:
    """Merge incoming rules into existing rules (incremental update).

    - pricing / images / variant_overrides / option_edits: replace entire family
    - content: merge by individual field
    - null value for a family: remove that family
    """
    merged = deepcopy(existing)
    for key, value in incoming.items():
        if value is None:
            merged.pop(key, None)
        elif key == "content":
            existing_content = merged.get("content") or {}
            if isinstance(value, dict):
                for ck, cv in value.items():
                    if cv is None or cv == "":
                        existing_content.pop(ck, None)
                    else:
                        existing_content[ck] = cv
                if existing_content:
                    merged["content"] = existing_content
                else:
                    merged.pop("content", None)
            else:
                merged["content"] = value
        else:
            merged[key] = deepcopy(value)
    return merged


# ──────────────────────────────────────────────────────────────
#  Utility helpers / 工具辅助函数
# ──────────────────────────────────────────────────────────────

def _first_price(variant: Dict[str, Any]) -> Any:
    """
    Return the best available price from a variant (offer_price first, then supplier_price).
    返回变体的最佳可用价格（优先 offer_price，其次 supplier_price）。
    """
    for key in ("offer_price", "supplier_price"):
        value = variant.get(key)
        parsed = _as_float(value, None)
        if parsed is not None:
            return parsed
    return None


def _as_float(value: Any, default: Any) -> Any:
    if value is None or value == "":
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _allowed_rule_keys(capability: Optional[Dict[str, Any]], default_keys: Set[str]) -> Set[str]:
    """
    Determine which rule keys are allowed based on provider capability declarations.
    The supported field can be True (all), False (none), or a list of specific keys.

    根据提供者的能力声明确定允许哪些规则键。
    supported 字段可以是 True（全部）、False（无）或具体键列表。
    """
    capability = capability or {}
    supported = capability.get("supported")
    unsupported = {str(item) for item in capability.get("unsupported") or []}

    if isinstance(supported, list):
        allowed = {str(item) for item in supported}
    elif supported is False:
        allowed = set()
    else:
        allowed = set(default_keys)

    return allowed - unsupported
