# Technical Architecture / 技术架构文档 — DSers MCP Product

> [English](#english) | [中文](#中文)

---

<a id="english"></a>

## English

### 1. Overview

**DSers MCP Product** is an [MCP](https://modelcontextprotocol.io/) server that gives AI Agents a complete **import → edit → push-to-store** workflow for dropshipping products.

Agents call 7 high-level tools to go from a supplier URL to a live store listing, without knowing any platform API details.

---

### 2. Directory Structure

```
dsers-mcp-product/
├── server.py                     # MCP server entry (stdio transport)
├── dsers_mcp_product/          # Core package — protocol layer
│   ├── provider.py               # ImportProvider ABC + dynamic loading
│   ├── mock_provider.py          # Offline mock provider (dev / demo)
│   ├── service.py                # ImportFlowService — tool orchestration
│   ├── job_store.py              # Job persistence (FileJobStore)
│   ├── push_options.py           # push_options validation & normalization
│   ├── resolver.py               # Source URL resolution
│   └── rules.py                  # Rules engine (pricing / content / images)
├── dsers_provider/               # DSers adapter layer
│   ├── __init__.py
│   └── provider.py               # PrivateDsersProvider — ImportProvider impl
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
├── smoke_mock.py                 # Mock provider smoke test
├── smoke_dsers.py                # DSers provider smoke test
├── SKILL.md                      # AI Agent skill guide
├── ARCHITECTURE.md               # This document
├── USAGE.md                      # User guide
├── .env.example                  # Environment variable template
├── .gitignore
├── requirements.txt
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
│  server.py + dsers_mcp_product/           │
│  ┌────────────────────────────────────────┐ │
│  │  ImportFlowService (orchestration)     │ │
│  │  ├─ Rules Engine                       │ │
│  │  ├─ Push Options   normalization       │ │
│  │  └─ Job Store      state persistence   │ │
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
| **Protocol** | `dsers_mcp_product/` | 7 MCP tools, prepare → review → push orchestration | Fixed |
| **Adapter** | `dsers_provider/` | Implements `ImportProvider`, translates platform-agnostic requests into platform-specific calls | Swappable |
| **Platform Lib** | `vendor-dsers/` | Low-level HTTP API wrappers (auth, product, order, logistics) | Replaced with adapter |

---

### 4. Tool Flow

#### 4.1 Full Push Flow

```
Agent                              MCP Server
  │                                    │
  ├─ get_rule_capabilities() ────────► │ returns rules / stores / channels
  │                                    │
  ├─ validate_rules({rules}) ────────► │ validates rule structure
  │                                    │
  ├─ prepare_import_candidate() ─────► │ resolve URL → import → apply rules
  │                                    │ returns job_id + draft preview
  │                                    │
  ├─ get_import_preview(job_id) ─────► │ view edited draft
  │                                    │
  ├─ set_product_visibility() ───────► │ (optional) adjust visibility
  │                                    │
  ├─ confirm_push_to_store() ────────► │ commit push → poll status
  │                                    │ returns completed / failed
  │                                    │
  └─ get_job_status(job_id) ─────────► │ query final status
```

#### 4.2 Tool Summary

| Tool | Description | Required Params |
|------|-------------|-----------------|
| `get_rule_capabilities` | Query stores (with Shopify shipping profiles), rule families, push options | — |
| `validate_rules` | Validate rule structure, return normalized object | `rules` |
| `prepare_import_candidate` | Import from URL(s) — single (`source_url`) or batch (`source_urls`) | `source_url` or `source_urls` |
| `get_import_preview` | View prepared job preview | `job_id` |
| `set_product_visibility` | Change visibility (backend_only / sell_immediately) | `job_id`, `visibility_mode` |
| `confirm_push_to_store` | Push to store(s) — single, batch (`job_ids`), or multi-store (`target_stores`) | `job_id` or `job_ids` |
| `get_job_status` | Query push status | `job_id` |

---

### 5. Provider Extension

#### 5.1 ImportProvider Interface

```python
class ImportProvider(ABC):
    name = "abstract"

    async def get_rule_capabilities(self, target_store=None) -> dict: ...
    async def prepare_candidate(self, source_url, source_hint, country) -> dict: ...
    async def commit_candidate(self, provider_state, draft, target_store,
                                visibility_mode, push_options) -> dict: ...
```

#### 5.2 Adding a New Provider

1. Create `your_provider/provider.py` implementing the three `ImportProvider` methods
2. Expose a `build_provider()` factory function
3. Set `IMPORT_PROVIDER_MODULE=your_provider.provider`

#### 5.3 Provider Loading

`load_provider()` dynamically imports the module specified by `IMPORT_PROVIDER_MODULE` and calls its `build_provider()` factory. Defaults to `dsers_provider.provider`.

---

### 6. DSers Adapter Details

#### 6.1 Authentication Flow

```
DSersConfig.from_env() → email / password
        │
DSersClient.__init__() → try restoring from session_file
        │
first / expired → POST /passport/login → get session_id → cache to session_file
        │
subsequent → Bearer {session_id} header
```

#### 6.2 vendor-dsers Dynamic Loading

`PrivateDsersProvider.__init__()` adds `vendor-dsers/` to `sys.path`, then uses `importlib` to dynamically load each business module's `register()` function to obtain handlers.

#### 6.3 Shipping Profile Auto-Discovery

During push to Shopify stores, the Delivery Profile is handled automatically:
1. Calls `GET /import-list/shopify/shipping-profile/get` to fetch all Shopify delivery profiles
2. Picks the profile with `isChecked=true` (the default configured in DSers web UI)
3. If `push_options.shipping_profile_name` is specified, matches by name instead
4. Falls back to `push_options.store_shipping_profile` for manual override
5. Non-Shopify stores (Wix, WooCommerce) skip this step entirely

`get_rule_capabilities` also returns `shipping_profiles` for each Shopify store (name, is_default, countries, rate) so agents can display available profiles to the user.

---

### 7. Push Options

| Option | Type | Description |
|--------|------|-------------|
| `publish_to_online_store` | `bool` | Publish to online storefront |
| `only_push_specifications` | `bool` | Push specification data only |
| `image_strategy` | `str` | `selected_only` / `all_available` |
| `pricing_rule_behavior` | `str` | `keep_manual` / `apply_store_pricing_rule` |
| `auto_inventory_update` | `bool` | Auto-sync inventory |
| `auto_price_update` | `bool` | Auto-sync price |
| `sales_channels` | `list` | Sales channel identifiers |
| `shipping_profile_name` | `str` | Shopify delivery profile name — auto-picks default if omitted |
| `store_shipping_profile` | `list` | Manual override: raw delivery profile bindings (rarely needed) |

---

### 8. Local Development

#### 8.1 Setup

```bash
git clone https://github.com/lofder/dsers-mcp-product.git && cd dsers-mcp-product
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your credentials
```

#### 8.2 Smoke Tests

```bash
python smoke_mock.py                      # offline, no credentials
python smoke_dsers.py                     # needs .env credentials
SAMPLE_IMPORT_URL="https://..." python smoke_dsers.py   # with real import
```

#### 8.3 Run as MCP Server

```bash
python server.py
```

Cursor MCP config:

```json
{
  "mcpServers": {
    "dropship-import": {
      "command": "python",
      "args": ["server.py"],
      "cwd": "/path/to/dsers-mcp-product"
    }
  }
}
```

---

### 9. Security Notes

- **`.env` files are never committed** — excluded in `.gitignore`
- **Session caches** (`.session-cache/`, `.session.json`) are excluded in `.gitignore`
- Credentials are injected via environment variables, no hardcoding in source
- All API calls in `vendor-dsers/` go through `DSersClient` which manages sessions centrally

---

### 10. Known Limitations & Roadmap

| Status | Description |
|--------|-------------|
| ✅ Done | Production API (`DSERS_ENV=production` default) |
| ✅ Done | Batch import and batch push support |
| ✅ Done | Multi-store push (1 product x N stores) |
| ✅ Done | Shopify shipping profile auto-discovery via dedicated API |
| ✅ Done | Multi-platform targets: Shopify, Wix, WooCommerce |
| ✅ Done | Multi-source: AliExpress, Alibaba, 1688 |
| 🔜 Next | Support additional platform providers (non-DSers) |
| 🔜 Next | Tag editing in rules engine |
| 🔜 Next | AliExpress bundle URL support |

---
---

<a id="中文"></a>

## 中文

### 1. 项目定位

**DSers MCP Product** 是一个基于 [MCP](https://modelcontextprotocol.io/) 的服务器，为 AI Agent 提供**一件代发商品导入 → 编辑 → 推送到店铺**的完整工作流。

Agent 只需调用 7 个高层工具，即可完成从供应商 URL 到店铺上架的全过程，无需了解底层平台 API 细节。

---

### 2. 目录结构

```
dsers-mcp-product/
├── server.py                     # MCP 服务入口 (stdio transport)
├── dsers_mcp_product/          # 核心包 — 协议层
│   ├── provider.py               # ImportProvider 抽象基类 + 动态加载
│   ├── mock_provider.py          # 离线 Mock Provider（开发/演示）
│   ├── service.py                # ImportFlowService — 工具编排层
│   ├── job_store.py              # 作业持久化 (FileJobStore)
│   ├── push_options.py           # push_options 校验与归一化
│   ├── resolver.py               # 来源 URL 解析
│   └── rules.py                  # 规则引擎（定价/内容/图片）
├── dsers_provider/               # DSers 适配层
│   ├── __init__.py
│   └── provider.py               # PrivateDsersProvider — ImportProvider 实现
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
├── smoke_mock.py                 # Mock Provider 冒烟测试
├── smoke_dsers.py                # DSers Provider 冒烟测试
├── SKILL.md                      # AI Agent 使用指南
├── ARCHITECTURE.md               # 本文档
├── USAGE.md                      # 使用指南
├── .env.example                  # 环境变量模板
├── .gitignore
├── requirements.txt
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
│  server.py + dsers_mcp_product/           │
│  ┌────────────────────────────────────────┐ │
│  │  ImportFlowService (协议编排层)          │ │
│  │  ├─ Rules Engine    规则校验/应用       │ │
│  │  ├─ Push Options    推送参数归一化      │ │
│  │  └─ Job Store       作业状态持久化      │ │
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
| **协议层** | `dsers_mcp_product/` | 定义 7 个 MCP 工具，编排 prepare → review → push 流程 | 固定 |
| **适配层** | `dsers_provider/` | 实现 `ImportProvider` 接口，转换平台无关请求为平台特定调用 | 可替换为其他平台 |
| **平台库** | `vendor-dsers/` | 封装底层 HTTP API（认证、商品、订单、物流） | 随适配层一同替换 |

---

### 4. 工具流程

#### 4.1 完整推送流程

```
Agent                              MCP Server
  │                                    │
  ├─ get_rule_capabilities() ────────► │ 返回支持的规则/店铺/渠道
  │                                    │
  ├─ validate_rules({rules}) ────────► │ 校验规则结构
  │                                    │
  ├─ prepare_import_candidate() ─────► │ 解析 URL → 导入 → 应用规则
  │                                    │ 返回 job_id + draft 预览
  │                                    │
  ├─ get_import_preview(job_id) ─────► │ 查看编辑后的商品草稿
  │                                    │
  ├─ set_product_visibility() ───────► │ (可选) 调整可见性
  │                                    │
  ├─ confirm_push_to_store() ────────► │ 提交推送 → 轮询状态
  │                                    │ 返回 completed / failed
  │                                    │
  └─ get_job_status(job_id) ─────────► │ 查询最终状态
```

#### 4.2 工具一览

| 工具名 | 说明 | 必需参数 |
|--------|------|----------|
| `get_rule_capabilities` | 查询店铺（含 Shopify 运费模板）、规则族、推送选项 | — |
| `validate_rules` | 校验规则结构，返回归一化后的规则对象 | `rules` |
| `prepare_import_candidate` | 从 URL 导入——单条（`source_url`）或批量（`source_urls`） | `source_url` 或 `source_urls` |
| `get_import_preview` | 查看已准备的作业预览 | `job_id` |
| `set_product_visibility` | 修改可见性 (backend_only / sell_immediately) | `job_id`, `visibility_mode` |
| `confirm_push_to_store` | 推送到店铺——单条、批量（`job_ids`）或多店铺（`target_stores`） | `job_id` 或 `job_ids` |
| `get_job_status` | 查询推送状态 | `job_id` |

---

### 5. Provider 扩展机制

#### 5.1 ImportProvider 接口

```python
class ImportProvider(ABC):
    name = "abstract"

    async def get_rule_capabilities(self, target_store=None) -> dict: ...
    async def prepare_candidate(self, source_url, source_hint, country) -> dict: ...
    async def commit_candidate(self, provider_state, draft, target_store,
                                visibility_mode, push_options) -> dict: ...
```

#### 5.2 新增 Provider

1. 创建 `your_provider/provider.py`，实现 `ImportProvider` 的三个方法
2. 暴露 `build_provider()` 工厂函数
3. 设置环境变量 `IMPORT_PROVIDER_MODULE=your_provider.provider`

#### 5.3 Provider 加载机制

`load_provider()` 通过 `IMPORT_PROVIDER_MODULE` 环境变量动态加载指定模块，调用其 `build_provider()` 工厂函数返回实例。默认加载 `dsers_provider.provider`。

---

### 6. DSers 适配层详解

#### 6.1 认证流程

```
DSersConfig.from_env() → email/password
        │
DSersClient.__init__() → 尝试从 session_file 恢复
        │
首次/过期 → POST /passport/login → 获取 session_id → 缓存到 session_file
        │
后续请求 → Bearer {session_id} header
```

#### 6.2 vendor-dsers 动态加载

`PrivateDsersProvider.__init__()` 将 `vendor-dsers/` 加入 `sys.path`，然后通过 `importlib` 动态加载各业务模块的 `register()` 函数获取 handler。

#### 6.3 Shipping Profile 自动发现

推送到 Shopify 店铺时，自动处理 Delivery Profile：
1. 调用 `GET /import-list/shopify/shipping-profile/get` 获取所有 Shopify delivery profiles
2. 选取 `isChecked=true` 的 profile（即 DSers 网页端默认选中的）
3. 如果指定了 `push_options.shipping_profile_name`，则按名称匹配
4. 回退到 `push_options.store_shipping_profile` 手动覆盖
5. 非 Shopify 店铺（Wix、WooCommerce）完全跳过此步骤

`get_rule_capabilities` 也会为每个 Shopify 店铺返回 `shipping_profiles`（名称、是否默认、覆盖国家数、运费），供 Agent 展示给用户选择。

---

### 7. Push Options

| 选项 | 类型 | 说明 |
|------|------|------|
| `publish_to_online_store` | `bool` | 是否发布到在线店铺 |
| `only_push_specifications` | `bool` | 仅推送规格数据 |
| `image_strategy` | `str` | `selected_only` / `all_available` |
| `pricing_rule_behavior` | `str` | `keep_manual` / `apply_store_pricing_rule` |
| `auto_inventory_update` | `bool` | 自动同步库存 |
| `auto_price_update` | `bool` | 自动同步价格 |
| `sales_channels` | `list` | 销售渠道列表 |
| `shipping_profile_name` | `str` | Shopify 运费模板名称——不指定则自动使用默认模板 |
| `store_shipping_profile` | `list` | 手动覆盖：原始 delivery profile 绑定（极少需要） |

---

### 8. 本地开发

#### 8.1 环境搭建

```bash
git clone https://github.com/lofder/dsers-mcp-product.git && cd dsers-mcp-product
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# 编辑 .env 填入你的凭据
```

#### 8.2 冒烟测试

```bash
python smoke_mock.py                      # 离线，无需凭据
python smoke_dsers.py                     # 需要 .env 中的凭据
SAMPLE_IMPORT_URL="https://..." python smoke_dsers.py   # 带实际导入
```

#### 8.3 作为 MCP 服务器运行

```bash
python server.py
```

在 Cursor 的 MCP 配置中添加：

```json
{
  "mcpServers": {
    "dropship-import": {
      "command": "python",
      "args": ["server.py"],
      "cwd": "/path/to/dsers-mcp-product"
    }
  }
}
```

---

### 9. 安全注意事项

- **`.env` 文件绝不提交到 Git** — 已在 `.gitignore` 中排除
- **Session 缓存文件**（`.session-cache/`、`.session.json`）已在 `.gitignore` 中排除
- 凭据通过环境变量传入，代码中无硬编码
- `vendor-dsers/` 中的 API 调用全部通过 `DSersClient` 统一管理 session

---

### 10. 已知限制 & 迭代计划

| 状态 | 说明 |
|------|------|
| ✅ 已完成 | 生产环境 API（`DSERS_ENV=production` 默认） |
| ✅ 已完成 | 批量导入和批量推送 |
| ✅ 已完成 | 多店铺推送（1 个商品 x N 个店铺） |
| ✅ 已完成 | Shopify 运费模板自动发现（专用 API） |
| ✅ 已完成 | 多平台目标：Shopify、Wix、WooCommerce |
| ✅ 已完成 | 多来源：AliExpress、Alibaba、1688 |
| 🔜 后续 | 支持更多平台 Provider（非 DSers） |
| 🔜 后续 | 规则引擎增加 tag 编辑支持 |
| 🔜 后续 | AliExpress Bundle URL 支持 |
