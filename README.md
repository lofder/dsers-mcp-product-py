# DSers MCP Product (Python) v1.5.7

> **The TypeScript version is the primary maintained version.**
> For the latest features, Smithery integration, and active development, see **[dsers-mcp-product (TypeScript)](https://github.com/lofder/dsers-mcp-product)**.
> This Python port remains functional and receives critical fixes.

> **TypeScript 版本是主要维护版本。**
> 最新功能、Smithery 集成和活跃开发请参见 **[dsers-mcp-product (TypeScript)](https://github.com/lofder/dsers-mcp-product)**。
> 此 Python 版本仍可正常使用，将继续接收关键修复。

An open-source MCP server to automate DSers product import, rules editing, SKU remapping, and push to Shopify / Wix / WooCommerce using AI.

> [English](#english) | [中文](#中文)

---

<a id="english"></a>

## English

**DSers MCP Product** is an open-source [MCP (Model Context Protocol)](https://modelcontextprotocol.io/) server that lets AI Agents automate the entire DSers import workflow -- from AliExpress / Alibaba / 1688 product URL to Shopify / Wix / WooCommerce store listing. Bulk import, batch edit variants, clean titles, apply pricing rules, remap suppliers, and push to multiple stores -- all with a single sentence to your AI agent.

### Features

- **Full rules engine** -- pricing (multiplier, fixed_markup, fixed_price), content (title, description, tags), images (keep/drop/reorder), variant_overrides, option_edits
- **Push safety guards** -- automatic pre-push validation blocks sell-below-cost and zero-stock; warns on low margin, low stock, very low price
- **SKU remap** -- replace suppliers on existing store products with variant-level SKU matching (strict mode with URL, discover mode with reverse-image search)
- **Batch operations** -- import multiple URLs, push to multiple stores in one call
- **Structured logging** -- JSON-formatted request/response logging with configurable levels
- **Security hardening** -- HTML injection blocking in description fields, input sanitization, extreme pricing warnings
- **Provider extension** -- swap the DSers adapter for any other platform

### Documentation

| Document | Content |
|----------|---------|
| [USAGE.md](USAGE.md) | Installation, client setup, usage examples, scenario prompts, FAQ |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Three-layer architecture, module map, provider extension, security |
| [SKILL.md](SKILL.md) | AI Agent tool reference, v1.5.7 behaviors, push safety, error handling |
| [SKILL-CN.md](SKILL-CN.md) | AI Agent tool reference (Chinese) |

### Core Tools

| # | Tool | Description |
|---|------|-------------|
| 1 | `get_rule_capabilities` | Query supported stores (with Shopify shipping profiles), rule families, and push options |
| 2 | `validate_rules` | Validate and normalize a rules object; returns effective snapshot and errors |
| 3 | `prepare_import_candidate` | Import from supplier URL(s) -- single or batch -- apply rules, return preview with job_id |
| 4 | `get_import_preview` | View prepared draft preview (compact or full variant detail) |
| 5 | `set_product_visibility` | Adjust visibility (backend_only / sell_immediately) |
| 6 | `confirm_push_to_store` | Push to store(s) -- single, batch, or multi-store; includes pre-push safety validation |
| 7 | `get_job_status` | Query final push status (preview_ready / push_requested / completed / failed / persist_failed) |
| 8 | `dsers_product_update_rules` | Update pricing, content, images, variant, or option rules on an already-imported product |
| 9 | `dsers_find_product` | Search the DSers product pool by keyword or image URL (visual search) |
| 10 | `dsers_import_list` | Browse the DSers import list with enriched variant data |
| 11 | `dsers_my_products` | Browse products already pushed to a store |
| 12 | `dsers_product_delete` | Permanently delete a product from the import list (requires confirmation) |
| 13 | `dsers_sku_remap` | Replace supplier on a store product with SKU-level variant matching (strict or discover mode) |

### Supported Platforms

| Type | Platforms |
|------|-----------|
| **Source (import from)** | AliExpress, Alibaba, 1688 |
| **Target (push to)** | Shopify, Wix, WooCommerce (via DSers) |

### Quick Start

```bash
# 1. Clone and install
git clone https://github.com/lofder/dsers-mcp-product-py.git && cd dsers-mcp-product-py
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. Configure credentials
cp .env.example .env
# Edit .env, fill in DSERS_EMAIL and DSERS_PASSWORD

# 3. Smoke test
python smoke_mock.py     # Mock mode (no credentials needed)
python smoke_dsers.py    # DSers Provider (credentials required)

# 4. Start MCP server
python server.py
```

### Project Structure

```
dsers-mcp-product-py/
├── server.py                     # MCP server entry point
├── dsers_mcp_product/            # Protocol layer (tools, rules engine, job management)
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
│   └── sku_remap_service.py      # Supplier remap orchestration (strict + discover)
├── dsers_provider/               # DSers adapter layer
│   ├── __init__.py
│   └── provider.py               # PrivateDsersProvider -- ImportProvider impl
├── vendor-dsers/                 # DSers API library (auth / product / order / logistics)
├── tests/                        # Test suite
├── ARCHITECTURE.md               # Technical architecture
├── USAGE.md                      # User guide
├── SKILL.md                      # AI Agent skill guide (English)
├── SKILL-CN.md                   # AI Agent skill guide (Chinese)
├── .env.example                  # Environment variable template
├── pyproject.toml                # Project metadata
├── requirements.txt              # Python dependencies
└── LICENSE                       # MIT
```

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DSERS_EMAIL` | Yes | DSers account email |
| `DSERS_PASSWORD` | Yes | DSers account password |
| `DSERS_ENV` | No | `production` (default) or `test` |
| `IMPORT_PROVIDER_MODULE` | No | Provider module path (default: `dsers_provider.provider`) |
| `IMPORT_MCP_STATE_DIR` | No | Job state directory (default: `.state`) |

See `.env.example` for the full list.

### Push Options

| Option | Type | Description |
|--------|------|-------------|
| `publish_to_online_store` | bool | Publish product to online storefront |
| `image_strategy` | string | `selected_only` / `all_available` |
| `pricing_rule_behavior` | string | `keep_manual` / `apply_store_pricing_rule` |
| `auto_inventory_update` | bool | Auto-sync inventory |
| `auto_price_update` | bool | Auto-sync price |
| `sales_channels` | list | Sales channel identifiers |
| `shipping_profile_name` | string | Shopify delivery profile name -- if omitted, the default profile is used automatically |
| `store_shipping_profile` | list | Manual override: raw delivery profile bindings (rarely needed) |

### Provider Extension

Implement the three methods of the `ImportProvider` abstract base class, expose a `build_provider()` factory function, and set `IMPORT_PROVIDER_MODULE` to load your custom provider.

### Security

- `.env` and session caches are excluded via `.gitignore`
- No hardcoded credentials in source code
- All authentication managed through environment variables
- HTML injection blocking in description fields (v1.5.7)
- Input sanitization on all user-provided strings
- Extreme pricing warnings (multiplier >100x, fixed_markup >$500, fixed_price >$10,000)

### License

MIT

---

<a id="中文"></a>

## 中文

> **TypeScript 版本是主要维护版本。** 最新功能和活跃开发请参见 [dsers-mcp-product (TypeScript)](https://github.com/lofder/dsers-mcp-product)。此 Python 版本仍可正常使用，将继续接收关键修复。

**DSers MCP Product** 是一个开源的 [MCP (Model Context Protocol)](https://modelcontextprotocol.io/) 服务器，让 AI Agent 自动化 DSers 商品导入全流程 -- 从速卖通 / Alibaba / 1688 商品链接到 Shopify / Wix / WooCommerce 店铺上架。批量导入、批量编辑变体、清洗标题、应用定价规则、替换供应商、多店推送 -- 只需一句话。

### 功能特性

- **完整规则引擎** -- 定价（倍率、固定加价、固定价格）、内容（标题、描述、标签）、图片（保留/删除/重排序）、变体覆盖、选项编辑
- **推送安全防护** -- 自动预推送校验，阻止低于成本售价和零库存商品；对低利润、低库存、超低价格发出警告
- **SKU 重映射** -- 在已上架商品上替换供应商，支持变体级别 SKU 匹配（精确模式使用 URL，发现模式使用反向图片搜索）
- **批量操作** -- 一次调用导入多个 URL，一次推送到多个店铺
- **结构化日志** -- JSON 格式的请求/响应日志，可配置级别
- **安全加固** -- 描述字段 HTML 注入拦截、输入清洗、极端定价警告
- **Provider 扩展** -- 可将 DSers 适配层替换为其他平台

### 文档导航

| 文档 | 内容 |
|------|------|
| [USAGE.md](USAGE.md) | 安装配置、接入客户端、使用方式、场景提示词、常见问题 |
| [ARCHITECTURE.md](ARCHITECTURE.md) | 三层架构、模块图、Provider 扩展、安全机制 |
| [SKILL.md](SKILL.md) | AI Agent 工具参考 (English) |
| [SKILL-CN.md](SKILL-CN.md) | AI Agent 工具参考（中文） |

### 核心工具

| # | 工具 | 说明 |
|---|------|------|
| 1 | `get_rule_capabilities` | 查询支持的店铺（含 Shopify 运费模板）、规则族、推送选项 |
| 2 | `validate_rules` | 校验并归一化规则对象；返回有效快照和错误 |
| 3 | `prepare_import_candidate` | 从供应商 URL 导入 -- 单条或批量 -- 应用规则，返回带 job_id 的预览 |
| 4 | `get_import_preview` | 查看已准备的草稿预览（简洁或完整变体详情） |
| 5 | `set_product_visibility` | 调整可见性 (backend_only / sell_immediately) |
| 6 | `confirm_push_to_store` | 推送到店铺 -- 单条、批量或多店铺；含预推送安全校验 |
| 7 | `get_job_status` | 查询推送最终状态 (preview_ready / push_requested / completed / failed / persist_failed) |
| 8 | `dsers_product_update_rules` | 在已导入的商品上更新定价、内容、图片、变体或选项规则 |
| 9 | `dsers_find_product` | 通过关键词或图片 URL（视觉搜索）搜索 DSers 商品库 |
| 10 | `dsers_import_list` | 浏览 DSers 导入列表，含丰富的变体数据 |
| 11 | `dsers_my_products` | 浏览已推送到店铺的商品 |
| 12 | `dsers_product_delete` | 从导入列表永久删除商品（需确认） |
| 13 | `dsers_sku_remap` | 替换已上架商品的供应商，支持变体级别 SKU 匹配（精确模式或发现模式） |

### 支持平台

| 类型 | 平台 |
|------|------|
| **来源（导入）** | AliExpress（速卖通）、Alibaba、1688 |
| **目标（推送）** | Shopify、Wix、WooCommerce（通过 DSers） |

### 快速开始

```bash
# 1. 克隆并安装
git clone https://github.com/lofder/dsers-mcp-product-py.git && cd dsers-mcp-product-py
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. 配置凭据
cp .env.example .env
# 编辑 .env，填入 DSERS_EMAIL 和 DSERS_PASSWORD

# 3. 冒烟测试
python smoke_mock.py     # Mock 模式（无需凭据）
python smoke_dsers.py    # DSers Provider（需要凭据）

# 4. 启动 MCP 服务器
python server.py
```

### 项目结构

```
dsers-mcp-product-py/
├── server.py                     # MCP 服务入口
├── dsers_mcp_product/            # 协议层（工具定义、规则引擎、作业管理）
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
│   └── sku_remap_service.py      # 供应商重映射编排（精确 + 发现）
├── dsers_provider/               # DSers 适配层
│   ├── __init__.py
│   └── provider.py               # PrivateDsersProvider -- ImportProvider 实现
├── vendor-dsers/                 # DSers API 封装库（认证/商品/订单/物流）
├── tests/                        # 测试套件
├── ARCHITECTURE.md               # 技术架构文档
├── USAGE.md                      # 使用指南
├── SKILL.md                      # AI Agent 使用指南 (English)
├── SKILL-CN.md                   # AI Agent 使用指南（中文）
├── .env.example                  # 环境变量模板
├── pyproject.toml                # 项目元数据
├── requirements.txt              # Python 依赖
└── LICENSE                       # MIT
```

### 环境变量

| 变量 | 必需 | 说明 |
|------|------|------|
| `DSERS_EMAIL` | 是 | DSers 账户邮箱 |
| `DSERS_PASSWORD` | 是 | DSers 账户密码 |
| `DSERS_ENV` | 否 | `production`（默认）或 `test` |
| `IMPORT_PROVIDER_MODULE` | 否 | Provider 模块路径（默认 `dsers_provider.provider`） |
| `IMPORT_MCP_STATE_DIR` | 否 | 作业状态目录（默认 `.state`） |

完整变量列表见 `.env.example`。

### Push Options

| 选项 | 类型 | 说明 |
|------|------|------|
| `publish_to_online_store` | bool | 商品是否上架到店铺前端 |
| `image_strategy` | string | `selected_only` / `all_available` |
| `pricing_rule_behavior` | string | `keep_manual` / `apply_store_pricing_rule` |
| `auto_inventory_update` | bool | 自动同步库存 |
| `auto_price_update` | bool | 自动同步价格 |
| `sales_channels` | list | 销售渠道列表 |
| `shipping_profile_name` | string | Shopify 运费模板名称 -- 不指定则自动使用默认模板 |
| `store_shipping_profile` | list | 手动覆盖：原始 delivery profile 绑定（极少需要） |

### Provider 扩展

实现 `ImportProvider` 抽象基类的三个方法，暴露 `build_provider()` 工厂函数，设置 `IMPORT_PROVIDER_MODULE` 即可加载自定义 Provider。

### 安全

- `.env` 和 session 缓存已在 `.gitignore` 中排除
- 代码中无硬编码凭据
- 所有认证通过环境变量管理
- 描述字段 HTML 注入拦截 (v1.5.7)
- 所有用户输入字符串清洗
- 极端定价警告（倍率 >100x、固定加价 >$500、固定价格 >$10,000）

### License

MIT
