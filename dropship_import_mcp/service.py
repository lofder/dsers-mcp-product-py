"""
Import Flow Service — Orchestrates the complete import lifecycle.
导入流程服务 —— 编排完整的导入生命周期

This service is the central coordinator between all subsystems:
  resolver → provider → rules → push_options → job_store

A typical lifecycle:
  1. prepare_import_candidate — resolve URL, import, apply rules, save preview
  2. (optional) get_import_preview / set_product_visibility — review & adjust
  3. confirm_push_to_store — push the finalised draft to the target store

All methods accept a flat dict (the MCP tool arguments) and return a dict
(the MCP tool response). The service never talks to vendor APIs directly;
it delegates to the injected ImportProvider.

本服务是所有子系统之间的中央协调者：
  resolver → provider → rules → push_options → job_store

典型的生命周期：
  1. prepare_import_candidate — 解析 URL、导入、应用规则、保存预览
  2. （可选）get_import_preview / set_product_visibility — 审查和调整
  3. confirm_push_to_store — 将最终草稿推送到目标店铺

所有方法接受扁平字典（MCP 工具参数）并返回字典（MCP 工具响应）。
服务不直接与供应商 API 通信，而是委托给注入的 ImportProvider。
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from dropship_import_mcp.job_store import FileJobStore
from dropship_import_mcp.provider import ImportProvider
from dropship_import_mcp.push_options import normalize_push_options
from dropship_import_mcp.resolver import resolve_source_url
from dropship_import_mcp.rules import apply_rules, normalize_rules


class ImportFlowService:
    """
    Stateless orchestrator — all state lives in the FileJobStore.
    无状态编排器 —— 所有状态都保存在 FileJobStore 中。
    """

    def __init__(self, provider: ImportProvider, store: FileJobStore) -> None:
        self._provider = provider
        self._store = store

    # ── Step 0: Capability discovery / 步骤 0：能力发现 ──

    async def get_rule_capabilities(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Return what the loaded provider supports: stores, rule families,
        push options, and any advisory notes.

        返回当前加载的提供者支持的内容：店铺列表、规则族、
        推送选项以及任何咨询说明。
        """
        target_store = payload.get("target_store")
        provider_caps = await self._provider.get_rule_capabilities(target_store=target_store)
        return {
            "provider_label": provider_caps.get("provider_label", self._provider.name),
            "source_support": provider_caps.get("source_support", []),
            "stores": provider_caps.get("stores", []),
            "rule_families": provider_caps.get("rule_families", {}),
            "push_options": provider_caps.get("push_options", {}),
            "notes": provider_caps.get("notes", []),
        }

    async def validate_rules(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Dry-run rule validation without importing a product.
        不导入商品的规则校验试运行。
        """
        target_store = payload.get("target_store")
        rules = payload.get("rules") or {}
        provider_caps = await self._provider.get_rule_capabilities(target_store=target_store)
        validation = normalize_rules(rules, provider_caps.get("rule_families"))
        return {
            "provider_label": provider_caps.get("provider_label", self._provider.name),
            "target_store": target_store,
            "requested_rules": validation.get("requested_rules", {}),
            "effective_rules_snapshot": validation.get("effective_rules", {}),
            "warnings": validation.get("warnings", []),
            "errors": validation.get("errors", []),
        }

    # ── Step 1: Import and preview / 步骤 1：导入和预览 ──

    async def prepare_import_candidate(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Full import pipeline: resolve URL → provider.prepare → apply rules
        → persist job → return preview.

        完整导入流水线：解析 URL → provider.prepare → 应用规则
        → 持久化任务 → 返回预览。
        """
        source_url = str(payload.get("source_url") or "").strip()
        if not source_url:
            raise ValueError("source_url is required")

        source_hint = str(payload.get("source_hint") or "auto").strip() or "auto"
        country = str(payload.get("country") or "US").strip() or "US"
        visibility_mode = str(payload.get("visibility_mode") or "backend_only").strip() or "backend_only"
        target_store = payload.get("target_store")
        rules = payload.get("rules") or {}

        provider_caps = await self._provider.get_rule_capabilities(target_store=target_store)
        validated_rules = normalize_rules(rules, provider_caps.get("rule_families"))
        if validated_rules.get("errors"):
            raise ValueError("; ".join(validated_rules["errors"]))

        resolved = await resolve_source_url(source_url, source_hint)
        prepared = await self._provider.prepare_candidate(
            source_url=resolved["resolved_url"],
            source_hint=resolved["source_hint"],
            country=country,
        )

        # Keep the unmodified draft for before/after comparison in preview.
        # 保留未修改的草稿，用于预览中的前后对比。
        original_draft = deepcopy(prepared["draft"])
        effective_rules = validated_rules.get("effective_rules", {})
        ruled = apply_rules(prepared["draft"], effective_rules)
        final_draft = ruled["draft"]

        job = {
            "status": "preview_ready",
            "created_at": _utc_now(),
            "provider_label": prepared.get("provider_label", self._provider.name),
            "source_url": source_url,
            "resolved_source_url": resolved["resolved_url"],
            "source_hint": resolved["source_hint"],
            "resolver_mode": resolved.get("resolver_mode"),
            "country": country,
            "target_store": target_store,
            "visibility_mode": visibility_mode,
            "requested_rules": validated_rules.get("requested_rules", {}),
            "effective_rules_snapshot": effective_rules,
            "rules": effective_rules,
            "provider_state": prepared["provider_state"],
            "original_draft": original_draft,
            "draft": final_draft,
            "warnings": list(resolved.get("warnings") or [])
            + list(prepared.get("warnings") or [])
            + list(validated_rules.get("warnings") or [])
            + list((ruled.get("summary") or {}).get("warnings") or []),
            "rule_summary": ruled.get("summary") or {},
        }
        job_id = self._store.create(job)
        job["job_id"] = job_id
        self._store.save(job_id, job)
        return self._preview(job)

    async def get_import_preview(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Reload a previously prepared preview by job_id.
        通过 job_id 重新加载之前准备的预览。
        """
        job_id = str(payload.get("job_id") or "").strip()
        if not job_id:
            raise ValueError("job_id is required")
        job = self._store.load(job_id)
        return self._preview(job)

    # ── Step 2: Adjust before push / 步骤 2：推送前调整 ──

    async def set_product_visibility(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Change visibility_mode (backend_only ↔ sell_immediately) before confirmation.
        在确认推送前更改 visibility_mode（backend_only ↔ sell_immediately）。
        """
        job_id = str(payload.get("job_id") or "").strip()
        visibility_mode = str(payload.get("visibility_mode") or "").strip()
        if not job_id or not visibility_mode:
            raise ValueError("job_id and visibility_mode are required")
        job = self._store.load(job_id)
        job["visibility_mode"] = visibility_mode
        job["updated_at"] = _utc_now()
        self._store.save(job_id, job)
        return {
            "job_id": job_id,
            "status": job.get("status"),
            "visibility_mode": visibility_mode,
        }

    # ── Step 3: Push to store / 步骤 3：推送到店铺 ──

    async def confirm_push_to_store(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Final confirmation: validate push options → delegate to provider.commit
        → persist result. This is the only step with real side effects.

        最终确认：校验推送选项 → 委托给 provider.commit → 持久化结果。
        这是唯一具有真实副作用的步骤。
        """
        job_id = str(payload.get("job_id") or "").strip()
        if not job_id:
            raise ValueError("job_id is required")

        job = self._store.load(job_id)
        target_store = payload.get("target_store") or job.get("target_store")
        visibility_mode = payload.get("visibility_mode") or job.get("visibility_mode") or "backend_only"
        provider_caps = await self._provider.get_rule_capabilities(target_store=target_store)
        push_option_check = normalize_push_options(
            payload.get("push_options"),
            visibility_mode,
            provider_caps.get("push_options"),
        )
        if push_option_check.get("errors"):
            raise ValueError("; ".join(push_option_check["errors"]))
        effective_push_options = push_option_check.get("effective_push_options", {})

        result = await self._provider.commit_candidate(
            provider_state=job["provider_state"],
            draft=job["draft"],
            target_store=target_store,
            visibility_mode=visibility_mode,
            push_options=effective_push_options,
        )
        job["status"] = result.get("job_status", "push_requested")
        job["updated_at"] = _utc_now()
        job["target_store"] = target_store
        job["visibility_mode"] = visibility_mode
        job["requested_push_options"] = push_option_check.get("requested_push_options", {})
        job["effective_push_options"] = effective_push_options
        job["push_option_warnings"] = push_option_check.get("warnings", [])
        job["push_result"] = result
        self._store.save(job_id, job)

        return {
            "job_id": job_id,
            "status": job["status"],
            "target_store": target_store,
            "visibility_requested": visibility_mode,
            "visibility_applied": result.get("visibility_applied", visibility_mode),
            "push_options_applied": result.get("push_options_applied", effective_push_options),
            "job_summary": result.get("summary", {}),
            "warnings": list(push_option_check.get("warnings") or []) + list(result.get("warnings", [])),
        }

    # ── Status query / 状态查询 ──

    async def get_job_status(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Return current status and metadata for a job.
        返回任务的当前状态和元数据。
        """
        job_id = str(payload.get("job_id") or "").strip()
        if not job_id:
            raise ValueError("job_id is required")
        job = self._store.load(job_id)
        return {
            "job_id": job_id,
            "status": job.get("status"),
            "created_at": job.get("created_at"),
            "updated_at": job.get("updated_at"),
            "target_store": job.get("target_store"),
            "visibility_mode": job.get("visibility_mode"),
            "warnings": list(job.get("warnings", [])) + list(job.get("push_option_warnings", [])),
            "has_push_result": bool(job.get("push_result")),
        }

    # ── Preview builder / 预览构建 ──

    def _preview(self, job: Dict[str, Any]) -> Dict[str, Any]:
        """
        Build a human-readable preview comparing the original and final draft.
        构建可读的预览，对比原始草稿和最终草稿。
        """
        original = job["original_draft"]
        final = job["draft"]
        preview = {
            "job_id": job.get("job_id"),
            "status": job.get("status"),
            "source_url": job.get("source_url"),
            "resolved_source_url": job.get("resolved_source_url"),
            "resolver_mode": job.get("resolver_mode"),
            "target_store": job.get("target_store"),
            "visibility_mode": job.get("visibility_mode"),
            "title_before": original.get("title"),
            "title_after": final.get("title"),
            "description_changed": (original.get("description_html") or "") != (final.get("description_html") or ""),
            "images_before": len(original.get("images") or []),
            "images_after": len(final.get("images") or []),
            "variant_count": len(final.get("variants") or []),
            "price_range_before": _price_range(original),
            "price_range_after": _price_range(final),
            "tags_before": original.get("tags") or [],
            "tags_after": final.get("tags") or [],
            "requested_rules": job.get("requested_rules", {}),
            "effective_rules_snapshot": job.get("effective_rules_snapshot", {}),
            "rule_summary": job.get("rule_summary", {}),
            "warnings": job.get("warnings", []),
        }
        if final.get("variants"):
            preview["variant_preview"] = [
                {
                    "title": item.get("title"),
                    "supplier_price": item.get("supplier_price"),
                    "offer_price": item.get("offer_price"),
                    "sku": item.get("sku"),
                }
                for item in final.get("variants")[:5]
            ]
        return preview


# ──────────────────────────────────────────────────────────────
#  Module-level helpers / 模块级辅助函数
# ──────────────────────────────────────────────────────────────

def _price_range(draft: Dict[str, Any]) -> Dict[str, Optional[float]]:
    """
    Extract the min/max price across all variants for display in preview.
    提取所有变体的最低/最高价格，用于预览展示。
    """
    prices = []
    for variant in draft.get("variants") or []:
        for key in ("offer_price", "supplier_price"):
            value = variant.get(key)
            if value is None:
                continue
            try:
                prices.append(float(value))
                break
            except (TypeError, ValueError):
                continue
    if not prices:
        return {"min": None, "max": None}
    return {"min": min(prices), "max": max(prices)}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
