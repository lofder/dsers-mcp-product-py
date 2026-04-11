"""
Import Provider — Abstract interface and dynamic loader.
导入提供者 —— 抽象接口与动态加载器

This module defines the ImportProvider contract that all vendor adapters
must implement. It also provides load_provider(), which reads an env var
to decide which concrete adapter to instantiate. This design keeps the
public protocol layer completely decoupled from any specific dropshipping
platform.

本模块定义了所有供应商适配器必须实现的 ImportProvider 契约，同时提供
load_provider() 函数，通过读取环境变量来决定实例化哪个具体适配器。
这种设计使公开协议层与任何特定代发货平台完全解耦。
"""
from __future__ import annotations

import importlib
import os
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class ImportProvider(ABC):
    """
    Provider contract for scenario-first import workflows.
    场景优先导入工作流的提供者契约。

    Every vendor adapter (DSers, CJ, etc.) implements this interface.
    The three methods map directly to the import lifecycle:
      1. get_rule_capabilities  → discover what the adapter supports
      2. prepare_candidate      → import a product and build a draft
      3. commit_candidate       → push the finalised draft to a store

    每个供应商适配器（DSers、CJ 等）都实现此接口。
    三个方法直接对应导入生命周期：
      1. get_rule_capabilities  → 查询适配器支持的能力
      2. prepare_candidate      → 导入商品并构建草稿
      3. commit_candidate       → 将最终草稿推送到店铺
    """

    name = "abstract"

    @abstractmethod
    async def get_rule_capabilities(self, target_store: Optional[str] = None) -> Dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def prepare_candidate(
        self,
        source_url: str,
        source_hint: str,
        country: str,
    ) -> Dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def commit_candidate(
        self,
        provider_state: Dict[str, Any],
        draft: Dict[str, Any],
        target_store: Optional[str],
        visibility_mode: str,
        push_options: Dict[str, Any],
    ) -> Dict[str, Any]:
        raise NotImplementedError

    # ── Browse / search methods (v1.5) ──

    async def find_products(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return {"items": [], "search_after": ""}

    async def list_import_items(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return {"items": [], "total": 0}

    async def list_my_products(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return {"items": [], "total": 0}

    async def delete_import_item(self, import_item_id: str) -> Dict[str, Any]:
        return {}

    async def save_draft(self, provider_state: Dict[str, Any], draft: Dict[str, Any]) -> Dict[str, Any]:
        return {"warnings": []}

    async def get_store_pricing_rule(self, store_ref: str) -> Dict[str, Any]:
        return {"enabled": False}


def load_provider() -> ImportProvider:
    """
    Dynamically load and instantiate the configured provider adapter.
    动态加载并实例化已配置的提供者适配器。

    The env var IMPORT_PROVIDER_MODULE controls which module is loaded.
    The module must expose a build_provider() factory function that
    returns an ImportProvider instance.

    环境变量 IMPORT_PROVIDER_MODULE 控制加载哪个模块。
    该模块必须暴露一个 build_provider() 工厂函数，返回 ImportProvider 实例。
    """
    module_name = os.getenv("IMPORT_PROVIDER_MODULE", "dsers_provider.provider")
    module = importlib.import_module(module_name)
    factory = getattr(module, "build_provider", None)
    if factory is None:
        raise RuntimeError(f"Provider module '{module_name}' does not expose build_provider()")
    provider = factory()
    if not isinstance(provider, ImportProvider):
        raise RuntimeError(f"Provider module '{module_name}' returned an invalid provider instance")
    return provider
