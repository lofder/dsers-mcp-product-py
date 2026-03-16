# Dropship Import MCP

基于 [Model Context Protocol](https://modelcontextprotocol.io/) 的一件代发商品导入服务。AI Agent 通过 7 个高层工具，完成从供应商 URL 到店铺上架的全过程。

## 文档导航

| 文档 | 内容 |
|------|------|
| [USAGE.md — 使用指南](USAGE.md) | 安装配置、接入客户端、使用方式、常见问题 |
| [ARCHITECTURE.md — 技术架构](ARCHITECTURE.md) | 三层架构、工具流程、Provider 扩展、DSers 适配层详解 |
| [SKILL.md — Agent Skill](SKILL.md) | AI Agent 工具参考、参数格式、Push Options |

## 核心工具

| 工具 | 说明 |
|------|------|
| `get_rule_capabilities` | 查询支持的规则族、店铺、推送选项 |
| `validate_rules` | 校验并归一化规则对象 |
| `prepare_import_candidate` | 解析 URL → 导入 → 应用规则 → 返回预览 |
| `get_import_preview` | 查看已准备的草稿预览 |
| `set_product_visibility` | 调整可见性 (backend_only / sell_immediately) |
| `confirm_push_to_store` | 确认推送到目标店铺 |
| `get_job_status` | 查询推送最终状态 |

## 快速开始

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

## 项目结构

```
dropship-import-mcp/
├── server.py                 # MCP 服务入口
├── dropship_import_mcp/      # 协议层（工具定义、规则引擎、作业管理）
├── dsers_provider/           # DSers 适配层（ImportProvider 实现）
├── vendor-dsers/             # DSers API 封装库（认证/商品/订单/物流）
├── ARCHITECTURE.md           # 详细技术架构文档
├── SKILL.md                  # AI Agent 使用指南
└── .env.example              # 环境变量模板
```

详细说明见上方「文档导航」。

## 环境变量

| 变量 | 必需 | 说明 |
|------|------|------|
| `DSERS_EMAIL` | 是 | DSers 账户邮箱 |
| `DSERS_PASSWORD` | 是 | DSers 账户密码 |
| `DSERS_ENV` | 否 | `test` 或 `production`（默认 `test`） |
| `IMPORT_PROVIDER_MODULE` | 否 | Provider 模块路径（默认 `dsers_provider.provider`） |
| `IMPORT_MCP_STATE_DIR` | 否 | 作业状态目录（默认 `.state`） |

完整变量列表见 `.env.example`。

## Push Options

| 选项 | 类型 | 说明 |
|------|------|------|
| `publish_to_online_store` | bool | 商品是否上架到店铺前端 |
| `image_strategy` | string | `selected_only` / `all_available` |
| `pricing_rule_behavior` | string | `keep_manual` / `apply_store_pricing_rule` |
| `auto_inventory_update` | bool | 自动同步库存 |
| `auto_price_update` | bool | 自动同步价格 |
| `sales_channels` | list | 销售渠道列表 |
| `store_shipping_profile` | list | 平台 Delivery Profile 绑定（fallback） |

## Provider 扩展

实现 `ImportProvider` 抽象基类的三个方法，暴露 `build_provider()` 工厂函数，设置 `IMPORT_PROVIDER_MODULE` 即可加载自定义 Provider。

## 安全

- `.env` 和 session 缓存已在 `.gitignore` 中排除
- 代码中无硬编码凭据
- 所有认证通过环境变量管理

## License

MIT
