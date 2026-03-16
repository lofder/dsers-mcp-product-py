# 使用指南 — Dropship Import MCP

本文档面向**最终使用者**，介绍如何安装、配置并通过 AI Agent 使用本 MCP 完成商品导入与推送。

---

## 1. 前置条件

| 项目 | 要求 |
|------|------|
| Python | 3.10 或更高版本 |
| DSers 账号 | 已注册，且绑定了至少一个 Shopify 店铺 |
| MCP 客户端 | Cursor IDE、Claude Desktop 或其他支持 MCP 的 AI 客户端 |

---

## 2. 安装

```bash
# 克隆仓库
git clone https://github.com/lofder/dropship-import-mcp.git
cd dropship-import-mcp

# 创建虚拟环境并安装依赖
python3 -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

---

## 3. 配置

### 3.1 创建 `.env` 文件

```bash
cp .env.example .env
```

### 3.2 填写必需变量

用编辑器打开 `.env`，填入以下内容：

```ini
DSERS_EMAIL=你的DSers邮箱
DSERS_PASSWORD=你的DSers密码
DSERS_ENV=test
```

| 变量 | 说明 |
|------|------|
| `DSERS_EMAIL` | DSers 登录邮箱 |
| `DSERS_PASSWORD` | DSers 登录密码 |
| `DSERS_ENV` | `test` = 测试环境，`production` = 生产环境 |

> **安全提示**：`.env` 文件已被 `.gitignore` 排除，不会被提交到 Git。

### 3.3 验证安装

```bash
# Mock 模式验证（无需凭据）
python smoke_mock.py

# DSers Provider 验证（需要凭据）
python smoke_dsers.py
```

如果 `smoke_dsers.py` 输出了 `capabilities` 且无报错，说明凭据配置正确。

---

## 4. 接入 AI 客户端

### 4.1 Cursor IDE

在 Cursor 设置中找到 MCP 配置（Settings → MCP），添加：

```json
{
  "mcpServers": {
    "dropship-import": {
      "command": "/绝对路径/dropship-import-mcp/.venv/bin/python",
      "args": ["server.py"],
      "cwd": "/绝对路径/dropship-import-mcp"
    }
  }
}
```

> 将 `/绝对路径/` 替换为你的实际项目路径。使用虚拟环境的 Python 路径可以确保依赖正确加载。

### 4.2 Claude Desktop

编辑 `~/Library/Application Support/Claude/claude_desktop_config.json`（macOS）：

```json
{
  "mcpServers": {
    "dropship-import": {
      "command": "/绝对路径/dropship-import-mcp/.venv/bin/python",
      "args": ["server.py"],
      "cwd": "/绝对路径/dropship-import-mcp"
    }
  }
}
```

配置完成后重启客户端，即可在对话中使用导入工具。

---

## 5. 使用方式

接入 MCP 后，你可以直接用自然语言指示 AI Agent 完成以下操作。

### 5.1 导入并推送一个商品

> **你说**：帮我把这个商品导入到我的 Shopify 店铺
> https://www.aliexpress.com/item/1005006xxxxx.html
> 价格加价 50%，标题前面加上 "HOT - "

Agent 会自动执行以下流程：

1. 调用 `get_rule_capabilities` 获取店铺列表
2. 调用 `prepare_import_candidate` 导入商品并应用规则
3. 展示预览，询问你确认
4. 调用 `confirm_push_to_store` 推送到店铺
5. 调用 `get_job_status` 确认推送结果

### 5.2 只预览不推送

> **你说**：帮我看看这个商品的详情，先不要推送
> https://www.aliexpress.com/item/1005006xxxxx.html

Agent 只会执行到预览步骤，等待你确认后才推送。

### 5.3 批量操作

> **你说**：把以下 3 个链接的商品都导入到我的店铺，统一加价 80%
> - https://...
> - https://...
> - https://...

Agent 会逐个导入并推送（当前版本为串行执行）。

### 5.4 指定推送选项

> **你说**：推送这个商品，但是先不要上架到前端，只在后台显示，同时开启自动同步库存

Agent 会将对应的 push_options 设置为：
- `publish_to_online_store: false`
- `auto_inventory_update: true`
- `visibility_mode: backend_only`

---

## 6. 推送选项详解

在对话中提到以下关键词，Agent 会自动匹配对应的推送选项：

| 你的描述 | 对应选项 | 值 |
|----------|----------|------|
| "上架" / "发布到前端" | `publish_to_online_store` | `true` |
| "只在后台" / "不上架" | `publish_to_online_store` | `false` |
| "推送所有图片" | `image_strategy` | `all_available` |
| "用店铺定价规则" | `pricing_rule_behavior` | `apply_store_pricing_rule` |
| "自动同步库存" | `auto_inventory_update` | `true` |
| "自动同步价格" | `auto_price_update` | `true` |

---

## 7. 规则说明

你可以在导入时通过自然语言指定规则，Agent 会转换为结构化规则对象：

### 定价规则

| 描述 | 示例 |
|------|------|
| 加价百分比 | "加价 50%" → `markup_percent: 50` |
| 固定加价 | "每个加 5 美元" → `fixed_markup: 5` |
| 倍数 | "价格乘以 2.5" → `multiplier: 2.5` |

### 内容规则

| 描述 | 示例 |
|------|------|
| 标题前缀 | "标题前加 HOT" → `title_prefix: "HOT - "` |
| 标题后缀 | "标题后加 Free Shipping" → `title_suffix: " | Free Shipping"` |
| 替换标题 | "把标题改成 xxx" → `title_override: "xxx"` |

### 图片规则

| 描述 | 示例 |
|------|------|
| 限制图片数量 | "只保留前 5 张图" → `keep_first_n: 5` |
| 跳过首图 | "去掉第一张图" → `drop_indexes: [0]` |

---

## 8. 常见问题

### Q: 推送失败提示 "shipping profile not found"

**原因**：目标 Shopify 店铺需要 Delivery Profile 绑定。

**解决**：在推送时告诉 Agent 提供 store_shipping_profile，或者在 DSers 网页端找到对应的 Delivery Profile 信息后提供给 Agent。格式如下：

```json
{
  "store_shipping_profile": [
    {
      "storeId": "你的店铺ID",
      "locationId": "gid://shopify/DeliveryLocationGroup/xxx",
      "profileId": "gid://shopify/DeliveryProfile/xxx"
    }
  ]
}
```

系统会自动尝试通过 API 获取这些信息。只有 API 返回空时才需要手动提供。

### Q: 提示凭据无效 / 登录失败

1. 检查 `.env` 中的 `DSERS_EMAIL` 和 `DSERS_PASSWORD` 是否正确
2. 确认 `DSERS_ENV` 值与你的账号环境匹配（test / production）
3. 删除 `.session-cache/` 目录后重试（清除过期的 session 缓存）

### Q: 找不到目标店铺

1. 确认你的 DSers 账户已绑定 Shopify 店铺
2. 在对话中明确指定店铺名称或 ID
3. 调用 `get_rule_capabilities` 查看所有可用店铺

### Q: 如何切换到生产环境

将 `.env` 中的 `DSERS_ENV` 改为 `production`：

```ini
DSERS_ENV=production
```

然后重启 MCP 服务器。

### Q: 是否支持 AliExpress 以外的供应商

当前支持：
- **AliExpress** — 完整支持
- **Alibaba (1688)** — 基本支持
- **Accio** — 基本支持

### Q: 如何不使用 DSers，换成其他平台

设置环境变量切换 Provider：

```ini
IMPORT_PROVIDER_MODULE=dropship_import_mcp.mock_provider
```

`mock_provider` 是内置的离线模拟 Provider，用于开发和演示。你也可以实现自己的 Provider（参见 [ARCHITECTURE.md](ARCHITECTURE.md) 第 5 节）。

---

## 9. 故障排查清单

遇到问题时按以下顺序检查：

1. **`.env` 文件是否存在** — 必须从 `.env.example` 复制
2. **Python 版本** — 运行 `python3 --version` 确认 ≥ 3.10
3. **依赖是否安装** — 运行 `pip install -r requirements.txt`
4. **虚拟环境是否激活** — 确认终端前缀显示 `(.venv)`
5. **MCP 客户端路径** — 确认使用了虚拟环境内的 Python 路径
6. **冒烟测试** — 运行 `python smoke_dsers.py` 检查输出
7. **查看 warnings** — 所有 MCP 响应都包含 `warnings` 数组，注意其中的提示信息
