"""
Push Options — Validate and normalise store-push configuration.
推送选项 —— 校验和标准化店铺推送配置

Push options control *how* a product is published to the target store,
separate from *what* the product looks like (which is handled by rules).
Examples include whether to publish immediately, which sales channels
to activate, which image strategy to use, and whether to apply the
store's own pricing rule.

推送选项控制商品*如何*发布到目标店铺，与商品*长什么样*（由规则处理）
分开。例如：是否立即上架、激活哪些销售渠道、使用哪种图片策略、
是否应用店铺自身的定价规则等。
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List, Optional, Set

# All recognised push option keys. Unknown keys produce a warning.
# 所有已识别的推送选项键。未知键会产生警告。
_KNOWN_PUSH_OPTION_KEYS = {
    "publish_to_online_store",
    "only_push_specifications",
    "image_strategy",
    "pricing_rule_behavior",
    "auto_inventory_update",
    "auto_price_update",
    "sales_channels",
    "store_shipping_profile",
}

_DEFAULT_IMAGE_STRATEGIES = {"selected_only", "all_available"}
_DEFAULT_PRICING_RULE_BEHAVIORS = {"keep_manual", "apply_store_pricing_rule"}


def normalize_push_options(
    push_options: Optional[Dict[str, Any]],
    visibility_mode: str,
    capability: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Validate and normalise push options against provider capabilities.
    Ensures publish_to_online_store stays consistent with visibility_mode.

    根据提供者能力校验和标准化推送选项。
    确保 publish_to_online_store 与 visibility_mode 保持一致。
    """
    requested_push_options = deepcopy(push_options or {})
    warnings: List[str] = []
    errors: List[str] = []

    if requested_push_options and not isinstance(requested_push_options, dict):
        return {
            "requested_push_options": requested_push_options,
            "effective_push_options": {},
            "warnings": [],
            "errors": ["push_options must be an object"],
        }

    requested_push_options = requested_push_options if isinstance(requested_push_options, dict) else {}
    capability = capability or {}
    allowed_keys = _allowed_push_option_keys(capability)

    # Derive the default publish flag from visibility_mode.
    # 从 visibility_mode 推导默认的发布标志。
    publish_to_online_store = visibility_mode == "sell_immediately"
    effective_push_options: Dict[str, Any] = {
        "publish_to_online_store": publish_to_online_store,
        "only_push_specifications": False,
        "image_strategy": "selected_only",
        "pricing_rule_behavior": "keep_manual",
        "auto_inventory_update": False,
        "auto_price_update": False,
        "sales_channels": ["online_store"] if publish_to_online_store else [],
    }

    for key in sorted(requested_push_options):
        if key not in _KNOWN_PUSH_OPTION_KEYS:
            warnings.append(f"Unknown push option '{key}' was ignored.")
            continue
        if key not in allowed_keys:
            warnings.append(f"Push option '{key}' is not supported by the current provider and was ignored.")
            continue

        value = requested_push_options.get(key)

        # publish_to_online_store must stay consistent with visibility_mode.
        # publish_to_online_store 必须与 visibility_mode 保持一致。
        if key == "publish_to_online_store":
            requested_publish = bool(value)
            if requested_publish != publish_to_online_store:
                warnings.append(
                    "push_options.publish_to_online_store was overridden to stay consistent with visibility_mode."
                )
            effective_push_options[key] = publish_to_online_store
            continue

        # Simple boolean toggles. / 简单布尔开关。
        if key in {"only_push_specifications", "auto_inventory_update", "auto_price_update"}:
            effective_push_options[key] = bool(value)
            continue

        if key == "image_strategy":
            strategy = str(value or "").strip() or effective_push_options[key]
            allowed_strategies = set(capability.get("image_strategy_modes") or _DEFAULT_IMAGE_STRATEGIES)
            if strategy not in _DEFAULT_IMAGE_STRATEGIES:
                errors.append(f"Unsupported push_options.image_strategy '{strategy}'.")
                continue
            if strategy not in allowed_strategies:
                warnings.append(f"image_strategy '{strategy}' is not supported by the current provider and was ignored.")
                continue
            effective_push_options[key] = strategy
            continue

        if key == "pricing_rule_behavior":
            behavior = str(value or "").strip() or effective_push_options[key]
            allowed_behaviors = set(capability.get("pricing_rule_behavior_modes") or _DEFAULT_PRICING_RULE_BEHAVIORS)
            if behavior not in _DEFAULT_PRICING_RULE_BEHAVIORS:
                errors.append(f"Unsupported push_options.pricing_rule_behavior '{behavior}'.")
                continue
            if behavior not in allowed_behaviors:
                warnings.append(
                    f"pricing_rule_behavior '{behavior}' is not supported by the current provider and was ignored."
                )
                continue
            effective_push_options[key] = behavior
            continue

        # Shopify delivery profile — passthrough as opaque data.
        # Shopify 配送档案 —— 作为不透明数据透传。
        if key == "store_shipping_profile":
            if isinstance(value, list) or value is None:
                effective_push_options[key] = value
            continue

        if key == "sales_channels":
            if value in (None, []):
                effective_push_options[key] = []
                continue
            if not isinstance(value, list):
                errors.append("push_options.sales_channels must be an array of strings when provided.")
                continue
            allowed_channels = set(capability.get("sales_channels") or [])
            channels = []
            for raw_channel in value:
                channel = str(raw_channel).strip()
                if not channel:
                    continue
                if allowed_channels and channel not in allowed_channels:
                    warnings.append(f"Sales channel '{channel}' is not supported by the current provider and was ignored.")
                    continue
                if channel not in channels:
                    channels.append(channel)
            effective_push_options[key] = channels

    # Enforce consistency: no channels when not publishing online.
    # 强制一致性：不在线发布时清空销售渠道。
    if not effective_push_options.get("publish_to_online_store"):
        effective_push_options["sales_channels"] = []
    elif "online_store" not in effective_push_options["sales_channels"]:
        effective_push_options["sales_channels"] = ["online_store"] + list(effective_push_options["sales_channels"])

    return {
        "requested_push_options": requested_push_options,
        "effective_push_options": effective_push_options,
        "warnings": warnings,
        "errors": errors,
    }


def _allowed_push_option_keys(capability: Optional[Dict[str, Any]]) -> Set[str]:
    """
    Determine which push option keys the provider supports.
    Same tri-state logic as rule capabilities: True / False / list.

    确定提供者支持哪些推送选项键。
    与规则能力相同的三态逻辑：True / False / 列表。
    """
    capability = capability or {}
    supported = capability.get("supported")
    unsupported = {str(item) for item in capability.get("unsupported") or []}

    if isinstance(supported, list):
        allowed = {str(item) for item in supported}
    elif supported is False:
        allowed = set()
    else:
        allowed = set(_KNOWN_PUSH_OPTION_KEYS)

    return allowed - unsupported
