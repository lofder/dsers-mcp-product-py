# Dropship Import MCP

> [English](#english) | [中文](#中文)

---

<a id="english"></a>

## English

An MCP server for dropshipping product import, built on [Model Context Protocol](https://modelcontextprotocol.io/). AI Agents use 7 high-level tools to complete the full workflow from supplier URL to store listing.

### Documentation

| Document | Content |
|----------|---------|
| [USAGE.md — User Guide](USAGE.md) | Installation, client setup, usage examples, FAQ |
| [ARCHITECTURE.md — Technical Architecture](ARCHITECTURE.md) | Three-layer architecture, tool flow, provider extension |
| [SKILL.md — Agent Skill Guide](SKILL.md) | Tool reference, parameter formats, push options |

### Core Tools

| Tool | Description |
|------|-------------|
| `get_rule_capabilities` | Query supported rule families, stores, and push options |
| `validate_rules` | Validate and normalize a rule object |
| `prepare_import_candidate` | Resolve URL → import → apply rules → return preview |
| `get_import_preview` | View prepared draft preview |
| `set_product_visibility` | Adjust visibility (backend_only / sell_immediately) |
| `confirm_push_to_store` | Confirm push to target store |
| `get_job_status` | Query final push status |

### Quick Start

```bash
# 1. Clone and install
git clone <repo-url> && cd dropship-import-mcp
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
dropship-import-mcp/
├── server.py                 # MCP server entry point
├── dropship_import_mcp/      # Protocol layer (tools, rules engine, job management)
├── dsers_provider/           # DSers adapter (ImportProvider implementation)
├── vendor-dsers/             # DSers API library (auth / product / order / logistics)
├── ARCHITECTURE.md           # Technical architecture
├── USAGE.md                  # User guide
├── SKILL.md                  # AI Agent skill guide
└── .env.example              # Environment variable template
```

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DSERS_EMAIL` | Yes | DSers account email |
| `DSERS_PASSWORD` | Yes | DSers account password |
| `DSERS_ENV` | No | `test` or `production` (default: `test`) |
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
| `store_shipping_profile` | list | Platform delivery profile bindings (fallback) |

### Provider Extension

Implement the three methods of the `ImportProvider` abstract base class, expose a `build_provider()` factory function, and set `IMPORT_PROVIDER_MODULE` to load your custom provider.

### Security

- `.env` and session caches are excluded via `.gitignore`
- No hardcoded credentials in source code
- All authentication managed through environment variables

### License

MIT

---

<a id="中文"></a>

## 中文

基于 [Model Context Protocol](https://modelcontextprotocol.io/) 的一件代发商品导入服务。AI Agent 通过 7 个高层工具，完成从供应商 URL 到店铺上架的全过程。

### 文档导航

| 文档 | 内容 |
|------|------|
| [USAGE.md — 使用指南](USAGE.md) | 安装配置、接入客户端、使用方式、常见问题 |
| [ARCHITECTURE.md — 技术架构](ARCHITECTURE.md) | 三层架构、工具流程、Provider 扩展、DSers 适配层详解 |
| [SKILL.md — Agent Skill](SKILL.md) | AI Agent 工具参考、参数格式、Push Options |

### 核心工具

| 工具 | 说明 |
|------|------|
| `get_rule_capabilities` | 查询支持的规则族、店铺、推送选项 |
| `validate_rules` | 校验并归一化规则对象 |
| `prepare_import_candidate` | 解析 URL → 导入 → 应用规则 → 返回预览 |
| `get_import_preview` | 查看已准备的草稿预览 |
| `set_product_visibility` | 调整可见性 (backend_only / sell_immediately) |
| `confirm_push_to_store` | 确认推送到目标店铺 |
| `get_job_status` | 查询推送最终状态 |

### 快速开始

```bash
# 1. 克隆并安装
git clone <repo-url> && cd dropship-import-mcp
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
dropship-import-mcp/
├── server.py                 # MCP 服务入口
├── dropship_import_mcp/      # 协议层（工具定义、规则引擎、作业管理）
├── dsers_provider/           # DSers 适配层（ImportProvider 实现）
├── vendor-dsers/             # DSers API 封装库（认证/商品/订单/物流）
├── ARCHITECTURE.md           # 详细技术架构文档
├── USAGE.md                  # 使用指南
├── SKILL.md                  # AI Agent 使用指南
└── .env.example              # 环境变量模板
```

### 环境变量

| 变量 | 必需 | 说明 |
|------|------|------|
| `DSERS_EMAIL` | 是 | DSers 账户邮箱 |
| `DSERS_PASSWORD` | 是 | DSers 账户密码 |
| `DSERS_ENV` | 否 | `test` 或 `production`（默认 `test`） |
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
| `store_shipping_profile` | list | 平台 Delivery Profile 绑定（fallback） |

### Provider 扩展

实现 `ImportProvider` 抽象基类的三个方法，暴露 `build_provider()` 工厂函数，设置 `IMPORT_PROVIDER_MODULE` 即可加载自定义 Provider。

### 安全

- `.env` 和 session 缓存已在 `.gitignore` 中排除
- 代码中无硬编码凭据
- 所有认证通过环境变量管理

### License

MIT
