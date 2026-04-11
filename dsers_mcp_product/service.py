"""
Import Flow Service — Orchestrates the complete import lifecycle.
导入流程服务 —— 编排完整的导入生命周期

This service is the central coordinator between all subsystems:
  resolver → provider → rules → push_options → job_store

Supports both single and batch modes:
  - Single: source_url / job_id  (original behaviour, fully backward-compatible)
  - Batch:  source_urls / job_ids (iterate and return per-item results)
  - Multi-store: target_stores    (one job pushed to N stores in one call)

同时支持单条和批量模式：
  - 单条：source_url / job_id（原始行为，完全向后兼容）
  - 批量：source_urls / job_ids（逐条执行并返回每条结果）
  - 多店铺：target_stores（一个 job 在一次调用中推到 N 个店铺）
"""
from __future__ import annotations

import uuid as _uuid
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from dsers_mcp_product.job_store import FileJobStore
from dsers_mcp_product.provider import ImportProvider
from dsers_mcp_product.push_options import normalize_push_options
from dsers_mcp_product.resolver import resolve_source_url
from dsers_mcp_product.rules import apply_rules, normalize_rules, merge_rules


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

    # ══════════════════════════════════════════════════════════════
    #  Step 1: Import — single or batch
    #  步骤 1：导入 —— 单条或批量
    # ══════════════════════════════════════════════════════════════

    async def prepare_import_candidate(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Unified entry point for single and batch import.
        单条和批量导入的统一入口。

        - If `source_urls` (list) is present → batch mode
        - Otherwise falls back to `source_url` (string) → single mode
        - 如果存在 `source_urls`（列表）→ 批量模式
        - 否则回退到 `source_url`（字符串）→ 单条模式
        """
        source_urls = payload.get("source_urls")
        if isinstance(source_urls, list):
            return await self._batch_prepare(payload, source_urls)
        return await self._prepare_single(payload)

    async def _prepare_single(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Original single-item import pipeline (fully backward-compatible).
        原始单条导入流水线（完全向后兼容）。
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

    async def _batch_prepare(self, payload: Dict[str, Any], source_urls: List[Any]) -> Dict[str, Any]:
        """
        Batch import: iterate over source_urls, call _prepare_single for each.
        Each item can be a plain URL string or an object with per-item overrides.
        Failures are captured per-item and do not stop the batch.

        批量导入：遍历 source_urls，逐条调用 _prepare_single。
        每项可以是纯 URL 字符串或带单条覆盖的对象。
        单条失败不会中断整个批次。
        """
        if not source_urls:
            return {"error": "source_urls must be a non-empty list / source_urls 不能为空列表"}

        batch_id = f"batch-{_uuid.uuid4().hex[:12]}"
        # Shared defaults from the batch-level payload.
        # 从批次级 payload 中提取共享默认值。
        shared_keys = ("country", "target_store", "visibility_mode", "source_hint")
        shared = {k: payload.get(k) for k in shared_keys if payload.get(k) is not None}
        shared_rules = payload.get("rules")

        results: List[Dict[str, Any]] = []
        succeeded = 0
        failed = 0

        for idx, item in enumerate(source_urls):
            url, item_payload = _parse_batch_item(item, shared, shared_rules)
            if not url:
                results.append({"index": idx, "source_url": "", "error": "Empty or invalid URL entry / 空或无效的 URL 条目"})
                failed += 1
                continue

            try:
                preview = await self._prepare_single(item_payload)
                preview["index"] = idx
                results.append(preview)
                succeeded += 1
            except Exception as exc:
                results.append({"index": idx, "source_url": url, "error": str(exc)})
                failed += 1

        return {
            "batch_id": batch_id,
            "total": len(source_urls),
            "succeeded": succeeded,
            "failed": failed,
            "results": results,
        }

    # ══════════════════════════════════════════════════════════════
    #  Preview & visibility / 预览和可见性
    # ══════════════════════════════════════════════════════════════

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

    async def update_rules(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Re-apply rules to an existing job without re-importing.
        Rules are merged incrementally: pricing/images/variant_overrides replace by family;
        content merges by field.
        """
        job_id = str(payload.get("job_id") or "").strip()
        if not job_id:
            raise ValueError(
                "job_id is required. RECOVERY: Use the job_id from prepare_import_candidate. "
                "If lost, re-import the product."
            )
        job = self._store.load(job_id)
        if not job.get("original_draft"):
            raise ValueError(
                "Cannot re-apply rules: original draft data has expired. "
                "RECOVERY: Re-import the product with prepare_import_candidate."
            )

        existing_rules = job.get("effective_rules_snapshot") or job.get("rules") or {}
        incoming_rules = payload.get("rules") or {}
        merged = merge_rules(existing_rules, incoming_rules)

        target_store = payload.get("target_store") or job.get("target_store")
        caps = await self._provider.get_rule_capabilities(target_store)
        validated = normalize_rules(merged, caps.get("rule_families"))
        if validated.get("errors"):
            raise ValueError(
                "Rule validation failed: " + "; ".join(validated["errors"]) +
                " RECOVERY: Fix the rule parameters and retry."
            )

        effective_rules = validated.get("effective_rules") or {}
        ruled = apply_rules(job["original_draft"], effective_rules)

        job["draft"] = ruled["draft"]
        job["requested_rules"] = validated.get("requested_rules") or {}
        job["effective_rules_snapshot"] = effective_rules
        job["rules"] = effective_rules
        job["rule_summary"] = ruled.get("summary") or {}
        job["status"] = "preview_ready"
        job["updated_at"] = _utc_now()
        if payload.get("target_store"):
            job["target_store"] = payload["target_store"]
        if payload.get("visibility_mode"):
            job["visibility_mode"] = payload["visibility_mode"]

        save_warnings: List[str] = []
        try:
            save_result = await self._provider.save_draft(
                job.get("provider_state") or {}, job["draft"]
            )
            save_warnings.extend(save_result.get("warnings") or [])
        except Exception:
            job["status"] = "persist_failed"
            save_warnings.append(
                "CRITICAL: Rules were applied locally but failed to save to DSers backend. "
                "Pushing this job will use OLD rules. Re-import the product or retry rule update."
            )

        job["warnings"] = [
            f"Rule re-applied at {job['updated_at']}",
            *(validated.get("warnings") or []),
            *((ruled.get("summary") or {}).get("warnings") or []),
            *save_warnings,
        ]
        self._store.save(job_id, job)
        return self._preview(job)

    async def set_product_visibility(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Change visibility_mode (backend_only / sell_immediately) before confirmation.
        在确认推送前更改 visibility_mode（backend_only / sell_immediately）。
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

    # ══════════════════════════════════════════════════════════════
    #  Step 3: Push — single, batch, multi-store
    #  步骤 3：推送 —— 单条、批量、多店铺
    # ══════════════════════════════════════════════════════════════

    async def confirm_push_to_store(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Unified entry point for single, batch, and multi-store push.
        单条、批量、多店铺推送的统一入口。

        Modes:
          - job_id (str)               → single push (backward-compatible)
          - job_ids (list)             → batch push
          - target_stores (list)       → one job to N stores
          - job_ids + target_stores    → N jobs x M stores (cartesian)

        模式：
          - job_id（字符串）           → 单条推送（向后兼容）
          - job_ids（列表）            → 批量推送
          - target_stores（列表）      → 一个 job 推 N 个店铺
          - job_ids + target_stores    → N 个 job x M 个店铺（笛卡尔积）
        """
        job_ids = payload.get("job_ids")
        target_stores = payload.get("target_stores")

        # Batch mode: job_ids is a list.
        # 批量模式：job_ids 是列表。
        if isinstance(job_ids, list):
            return await self._batch_push(payload, job_ids)

        # Single job_id, but possibly multi-store.
        # 单条 job_id，但可能多店铺。
        if isinstance(target_stores, list) and len(target_stores) > 0:
            return await self._multi_store_push_single_job(payload, target_stores)

        # Pure single mode (original behaviour).
        # 纯单条模式（原始行为）。
        return await self._push_single(payload)

    async def _push_single(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Original single-item push pipeline (fully backward-compatible).
        原始单条推送流水线（完全向后兼容）。
        """
        job_id = str(payload.get("job_id") or "").strip()
        if not job_id:
            raise ValueError("job_id is required")

        job = self._store.load(job_id)

        # Block push if rule persistence failed
        if job.get("status") == "persist_failed":
            raise ValueError(
                "push_blocked_persist_failed: Rules were applied locally but failed to persist to DSers backend. "
                "Pushing now would use OLD rules. "
                "RECOVERY: Call update_rules to retry, or re-import the product."
            )

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
        force_push = bool(payload.get("force_push") or effective_push_options.get("force_push"))

        # Pre-push safety checks
        from dsers_mcp_product.push_guard import validate_push_safety
        safety = validate_push_safety(job.get("draft") or {}, job.get("original_draft"))
        if safety["blocked"] and not force_push:
            raise ValueError(
                "push_blocked_by_safety_check: " + " | ".join(safety["blocked"]) +
                " RECOVERY: Fix pricing with update_rules, or set force_push=true after confirming the risk."
            )

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

    async def _multi_store_push_single_job(self, payload: Dict[str, Any], target_stores: List[str]) -> Dict[str, Any]:
        """
        Push a single job_id to multiple stores.
        将一个 job_id 推送到多个店铺。
        """
        batch_id = f"batch-{_uuid.uuid4().hex[:12]}"
        job_id = str(payload.get("job_id") or "").strip()
        if not job_id:
            return {"error": "job_id is required when using target_stores / 使用 target_stores 时需要提供 job_id"}

        results: List[Dict[str, Any]] = []
        succeeded = 0
        failed = 0

        for store in target_stores:
            store_name = str(store).strip()
            if not store_name:
                results.append({"job_id": job_id, "target_store": "", "error": "Empty store name / 空店铺名称"})
                failed += 1
                continue
            single_payload = dict(payload)
            single_payload["job_id"] = job_id
            single_payload["target_store"] = store_name
            single_payload.pop("target_stores", None)
            try:
                result = await self._push_single(single_payload)
                result["target_store"] = store_name
                results.append(result)
                succeeded += 1
            except Exception as exc:
                results.append({"job_id": job_id, "target_store": store_name, "error": str(exc)})
                failed += 1

        return {
            "batch_id": batch_id,
            "total": len(target_stores),
            "succeeded": succeeded,
            "failed": failed,
            "results": results,
        }

    async def _batch_push(self, payload: Dict[str, Any], job_ids: List[Any]) -> Dict[str, Any]:
        """
        Batch push: iterate over job_ids, expand multi-store combinations.
        Each item in job_ids can be a plain string or an object with per-item overrides.

        批量推送：遍历 job_ids，展开多店铺组合。
        job_ids 中每项可以是纯字符串或带单条覆盖的对象。
        """
        if not job_ids:
            return {"error": "job_ids must be a non-empty list / job_ids 不能为空列表"}

        batch_id = f"batch-{_uuid.uuid4().hex[:12]}"
        batch_target_stores = payload.get("target_stores")
        batch_target_store = payload.get("target_store")
        batch_visibility = payload.get("visibility_mode")
        batch_push_options = payload.get("push_options")

        # Build the (job_id, store, push_options) task list.
        # 构建 (job_id, store, push_options) 任务列表。
        tasks = _expand_push_tasks(
            job_ids,
            batch_target_stores=batch_target_stores,
            batch_target_store=batch_target_store,
            batch_visibility=batch_visibility,
            batch_push_options=batch_push_options,
        )

        results: List[Dict[str, Any]] = []
        succeeded = 0
        failed = 0

        for task in tasks:
            if task.get("error"):
                results.append(task)
                failed += 1
                continue
            try:
                result = await self._push_single(task["payload"])
                result["target_store"] = task["target_store"]
                results.append(result)
                succeeded += 1
            except Exception as exc:
                results.append({
                    "job_id": task.get("job_id", ""),
                    "target_store": task.get("target_store", ""),
                    "error": str(exc),
                })
                failed += 1

        return {
            "batch_id": batch_id,
            "total": len(tasks),
            "succeeded": succeeded,
            "failed": failed,
            "results": results,
        }

    # ══════════════════════════════════════════════════════════════
    #  Status & preview / 状态查询和预览
    # ══════════════════════════════════════════════════════════════

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

def _parse_batch_item(
    item: Any,
    shared: Dict[str, Any],
    shared_rules: Any,
) -> tuple:
    """
    Parse one element from source_urls into (url, payload_dict).
    Each item can be a plain URL string or a dict with per-item overrides.

    解析 source_urls 中的一个元素为 (url, payload_dict)。
    每项可以是纯 URL 字符串或带单条覆盖的字典。
    """
    if isinstance(item, str):
        url = item.strip()
        if not url:
            return "", {}
        merged = dict(shared)
        merged["source_url"] = url
        if shared_rules:
            merged.setdefault("rules", shared_rules)
        return url, merged

    if isinstance(item, dict):
        url = str(item.get("url") or item.get("source_url") or "").strip()
        if not url:
            return "", {}
        merged = dict(shared)
        merged["source_url"] = url
        for key in ("source_hint", "country", "target_store", "visibility_mode"):
            if item.get(key) is not None:
                merged[key] = item[key]
        merged["rules"] = item.get("rules") or shared_rules or {}
        return url, merged

    return "", {}


def _expand_push_tasks(
    job_ids: List[Any],
    batch_target_stores: Any,
    batch_target_store: Any,
    batch_visibility: Any,
    batch_push_options: Any,
) -> List[Dict[str, Any]]:
    """
    Expand job_ids (possibly with per-item overrides) and target_stores
    into a flat list of push tasks. Each task is either:
      {"payload": {...}, "job_id": ..., "target_store": ...}   (valid)
      {"job_id": ..., "target_store": ..., "error": ...}       (skip)

    将 job_ids（可能带单条覆盖）和 target_stores 展开为扁平的推送任务列表。
    """
    tasks: List[Dict[str, Any]] = []

    for item in job_ids:
        job_id, item_stores, item_push_options, item_visibility = _parse_push_item(
            item, batch_target_stores, batch_target_store, batch_visibility, batch_push_options,
        )

        if not job_id:
            tasks.append({"job_id": "", "target_store": "", "error": "Empty or invalid job_id entry / 空或无效的 job_id 条目"})
            continue

        if not item_stores:
            # No explicit stores → single push with whatever target_store resolves to.
            # 没有明确指定店铺 → 使用解析出的 target_store 进行单次推送。
            payload: Dict[str, Any] = {"job_id": job_id}
            if item_push_options is not None:
                payload["push_options"] = item_push_options
            if item_visibility:
                payload["visibility_mode"] = item_visibility
            tasks.append({"payload": payload, "job_id": job_id, "target_store": ""})
            continue

        for store in item_stores:
            store_name = str(store).strip()
            if not store_name:
                tasks.append({"job_id": job_id, "target_store": "", "error": "Empty store name / 空店铺名称"})
                continue
            payload = {"job_id": job_id, "target_store": store_name}
            if item_push_options is not None:
                payload["push_options"] = item_push_options
            if item_visibility:
                payload["visibility_mode"] = item_visibility
            tasks.append({"payload": payload, "job_id": job_id, "target_store": store_name})

    return tasks


def _parse_push_item(
    item: Any,
    batch_target_stores: Any,
    batch_target_store: Any,
    batch_visibility: Any,
    batch_push_options: Any,
) -> tuple:
    """
    Parse one element from job_ids into (job_id, stores_list, push_options, visibility).
    Per-item values override batch-level values.

    解析 job_ids 中的一个元素为 (job_id, stores_list, push_options, visibility)。
    单条值覆盖批次级值。
    """
    if isinstance(item, str):
        job_id = item.strip()
        stores = list(batch_target_stores) if isinstance(batch_target_stores, list) else (
            [batch_target_store] if batch_target_store else []
        )
        return job_id, stores, batch_push_options, batch_visibility

    if isinstance(item, dict):
        job_id = str(item.get("job_id") or "").strip()
        # Per-item stores: target_stores > target_store > batch fallback.
        # 单条店铺优先级：target_stores > target_store > 批次级回退。
        item_target_stores = item.get("target_stores")
        item_target_store = item.get("target_store")
        if isinstance(item_target_stores, list) and item_target_stores:
            stores = item_target_stores
        elif item_target_store:
            stores = [item_target_store]
        elif isinstance(batch_target_stores, list) and batch_target_stores:
            stores = list(batch_target_stores)
        elif batch_target_store:
            stores = [batch_target_store]
        else:
            stores = []

        push_options = item.get("push_options") if item.get("push_options") is not None else batch_push_options
        visibility = item.get("visibility_mode") or batch_visibility
        return job_id, stores, push_options, visibility

    return "", [], batch_push_options, batch_visibility


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
