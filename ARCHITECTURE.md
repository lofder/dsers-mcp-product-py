# Technical Architecture / 技术架构文档 -- DSers MCP Product (Python) v1.5.7

> **Note:** The TypeScript version is now the primary maintained version. See [dsers-mcp-product](https://github.com/lofder/dsers-mcp-product).

> [English](#english) | [中文](#中文)

---

<a id="english"></a>

## English

### 1. Overview

**DSers MCP Product** is an [MCP](https://modelcontextprotocol.io/) server that gives AI Agents a complete **import -> edit -> push-to-store** workflow for dropshipping products, plus browsing, product search, rule updates, and supplier remapping.

Agents call 13 tools to go from a supplier URL to a live store listing, browse existing products, or replace suppliers -- without knowing any platform API details.

---

### 2. Directory Structure

```
dsers-mcp-product-py/
├── server.py                     # MCP server entry (stdio transport)
├── dsers_mcp_product/            # Core package -- protocol layer
│   ├── __init__.py               # Package init, version
│   ├── provider.py               # ImportProvider ABC + dynamic loading
│   ├── mock_provider.py          # Offline mock provider (dev / demo)
│   ├── service.py                # ImportFlowService -- tool orchestration
│   ├── job_store.py              # Job persistence (FileJobStore)
│   ├── push_options.py           # push_options validation & normalization
│   ├── push_guard.py             # Pre-push safety validation (price/stock checks)
│   ├── resolver.py               # Source URL resolution
│   ├── rules.py                  # Rules engine (pricing / content / images / variants / options)
│   ├── browse_service.py         # Browse operations (import list, my products, find, delete)
│   ├── browse_shared.py          # Shared browse utilities
│   ├── security.py               # Input sanitization, HTML injection blocking
│   ├── logger.py                 # Structured JSON logging
│   ├── concurrency.py            # Async concurrency utilities
│   ├── error_map.py              # Standardized error code mapping
│   ├── sku_matcher.py            # SKU-level variant matching engine
│   ├── sku_remap_service.py      # Supplier remap orchestration (strict + discover)
│   └── smithery_entry.py         # Smithery platform entry point
├── dsers_provider/               # DSers adapter layer
│   ├── __init__.py
│   └── provider.py               # PrivateDsersProvider -- ImportProvider impl
├── vendor-dsers/                 # DSers platform API library
│   ├── dsers_mcp_base/           # Infrastructure: auth, HTTP client, config
│   │   ├── auth.py
│   │   ├── client.py
│   │   └── config.py
│   ├── dsers_account.py          # Account & store management
│   ├── dsers_product.py          # Product import, push, status
│   ├── dsers_settings.py         # Shipping templates & config
│   ├── dsers_order.py            # Order management
│   └── dsers_logistics.py        # Logistics tracking
├── tests/                        # Test suite
├── smoke_mock.py                 # Mock provider smoke test
├── smoke_dsers.py                # DSers provider smoke test
├── SKILL.md                      # AI Agent skill guide (English)
├── SKILL-CN.md                   # AI Agent skill guide (Chinese)
├── ARCHITECTURE.md               # This document
├── USAGE.md                      # User guide
├── .env.example                  # Environment variable template
├── pyproject.toml                # Project metadata
├── requirements.txt              # Python dependencies
├── smithery.yaml                 # Smithery config
├── .gitignore
└── LICENSE
```

---

### 3. Three-Layer Architecture

```
┌─────────────────────────────────────────────┐
│  MCP Client (Claude / Cursor / Agent)       │
└──────────────────┬──────────────────────────┘
                   │ MCP Protocol (stdio)
┌──────────────────▼──────────────────────────┐
│  server.py + dsers_mcp_product/             │
│  ┌────────────────────────────────────────┐ │
│  │  ImportFlowService (orchestration)     │ │
│  │  ├─ Rules Engine                       │ │
│  │  ├─ Push Options   normalization       │ │
│  │  ├─ Push Guard     safety validation   │ │
│  │  ├─ Job Store      state persistence   │ │
│  │  ├─ Browse Service  list/search/delete │ │
│  │  ├─ SKU Remap      supplier swap       │ │
│  │  ├─ Security       input sanitization  │ │
│  │  └─ Logger         structured logging  │ │
│  └──────────────┬─────────────────────────┘ │
│                 │ ImportProvider ABC         │
│  ┌──────────────▼─────────────────────────┐ │
│  │  dsers_provider/ (adapter layer)       │ │
│  │  ├─ prepare_candidate()                │ │
│  │  ├─ commit_candidate()                 │ │
│  │  └─ get_rule_capabilities()            │ │
│  └──────────────┬─────────────────────────┘ │
│                 │ vendor library (sys.path)  │
│  ┌──────────────▼─────────────────────────┐ │
│  │  vendor-dsers/ (platform API lib)      │ │
│  │  ├─ dsers_mcp_base/  infrastructure    │ │
│  │  ├─ dsers_product    product API       │ │
│  │  ├─ dsers_account    account API       │ │
│  │  └─ dsers_settings   config API        │ │
│  └────────────────────────────────────────┘ │
└─────────────────────────────────────────────┘
```

| Layer | Directory | Responsibility | Replaceable |
|-------|-----------|----------------|-------------|
| **Protocol** | `dsers_mcp_product/` | 13 MCP tools, prepare -> review -> push orchestration, browsing, SKU remap | Fixed |
| **Adapter** | `dsers_provider/` | Implements `ImportProvider`, translates platform-agnostic requests into platform-specific calls | Swappable |
| **Platform Lib** | `vendor-dsers/` | Low-level HTTP API wrappers (auth, product, order, logistics) | Replaced with adapter |

---

### 4. Module Descriptions

#### 4.1 Core Modules

| Module | File | Purpose |
|--------|------|---------|
| **ImportFlowService** | `service.py` | Central orchestrator for all 13 tools. Manages the import-edit-push pipeline. |
| **Rules Engine** | `rules.py` | Applies pricing (3 modes), content, images, variant_overrides, and option_edits. Validates and normalizes rule objects. |
| **Push Options** | `push_options.py` | Validates and normalizes push configuration (image strategy, pricing behavior, shipping profiles). |
| **Job Store** | `job_store.py` | Persists job state to disk (FileJobStore). Tracks status transitions: preview_ready -> push_requested -> completed/failed. |
| **Provider** | `provider.py` | ImportProvider ABC with dynamic module loading via `IMPORT_PROVIDER_MODULE`. |
| **Resolver** | `resolver.py` | Parses and normalizes supplier URLs. Detects platform (AliExpress, Alibaba, 1688). |

#### 4.2 v1.5.7 Additions

| Module | File | Purpose |
|--------|------|---------|
| **Push Guard** | `push_guard.py` | Pre-push safety validation. Blocks: sell < cost, zero stock. Warns: low margin, low stock, low price. |
| **Browse Service** | `browse_service.py` | Handles `dsers_find_product`, `dsers_import_list`, `dsers_my_products`, `dsers_product_delete`. |
| **Browse Shared** | `browse_shared.py` | Shared utilities for browse operations (pagination, formatting). |
| **Security** | `security.py` | Input sanitization. Strips script tags, event handlers, and dangerous HTML from description fields. Validates string inputs. |
| **Logger** | `logger.py` | Structured JSON logging with configurable levels. Logs tool invocations, provider calls, and errors. |
| **Concurrency** | `concurrency.py` | Async concurrency utilities for batch operations. |
| **Error Map** | `error_map.py` | Maps internal error codes to user-facing messages with actionable guidance. |
| **SKU Matcher** | `sku_matcher.py` | Variant-level matching engine. Compares SKU attributes (name, image, price) between old and new suppliers. Calculates confidence scores. |
| **SKU Remap Service** | `sku_remap_service.py` | Orchestrates supplier replacement. Two paths: strict (exact URL) and discover (reverse-image search + multi-factor ranking). Preview and apply modes. |

---

### 5. Tool Flow

#### 5.1 Full Push Flow

```
Agent                              MCP Server
  │                                    │
  ├─ get_rule_capabilities() ────────► │ returns rules / stores / channels
  │                                    │
  ├─ validate_rules({rules}) ────────► │ validates rule structure
  │                                    │
  ├─ prepare_import_candidate() ─────► │ resolve URL -> import -> apply rules
  │                                    │ -> push_guard pre-check
  │                                    │ returns job_id + draft preview
  │                                    │
  ├─ get_import_preview(job_id) ─────► │ view edited draft
  │                                    │
  ├─ set_product_visibility() ───────► │ (optional) adjust visibility
  │                                    │
  ├─ confirm_push_to_store() ────────► │ push_guard validates -> commit push
  │                                    │ returns completed / failed
  │                                    │
  └─ get_job_status(job_id) ─────────► │ query final status
```

#### 5.2 SKU Remap Flow

```
Agent                              MCP Server
  │                                    │
  ├─ dsers_my_products(store_id) ────► │ list store products
  │                                    │
  ├─ dsers_sku_remap(mode=preview) ──► │ fetch candidates -> sku_matcher
  │                                    │ returns match plan + diffs
  │                                    │
  └─ dsers_sku_remap(mode=apply) ────► │ persist swap -> poll status
                                       │ returns process_status
```

#### 5.3 Tool Summary

| # | Tool | Description | Required Params |
|---|------|-------------|-----------------|
| 1 | `get_rule_capabilities` | Query stores, rule families, push options | -- |
| 2 | `validate_rules` | Validate rule structure, return normalized object | `rules` |
| 3 | `prepare_import_candidate` | Import from URL(s), apply rules | `source_url` or `source_urls` |
| 4 | `get_import_preview` | View prepared job preview | `job_id` |
| 5 | `set_product_visibility` | Change visibility | `job_id`, `visibility_mode` |
| 6 | `confirm_push_to_store` | Push to store(s) with safety validation | `job_id` or `job_ids` |
| 7 | `get_job_status` | Query push status | `job_id` |
| 8 | `dsers_product_update_rules` | Update rules on existing import | `job_id` |
| 9 | `dsers_find_product` | Search product pool | `keyword` or `image_url` |
| 10 | `dsers_import_list` | Browse import list | -- |
| 11 | `dsers_my_products` | Browse store products | `store_id` |
| 12 | `dsers_product_delete` | Delete from import list | `import_item_id` |
| 13 | `dsers_sku_remap` | Replace supplier with SKU matching | `dsers_product_id`, `store_id` |

---

### 6. Provider Extension

#### 6.1 ImportProvider Interface

```python
class ImportProvider(ABC):
    name = "abstract"

    async def get_rule_capabilities(self, target_store=None) -> dict: ...
    async def prepare_candidate(self, source_url, source_hint, country) -> dict: ...
    async def commit_candidate(self, provider_state, draft, target_store,
                                visibility_mode, push_options) -> dict: ...
```

#### 6.2 Adding a New Provider

1. Create `your_provider/provider.py` implementing the three `ImportProvider` methods
2. Expose a `build_provider()` factory function
3. Set `IMPORT_PROVIDER_MODULE=your_provider.provider`

#### 6.3 Provider Loading

`load_provider()` dynamically imports the module specified by `IMPORT_PROVIDER_MODULE` and calls its `build_provider()` factory. Defaults to `dsers_provider.provider`.

---

### 7. DSers Adapter Details

#### 7.1 Authentication Flow

```
DSersConfig.from_env() -> email / password
        │
DSersClient.__init__() -> try restoring from session_file
        │
first / expired -> POST /passport/login -> get session_id -> cache to session_file
        │
subsequent -> Bearer {session_id} header
```

#### 7.2 vendor-dsers Dynamic Loading

`PrivateDsersProvider.__init__()` adds `vendor-dsers/` to `sys.path`, then uses `importlib` to dynamically load each business module's `register()` function to obtain handlers.

#### 7.3 Shipping Profile Auto-Discovery

During push to Shopify stores, the Delivery Profile is handled automatically:
1. Calls `GET /import-list/shopify/shipping-profile/get` to fetch all Shopify delivery profiles
2. Picks the profile with `isChecked=true` (the default configured in DSers web UI)
3. If `push_options.shipping_profile_name` is specified, matches by name instead
4. Falls back to `push_options.store_shipping_profile` for manual override
5. Non-Shopify stores (Wix, WooCommerce) skip this step entirely

`get_rule_capabilities` also returns `shipping_profiles` for each Shopify store (name, is_default, countries, rate) so agents can display available profiles to the user.

---

### 8. Security Layer (v1.5.7)

#### 8.1 Input Sanitization (`security.py`)

- Strips `<script>` tags from description HTML fields
- Removes event handler attributes (`onclick`, `onerror`, etc.)
- Validates string length limits on all user-provided inputs
- Returns warnings in the response when content is sanitized

#### 8.2 Pricing Safety

- Extreme pricing values trigger warnings (multiplier >100x, fixed_markup >$500, fixed_price >$10,000)
- Push guard blocks sell-below-cost scenarios
- Zero-stock products are blocked from push

#### 8.3 Credential Safety

- `.env` files never committed (excluded in `.gitignore`)
- Session caches (`.session-cache/`, `.session.json`) excluded in `.gitignore`
- Credentials injected via environment variables, no hardcoding
- All API calls go through `DSersClient` which manages sessions centrally

---

### 9. SKU Remap Subsystem

#### 9.1 Architecture

```
dsers_sku_remap (tool)
       │
       ▼
sku_remap_service.py (orchestration)
       │
       ├── Strict path: fetch new supplier -> sku_matcher -> map variants
       │
       └── Discover path: reverse-image search -> rank candidates -> sku_matcher -> map variants
                │
                ▼
         sku_matcher.py (matching engine)
              │
              ├── Compare SKU name similarity
              ├── Compare variant images
              ├── Compare price proximity
              └── Calculate confidence score (0-100)
```

#### 9.2 Modes

| Mode | Behavior |
|------|----------|
| `preview` | Read-only. Returns match plan, diffs, candidates. Nothing is written to DSers. |
| `apply` | Persists the supplier swap. Polls DSers for process_status confirmation. |

#### 9.3 Confidence Scoring

`sku_matcher.py` calculates a confidence score (0-100) for each variant mapping based on:
- Name similarity (fuzzy string matching)
- Image similarity (when available)
- Price proximity
- Option value alignment

Variants below `auto_confidence` (default 70) are kept on the old supplier.

---

### 10. Logger and Concurrency

#### 10.1 Structured Logging (`logger.py`)

- JSON-formatted log entries with timestamp, level, tool name, and context
- Configurable log levels
- Logs tool invocations, provider calls, validation results, and errors

#### 10.2 Concurrency (`concurrency.py`)

- Async utilities for batch import and batch push operations
- Controlled parallelism to avoid overwhelming DSers API rate limits

---

### 11. Push Options

| Option | Type | Description |
|--------|------|-------------|
| `publish_to_online_store` | `bool` | Publish to online storefront |
| `only_push_specifications` | `bool` | Push specification data only |
| `image_strategy` | `str` | `selected_only` / `all_available` |
| `pricing_rule_behavior` | `str` | `keep_manual` / `apply_store_pricing_rule` |
| `auto_inventory_update` | `bool` | Auto-sync inventory |
| `auto_price_update` | `bool` | Auto-sync price |
| `sales_channels` | `list` | Sales channel identifiers |
| `shipping_profile_name` | `str` | Shopify delivery profile name -- auto-picks default if omitted |
| `store_shipping_profile` | `list` | Manual override: raw delivery profile bindings (rarely needed) |

---

### 12. Local Development

#### 12.1 Setup

```bash
git clone https://github.com/lofder/dsers-mcp-product-py.git && cd dsers-mcp-product-py
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your credentials
```

#### 12.2 Smoke Tests

```bash
python smoke_mock.py                      # offline, no credentials
python smoke_dsers.py                     # needs .env credentials
SAMPLE_IMPORT_URL="https://..." python smoke_dsers.py   # with real import
```

#### 12.3 Run as MCP Server

```bash
python server.py
```

Cursor MCP config:

```json
{
  "mcpServers": {
    "dsers-mcp-product": {
      "command": "python",
      "args": ["server.py"],
      "cwd": "/path/to/dsers-mcp-product-py"
    }
  }
}
```

---

### 13. Known Limitations & Roadmap

| Status | Description |
|--------|-------------|
| Done | Production API (`DSERS_ENV=production` default) |
| Done | Batch import and batch push support |
| Done | Multi-store push (1 product x N stores) |
| Done | Shopify shipping profile auto-discovery via dedicated API |
| Done | Multi-platform targets: Shopify, Wix, WooCommerce |
| Done | Multi-source: AliExpress, Alibaba, 1688 |
| Done | Full rules engine: pricing (3 modes), content, images, variant_overrides, option_edits |
| Done | Push safety guards (price/stock validation) |
| Done | SKU remap with strict and discover modes |
| Done | Browse tools: import list, my products, find, delete |
| Done | Security: HTML injection blocking, input sanitization |
| Done | Structured logging |
| Next | Support additional platform providers (non-DSers) |
| Next | AliExpress bundle URL support |

---
---

<a id="中文"></a>

## 中文

### 1. 项目定位

**DSers MCP Product** 是一个基于 [MCP](https://modelcontextprotocol.io/) 的服务器，为 AI Agent 提供一件代发商品的**导入 -> 编辑 -> 推送到店铺**完整工作流，以及浏览、商品搜索、规则更新和供应商重映射功能。

Agent 调用 13 个工具即可完成从供应商 URL 到店铺上架、浏览已有商品或替换供应商的全过程，无需了解底层平台 API 细节。

---

### 2. 目录结构

```
dsers-mcp-product-py/
├── server.py                     # MCP 服务入口 (stdio transport)
├── dsers_mcp_product/            # 核心包 -- 协议层
│   ├── __init__.py               # 包初始化、版本
│   ├── provider.py               # ImportProvider 抽象基类 + 动态加载
│   ├── mock_provider.py          # 离线 Mock Provider（开发/演示）
│   ├── service.py                # ImportFlowService -- 工具编排层
│   ├── job_store.py              # 作业持久化 (FileJobStore)
│   ├── push_options.py           # push_options 校验与归一化
│   ├── push_guard.py             # 预推送安全校验（价格/库存检查）
│   ├── resolver.py               # 来源 URL 解析
│   ├── rules.py                  # 规则引擎（定价/内容/图片/变体/选项）
│   ├── browse_service.py         # 浏览操作（导入列表、我的商品、搜索、删除）
│   ├── browse_shared.py          # 共享浏览工具
│   ├── security.py               # 输入清洗、HTML 注入拦截
│   ├── logger.py                 # 结构化 JSON 日志
│   ├── concurrency.py            # 异步并发工具
│   ├── error_map.py              # 标准化错误代码映射
│   ├── sku_matcher.py            # SKU 级别变体匹配引擎
│   ├── sku_remap_service.py      # 供应商重映射编排（精确 + 发现）
│   └── smithery_entry.py         # Smithery 平台入口
├── dsers_provider/               # DSers 适配层
│   ├── __init__.py
│   └── provider.py               # PrivateDsersProvider -- ImportProvider 实现
├── vendor-dsers/                 # DSers 平台 API 封装库
│   ├── dsers_mcp_base/           # 基础设施：认证、HTTP 客户端、配置
│   │   ├── auth.py
│   │   ├── client.py
│   │   └── config.py
│   ├── dsers_account.py          # 账户与店铺管理
│   ├── dsers_product.py          # 商品导入、推送、状态查询
│   ├── dsers_settings.py         # 运费模板、运输配置
│   ├── dsers_order.py            # 订单管理
│   └── dsers_logistics.py        # 物流追踪
├── tests/                        # 测试套件
├── smoke_mock.py                 # Mock Provider 冒烟测试
├── smoke_dsers.py                # DSers Provider 冒烟测试
├── SKILL.md                      # AI Agent 使用指南 (English)
├── SKILL-CN.md                   # AI Agent 使用指南（中文）
├── ARCHITECTURE.md               # 本文档
├── USAGE.md                      # 使用指南
├── .env.example                  # 环境变量模板
├── pyproject.toml                # 项目元数据
├── requirements.txt              # Python 依赖
├── smithery.yaml                 # Smithery 配置
├── .gitignore
└── LICENSE
```

---

### 3. 三层架构

```
┌─────────────────────────────────────────────┐
│  MCP Client (Claude / Cursor / Agent)       │
└──────────────────┬──────────────────────────┘
                   │ MCP Protocol (stdio)
┌──────────────────▼──────────────────────────┐
│  server.py + dsers_mcp_product/             │
│  ┌────────────────────────────────────────┐ │
│  │  ImportFlowService (协议编排层)          │ │
│  │  ├─ Rules Engine    规则校验/应用       │ │
│  │  ├─ Push Options    推送参数归一化      │ │
│  │  ├─ Push Guard      安全校验           │ │
│  │  ├─ Job Store       作业状态持久化      │ │
│  │  ├─ Browse Service  列表/搜索/删除     │ │
│  │  ├─ SKU Remap       供应商替换         │ │
│  │  ├─ Security        输入清洗           │ │
│  │  └─ Logger          结构化日志         │ │
│  └──────────────┬─────────────────────────┘ │
│                 │ ImportProvider ABC         │
│  ┌──────────────▼─────────────────────────┐ │
│  │  dsers_provider/ (适配层)               │ │
│  │  ├─ prepare_candidate()                │ │
│  │  ├─ commit_candidate()                 │ │
│  │  └─ get_rule_capabilities()            │ │
│  └──────────────┬─────────────────────────┘ │
│                 │ vendor library (sys.path)  │
│  ┌──────────────▼─────────────────────────┐ │
│  │  vendor-dsers/ (平台 API 库)            │ │
│  │  ├─ dsers_mcp_base/  基础设施           │ │
│  │  ├─ dsers_product    商品 API           │ │
│  │  ├─ dsers_account    账户 API           │ │
│  │  └─ dsers_settings   配置 API           │ │
│  └────────────────────────────────────────┘ │
└─────────────────────────────────────────────┘
```

| 层级 | 目录 | 职责 | 可替换性 |
|------|------|------|----------|
| **协议层** | `dsers_mcp_product/` | 定义 13 个 MCP 工具，编排 prepare -> review -> push 流程，浏览，SKU 重映射 | 固定 |
| **适配层** | `dsers_provider/` | 实现 `ImportProvider` 接口，转换平台无关请求为平台特定调用 | 可替换为其他平台 |
| **平台库** | `vendor-dsers/` | 封装底层 HTTP API（认证、商品、订单、物流） | 随适配层一同替换 |

---

### 4. 模块说明

#### 4.1 核心模块

| 模块 | 文件 | 用途 |
|------|------|------|
| **ImportFlowService** | `service.py` | 所有 13 个工具的中央编排器。管理导入-编辑-推送管道。 |
| **Rules Engine** | `rules.py` | 应用定价（3 种模式）、内容、图片、变体覆盖和选项编辑。校验并归一化规则对象。 |
| **Push Options** | `push_options.py` | 校验和归一化推送配置（图片策略、定价行为、配送方案）。 |
| **Job Store** | `job_store.py` | 将作业状态持久化到磁盘（FileJobStore）。跟踪状态转换：preview_ready -> push_requested -> completed/failed。 |
| **Provider** | `provider.py` | ImportProvider 抽象基类，通过 `IMPORT_PROVIDER_MODULE` 动态加载模块。 |
| **Resolver** | `resolver.py` | 解析和归一化供应商 URL。检测平台（AliExpress、Alibaba、1688）。 |

#### 4.2 v1.5.7 新增模块

| 模块 | 文件 | 用途 |
|------|------|------|
| **Push Guard** | `push_guard.py` | 预推送安全校验。阻止：售价 < 成本、零库存。警告：低利润、低库存、低价格。 |
| **Browse Service** | `browse_service.py` | 处理 `dsers_find_product`、`dsers_import_list`、`dsers_my_products`、`dsers_product_delete`。 |
| **Browse Shared** | `browse_shared.py` | 浏览操作的共享工具（分页、格式化）。 |
| **Security** | `security.py` | 输入清洗。从描述字段剥离 script 标签、事件处理器和危险 HTML。校验字符串输入。 |
| **Logger** | `logger.py` | 结构化 JSON 日志，可配置级别。记录工具调用、Provider 调用和错误。 |
| **Concurrency** | `concurrency.py` | 批量操作的异步并发工具。 |
| **Error Map** | `error_map.py` | 将内部错误代码映射为用户友好的消息和可操作的指引。 |
| **SKU Matcher** | `sku_matcher.py` | 变体级别匹配引擎。比较新旧供应商的 SKU 属性（名称、图片、价格），计算置信度分数。 |
| **SKU Remap Service** | `sku_remap_service.py` | 编排供应商替换。两种路径：精确（指定 URL）和发现（反向图片搜索 + 多因素排名）。预览和应用模式。 |

---

### 5. 工具流程

#### 5.1 完整推送流程

```
Agent                              MCP Server
  │                                    │
  ├─ get_rule_capabilities() ────────► │ 返回支持的规则/店铺/渠道
  │                                    │
  ├─ validate_rules({rules}) ────────► │ 校验规则结构
  │                                    │
  ├─ prepare_import_candidate() ─────► │ 解析 URL -> 导入 -> 应用规则
  │                                    │ -> push_guard 预检查
  │                                    │ 返回 job_id + draft 预览
  │                                    │
  ├─ get_import_preview(job_id) ─────► │ 查看编辑后的商品草稿
  │                                    │
  ├─ set_product_visibility() ───────► │ (可选) 调整可见性
  │                                    │
  ├─ confirm_push_to_store() ────────► │ push_guard 校验 -> 提交推送
  │                                    │ 返回 completed / failed
  │                                    │
  └─ get_job_status(job_id) ─────────► │ 查询最终状态
```

#### 5.2 SKU 重映射流程

```
Agent                              MCP Server
  │                                    │
  ├─ dsers_my_products(store_id) ────► │ 列出店铺商品
  │                                    │
  ├─ dsers_sku_remap(mode=preview) ──► │ 获取候选 -> sku_matcher
  │                                    │ 返回匹配方案 + 差异
  │                                    │
  └─ dsers_sku_remap(mode=apply) ────► │ 持久化替换 -> 轮询状态
                                       │ 返回 process_status
```

#### 5.3 工具一览

| # | 工具名 | 说明 | 必需参数 |
|---|--------|------|----------|
| 1 | `get_rule_capabilities` | 查询店铺、规则族、推送选项 | -- |
| 2 | `validate_rules` | 校验规则结构，返回归一化后的规则对象 | `rules` |
| 3 | `prepare_import_candidate` | 从 URL 导入，应用规则 | `source_url` 或 `source_urls` |
| 4 | `get_import_preview` | 查看已准备的作业预览 | `job_id` |
| 5 | `set_product_visibility` | 修改可见性 | `job_id`, `visibility_mode` |
| 6 | `confirm_push_to_store` | 推送到店铺，含安全校验 | `job_id` 或 `job_ids` |
| 7 | `get_job_status` | 查询推送状态 | `job_id` |
| 8 | `dsers_product_update_rules` | 更新已导入商品的规则 | `job_id` |
| 9 | `dsers_find_product` | 搜索商品库 | `keyword` 或 `image_url` |
| 10 | `dsers_import_list` | 浏览导入列表 | -- |
| 11 | `dsers_my_products` | 浏览店铺商品 | `store_id` |
| 12 | `dsers_product_delete` | 从导入列表删除 | `import_item_id` |
| 13 | `dsers_sku_remap` | 替换供应商，SKU 匹配 | `dsers_product_id`, `store_id` |

---

### 6. Provider 扩展机制

#### 6.1 ImportProvider 接口

```python
class ImportProvider(ABC):
    name = "abstract"

    async def get_rule_capabilities(self, target_store=None) -> dict: ...
    async def prepare_candidate(self, source_url, source_hint, country) -> dict: ...
    async def commit_candidate(self, provider_state, draft, target_store,
                                visibility_mode, push_options) -> dict: ...
```

#### 6.2 新增 Provider

1. 创建 `your_provider/provider.py`，实现 `ImportProvider` 的三个方法
2. 暴露 `build_provider()` 工厂函数
3. 设置环境变量 `IMPORT_PROVIDER_MODULE=your_provider.provider`

#### 6.3 Provider 加载机制

`load_provider()` 通过 `IMPORT_PROVIDER_MODULE` 环境变量动态加载指定模块，调用其 `build_provider()` 工厂函数返回实例。默认加载 `dsers_provider.provider`。

---

### 7. DSers 适配层详解

#### 7.1 认证流程

```
DSersConfig.from_env() -> email/password
        │
DSersClient.__init__() -> 尝试从 session_file 恢复
        │
首次/过期 -> POST /passport/login -> 获取 session_id -> 缓存到 session_file
        │
后续请求 -> Bearer {session_id} header
```

#### 7.2 vendor-dsers 动态加载

`PrivateDsersProvider.__init__()` 将 `vendor-dsers/` 加入 `sys.path`，然后通过 `importlib` 动态加载各业务模块的 `register()` 函数获取 handler。

#### 7.3 Shipping Profile 自动发现

推送到 Shopify 店铺时，自动处理 Delivery Profile：
1. 调用 `GET /import-list/shopify/shipping-profile/get` 获取所有 Shopify delivery profiles
2. 选取 `isChecked=true` 的 profile（即 DSers 网页端默认选中的）
3. 如果指定了 `push_options.shipping_profile_name`，则按名称匹配
4. 回退到 `push_options.store_shipping_profile` 手动覆盖
5. 非 Shopify 店铺（Wix、WooCommerce）完全跳过此步骤

`get_rule_capabilities` 也会为每个 Shopify 店铺返回 `shipping_profiles`（名称、是否默认、覆盖国家数、运费），供 Agent 展示给用户选择。

---

### 8. 安全层 (v1.5.7)

#### 8.1 输入清洗 (`security.py`)

- 从描述 HTML 字段剥离 `<script>` 标签
- 移除事件处理器属性（`onclick`、`onerror` 等）
- 校验所有用户输入的字符串长度限制
- 内容被清洗时在响应中返回警告

#### 8.2 定价安全

- 极端定价值触发警告（倍率 >100x、固定加价 >$500、固定价格 >$10,000）
- Push guard 阻止售价低于成本的场景
- 零库存商品被阻止推送

#### 8.3 凭据安全

- `.env` 文件绝不提交到 Git -- 已在 `.gitignore` 中排除
- Session 缓存文件（`.session-cache/`、`.session.json`）已在 `.gitignore` 中排除
- 凭据通过环境变量传入，代码中无硬编码
- 所有 API 调用通过 `DSersClient` 统一管理 session

---

### 9. SKU 重映射子系统

#### 9.1 架构

```
dsers_sku_remap (工具)
       │
       ▼
sku_remap_service.py (编排)
       │
       ├── 精确路径: 获取新供应商 -> sku_matcher -> 映射变体
       │
       └── 发现路径: 反向图片搜索 -> 排名候选 -> sku_matcher -> 映射变体
                │
                ▼
         sku_matcher.py (匹配引擎)
              │
              ├── 比较 SKU 名称相似度
              ├── 比较变体图片
              ├── 比较价格接近度
              └── 计算置信度分数 (0-100)
```

#### 9.2 模式

| 模式 | 行为 |
|------|------|
| `preview` | 只读。返回匹配方案、差异、候选。不向 DSers 写入任何内容。 |
| `apply` | 持久化供应商替换。轮询 DSers 获取 process_status 确认。 |

#### 9.3 置信度评分

`sku_matcher.py` 为每个变体映射计算置信度分数（0-100），基于：
- 名称相似度（模糊字符串匹配）
- 图片相似度（如有）
- 价格接近度
- 选项值对齐

低于 `auto_confidence`（默认 70）的变体保留原供应商。

---

### 10. 日志与并发

#### 10.1 结构化日志 (`logger.py`)

- JSON 格式的日志条目，含时间戳、级别、工具名和上下文
- 可配置日志级别
- 记录工具调用、Provider 调用、校验结果和错误

#### 10.2 并发 (`concurrency.py`)

- 批量导入和批量推送操作的异步工具
- 控制并行度以避免超出 DSers API 速率限制

---

### 11. Push Options

| 选项 | 类型 | 说明 |
|------|------|------|
| `publish_to_online_store` | `bool` | 是否发布到在线店铺 |
| `only_push_specifications` | `bool` | 仅推送规格数据 |
| `image_strategy` | `str` | `selected_only` / `all_available` |
| `pricing_rule_behavior` | `str` | `keep_manual` / `apply_store_pricing_rule` |
| `auto_inventory_update` | `bool` | 自动同步库存 |
| `auto_price_update` | `bool` | 自动同步价格 |
| `sales_channels` | `list` | 销售渠道列表 |
| `shipping_profile_name` | `str` | Shopify 运费模板名称 -- 不指定则自动使用默认模板 |
| `store_shipping_profile` | `list` | 手动覆盖：原始 delivery profile 绑定（极少需要） |

---

### 12. 本地开发

#### 12.1 环境搭建

```bash
git clone https://github.com/lofder/dsers-mcp-product-py.git && cd dsers-mcp-product-py
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# 编辑 .env 填入你的凭据
```

#### 12.2 冒烟测试

```bash
python smoke_mock.py                      # 离线，无需凭据
python smoke_dsers.py                     # 需要 .env 中的凭据
SAMPLE_IMPORT_URL="https://..." python smoke_dsers.py   # 带实际导入
```

#### 12.3 作为 MCP 服务器运行

```bash
python server.py
```

在 Cursor 的 MCP 配置中添加：

```json
{
  "mcpServers": {
    "dsers-mcp-product": {
      "command": "python",
      "args": ["server.py"],
      "cwd": "/path/to/dsers-mcp-product-py"
    }
  }
}
```

---

### 13. 已知限制 & 迭代计划

| 状态 | 说明 |
|------|------|
| 已完成 | 生产环境 API（`DSERS_ENV=production` 默认） |
| 已完成 | 批量导入和批量推送 |
| 已完成 | 多店铺推送（1 个商品 x N 个店铺） |
| 已完成 | Shopify 运费模板自动发现（专用 API） |
| 已完成 | 多平台目标：Shopify、Wix、WooCommerce |
| 已完成 | 多来源：AliExpress、Alibaba、1688 |
| 已完成 | 完整规则引擎：定价（3 种模式）、内容、图片、变体覆盖、选项编辑 |
| 已完成 | 推送安全防护（价格/库存校验） |
| 已完成 | SKU 重映射（精确和发现模式） |
| 已完成 | 浏览工具：导入列表、我的商品、搜索、删除 |
| 已完成 | 安全：HTML 注入拦截、输入清洗 |
| 已完成 | 结构化日志 |
| 后续 | 支持更多平台 Provider（非 DSers） |
| 后续 | AliExpress Bundle URL 支持 |
