# User Guide / 使用指南 — DSers MCP Product (Python): How to Bulk Edit Variants with MCP

> **Note:** The TypeScript version is now the primary maintained version. See [dsers-mcp-product](https://github.com/lofder/dsers-mcp-product).

> [English](#english) | [中文](#中文)

---

<a id="english"></a>

## English

This guide is for **end users** — how to install, configure, and use this MCP with an AI Agent to import and push products.

---

### 1. Prerequisites

| Item | Requirement |
|------|-------------|
| Python | 3.10 or higher |
| DSers account | Registered, with at least one store linked (Shopify, Wix, or WooCommerce) |
| MCP client | Cursor IDE, Claude Desktop, or any MCP-compatible AI client |

---

### 2. Installation

```bash
# Clone the repository
git clone https://github.com/lofder/dsers-mcp-product.git
cd dsers-mcp-product

# Create virtual environment and install dependencies
python3 -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

---

### 3. Configuration

#### 3.1 Create `.env` File

```bash
cp .env.example .env
```

#### 3.2 Fill in Required Variables

Open `.env` in a text editor and fill in:

```ini
DSERS_EMAIL=your-dsers-email
DSERS_PASSWORD=your-dsers-password
DSERS_ENV=production
```

| Variable | Description |
|----------|-------------|
| `DSERS_EMAIL` | DSers login email |
| `DSERS_PASSWORD` | DSers login password |
| `DSERS_ENV` | `production` (default) or `test` |

> **Security note**: `.env` is excluded by `.gitignore` and will never be committed to Git.

#### 3.3 Verify Installation

```bash
# Mock mode (no credentials needed)
python smoke_mock.py

# DSers Provider (credentials required)
python smoke_dsers.py
```

If `smoke_dsers.py` outputs `capabilities` without errors, your credentials are configured correctly.

---

### 4. Connect to AI Client

#### 4.1 Cursor IDE

In Cursor settings, find MCP configuration (Settings → MCP) and add:

```json
{
  "mcpServers": {
    "dsers-mcp-product": {
      "command": "/absolute/path/to/dsers-mcp-product/.venv/bin/python",
      "args": ["server.py"],
      "cwd": "/absolute/path/to/dsers-mcp-product"
    }
  }
}
```

> Replace `/absolute/path/to/` with your actual project path. Using the venv Python path ensures dependencies load correctly.

#### 4.2 Claude Desktop

Edit `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS):

```json
{
  "mcpServers": {
    "dsers-mcp-product": {
      "command": "/absolute/path/to/dsers-mcp-product/.venv/bin/python",
      "args": ["server.py"],
      "cwd": "/absolute/path/to/dsers-mcp-product"
    }
  }
}
```

Restart the client after configuration to start using the import tools.

---

### 5. Usage

After connecting the MCP, you can use natural language to instruct the AI Agent.

#### 5.1 Import and Push a Product

> **You say**: Import this product to my Shopify store  
> https://www.aliexpress.com/item/1005006xxxxx.html  
> Mark up the price by 50%, add "HOT - " before the title

The Agent will automatically:

1. Call `get_rule_capabilities` to get the store list
2. Call `prepare_import_candidate` to import and apply rules
3. Show preview and ask for confirmation
4. Call `confirm_push_to_store` to push to the store
5. Call `get_job_status` to confirm the result

#### 5.2 Preview Only

> **You say**: Show me the details of this product, don't push yet  
> https://www.aliexpress.com/item/1005006xxxxx.html

The Agent will only proceed to the preview step and wait for your confirmation.

#### 5.3 Batch Import and Push

> **You say**: Import all 5 links below to my store, mark up 80%, all to backend  
> - https://aliexpress.com/item/111.html  
> - https://aliexpress.com/item/222.html  
> - https://aliexpress.com/item/333.html  
> - https://1688.com/offer/444.html  
> - https://aliexpress.com/item/555.html

The Agent will batch-import all URLs in a single call, then batch-push all valid results. Invalid URLs are reported per-item without blocking others. Mixed sources (AliExpress + 1688) are supported.

#### 5.4 Multi-Store Push

> **You say**: Push this product to both my Shopify store and my Wix store

The Agent will push the same product to multiple stores in one call using `target_stores`.

#### 5.5 Choose Shipping Profile (Shopify)

> **You say**: Push this product using the "General profile" shipping profile

For Shopify stores, the system auto-discovers available delivery profiles. By default it uses the one marked as default in DSers. You can specify a different one by name.

#### 5.6 Specify Push Options

> **You say**: Push this product but don't list it on the storefront, keep it as a draft, and enable auto inventory sync

The Agent will set the corresponding push_options:
- `publish_to_online_store: false`
- `auto_inventory_update: true`
- `visibility_mode: backend_only`

---

### 6. Push Options Reference

Use these keywords in conversation and the Agent will map them to push options:

| What You Say | Option | Value |
|--------------|--------|-------|
| "publish" / "list it" | `publish_to_online_store` | `true` |
| "draft only" / "don't publish" | `publish_to_online_store` | `false` |
| "push all images" | `image_strategy` | `all_available` |
| "use store pricing rule" | `pricing_rule_behavior` | `apply_store_pricing_rule` |
| "auto sync inventory" | `auto_inventory_update` | `true` |
| "auto sync price" | `auto_price_update` | `true` |
| "use General profile" | `shipping_profile_name` | `"General profile"` |

---

### 7. How to Bulk Edit Variants with MCP

One of the most time-consuming tasks in dropshipping is editing product variants — adjusting prices, cleaning up AliExpress titles, removing unwanted options. With this MCP server, you can bulk edit variants using natural language:

> **You say**: Import these 5 products, multiply all variant prices by 3, remove any Chinese text from titles, keep only the first 5 images.

The Agent applies your rules across all variants in all products in a single batch call. No manual clicking through each variant.

| Task | How to Say It |
|------|---------------|
| Bulk price adjustment | "multiply all prices by 2.5" / "add $8 markup to every variant" |
| Clean AliExpress titles | "remove Chinese characters from title" / "change title to ..." |
| Limit variants | "keep only first 3 images" / "drop the first image" |
| Batch + rules | "import all 5 links, uniform 2x pricing, all to backend" |

Rules are applied at the `prepare_import_candidate` stage and frozen as a snapshot — you can preview before pushing.

---

### 8. Rules

You can specify rules in natural language during import. The Agent converts them to structured rule objects:

#### Pricing Rules

| Description | Example |
|-------------|---------|
| Markup percentage | "mark up 50%" → `markup_percent: 50` |
| Fixed markup | "add $5 each" → `fixed_markup: 5` |
| Multiplier | "multiply price by 2.5" → `multiplier: 2.5` |

#### Content Rules

| Description | Example |
|-------------|---------|
| Title prefix | "add HOT before title" → `title_prefix: "HOT - "` |
| Title suffix | "add Free Shipping after title" → `title_suffix: " | Free Shipping"` |
| Title override | "change title to xxx" → `title_override: "xxx"` |

#### Image Rules

| Description | Example |
|-------------|---------|
| Limit image count | "keep only first 5 images" → `keep_first_n: 5` |
| Skip first image | "remove the first image" → `drop_indexes: [0]` |

---

### 9. FAQ

#### Q: Push fails with "shipping profile not found"

**Cause**: The target Shopify store requires a Delivery Profile binding.

**Solution**: This is now handled automatically. The system discovers the correct Shopify delivery profile via a dedicated API and attaches it to the push request. If you see this error:

1. Check `get_rule_capabilities` — it shows available shipping profiles for each Shopify store
2. Try specifying a profile by name: tell the Agent to use `shipping_profile_name: "DSers Shipping Profile"` (or whichever profile is listed)
3. Make sure the Shopify store has at least one Delivery Profile configured in DSers web UI (Settings > Shipping)

#### Q: Invalid credentials / login failed

1. Check `DSERS_EMAIL` and `DSERS_PASSWORD` in `.env`
2. Confirm `DSERS_ENV` matches your account environment (test / production)
3. Delete `.session-cache/` and retry (clears expired sessions)

#### Q: Target store not found

1. Confirm your DSers account has a linked Shopify store
2. Specify the store name or ID explicitly in conversation
3. Call `get_rule_capabilities` to see all available stores

#### Q: How to switch to production

Change `DSERS_ENV` in `.env` to `production`:

```ini
DSERS_ENV=production
```

Then restart the MCP server.

#### Q: Are suppliers other than AliExpress supported?

Currently supported:
- **AliExpress** — full support
- **Alibaba** — supported
- **1688** — supported

#### Q: How to use a different platform instead of DSers

Set the environment variable to switch provider:

```ini
IMPORT_PROVIDER_MODULE=dsers_mcp_product.mock_provider
```

`mock_provider` is a built-in offline simulator for development and demos. You can also implement your own provider (see [ARCHITECTURE.md](ARCHITECTURE.md) Section 5).

---

### 10. Troubleshooting Checklist

When you encounter issues, check in this order:

1. **`.env` file exists** — must be copied from `.env.example`
2. **Python version** — run `python3 --version` to confirm ≥ 3.10
3. **Dependencies installed** — run `pip install -r requirements.txt`
4. **Virtual environment active** — confirm terminal shows `(.venv)` prefix
5. **MCP client path** — confirm you're using the Python path inside venv
6. **Smoke test** — run `python smoke_dsers.py` and check output
7. **Check warnings** — all MCP responses include a `warnings` array, pay attention to hints

---
---

<a id="中文"></a>

## 中文

本文档面向**最终使用者**，介绍如何安装、配置并通过 AI Agent 使用本 MCP 完成商品导入与推送。

---

### 1. 前置条件

| 项目 | 要求 |
|------|------|
| Python | 3.10 或更高版本 |
| DSers 账号 | 已注册，且绑定了至少一个店铺（Shopify、Wix 或 WooCommerce） |
| MCP 客户端 | Cursor IDE、Claude Desktop 或其他支持 MCP 的 AI 客户端 |

---

### 2. 安装

```bash
# 克隆仓库
git clone https://github.com/lofder/dsers-mcp-product.git
cd dsers-mcp-product

# 创建虚拟环境并安装依赖
python3 -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

---

### 3. 配置

#### 3.1 创建 `.env` 文件

```bash
cp .env.example .env
```

#### 3.2 填写必需变量

用编辑器打开 `.env`，填入以下内容：

```ini
DSERS_EMAIL=你的DSers邮箱
DSERS_PASSWORD=你的DSers密码
DSERS_ENV=production
```

| 变量 | 说明 |
|------|------|
| `DSERS_EMAIL` | DSers 登录邮箱 |
| `DSERS_PASSWORD` | DSers 登录密码 |
| `DSERS_ENV` | `production`（默认）或 `test` |

> **安全提示**：`.env` 文件已被 `.gitignore` 排除，不会被提交到 Git。

#### 3.3 验证安装

```bash
# Mock 模式验证（无需凭据）
python smoke_mock.py

# DSers Provider 验证（需要凭据）
python smoke_dsers.py
```

如果 `smoke_dsers.py` 输出了 `capabilities` 且无报错，说明凭据配置正确。

---

### 4. 接入 AI 客户端

#### 4.1 Cursor IDE

在 Cursor 设置中找到 MCP 配置（Settings → MCP），添加：

```json
{
  "mcpServers": {
    "dsers-mcp-product": {
      "command": "/绝对路径/dsers-mcp-product/.venv/bin/python",
      "args": ["server.py"],
      "cwd": "/绝对路径/dsers-mcp-product"
    }
  }
}
```

> 将 `/绝对路径/` 替换为你的实际项目路径。使用虚拟环境的 Python 路径可以确保依赖正确加载。

#### 4.2 Claude Desktop

编辑 `~/Library/Application Support/Claude/claude_desktop_config.json`（macOS）：

```json
{
  "mcpServers": {
    "dsers-mcp-product": {
      "command": "/绝对路径/dsers-mcp-product/.venv/bin/python",
      "args": ["server.py"],
      "cwd": "/绝对路径/dsers-mcp-product"
    }
  }
}
```

配置完成后重启客户端，即可在对话中使用导入工具。

---

### 5. 使用方式

接入 MCP 后，你可以直接用自然语言指示 AI Agent 完成以下操作。

#### 5.1 导入并推送一个商品

> **你说**：帮我把这个商品导入到我的 Shopify 店铺
> https://www.aliexpress.com/item/1005006xxxxx.html
> 价格加价 50%，标题前面加上 "HOT - "

Agent 会自动执行以下流程：

1. 调用 `get_rule_capabilities` 获取店铺列表
2. 调用 `prepare_import_candidate` 导入商品并应用规则
3. 展示预览，询问你确认
4. 调用 `confirm_push_to_store` 推送到店铺
5. 调用 `get_job_status` 确认推送结果

#### 5.2 只预览不推送

> **你说**：帮我看看这个商品的详情，先不要推送
> https://www.aliexpress.com/item/1005006xxxxx.html

Agent 只会执行到预览步骤，等待你确认后才推送。

#### 5.3 批量导入和推送

> **你说**：把以下 5 个链接的商品都导入到我的店铺，统一加价 80%，先放后台
> - https://aliexpress.com/item/111.html
> - https://aliexpress.com/item/222.html
> - https://aliexpress.com/item/333.html
> - https://1688.com/offer/444.html
> - https://aliexpress.com/item/555.html

Agent 会一次调用批量导入所有 URL，然后批量推送所有有效结果。无效 URL 会在对应条目中报告，不影响其他条目。支持混合来源（速卖通 + 1688）。

#### 5.4 多店铺推送

> **你说**：把这个商品同时推送到我的 Shopify 店铺和 Wix 店铺

Agent 会使用 `target_stores` 一次调用推送到多个店铺。

#### 5.5 指定运费模板（Shopify）

> **你说**：推送这个商品，使用 "General profile" 运费模板

对于 Shopify 店铺，系统会自动发现可用的 delivery profile。默认使用 DSers 中标记为默认的 profile。你可以按名称指定使用其他 profile。

#### 5.6 指定推送选项

> **你说**：推送这个商品，但是先不要上架到前端，只在后台显示，同时开启自动同步库存

Agent 会将对应的 push_options 设置为：
- `publish_to_online_store: false`
- `auto_inventory_update: true`
- `visibility_mode: backend_only`

---

### 6. 推送选项详解

在对话中提到以下关键词，Agent 会自动匹配对应的推送选项：

| 你的描述 | 对应选项 | 值 |
|----------|----------|------|
| "上架" / "发布到前端" | `publish_to_online_store` | `true` |
| "只在后台" / "不上架" | `publish_to_online_store` | `false` |
| "推送所有图片" | `image_strategy` | `all_available` |
| "用店铺定价规则" | `pricing_rule_behavior` | `apply_store_pricing_rule` |
| "自动同步库存" | `auto_inventory_update` | `true` |
| "自动同步价格" | `auto_price_update` | `true` |
| "用 General profile" | `shipping_profile_name` | `"General profile"` |

---

### 7. 如何用 MCP 批量编辑变体

Dropshipping 中最耗时的操作之一就是编辑商品变体——调价格、清洗速卖通标题、删除不需要的选项。用这个 MCP 服务器，你可以通过自然语言批量编辑变体：

> **你说**：导入这 5 个商品，所有变体价格乘 3，去掉标题里的中文，只保留前 5 张图。

Agent 在一次批量调用中将规则应用到所有商品的所有变体，无需逐个手动点击。

| 任务 | 怎么说 |
|------|--------|
| 批量调价 | "所有价格乘 2.5" / "每个变体加 8 美元" |
| 清洗速卖通标题 | "去掉标题里的中文" / "标题改成 xxx" |
| 限制变体 | "只保留前 3 张图" / "去掉第一张图" |
| 批量 + 规则 | "导入所有 5 个链接，统一 2 倍加价，全部放后台" |

规则在 `prepare_import_candidate` 阶段应用并冻结为快照——推送前可以预览确认。

---

### 8. 规则说明

你可以在导入时通过自然语言指定规则，Agent 会转换为结构化规则对象：

#### 定价规则

| 描述 | 示例 |
|------|------|
| 加价百分比 | "加价 50%" → `markup_percent: 50` |
| 固定加价 | "每个加 5 美元" → `fixed_markup: 5` |
| 倍数 | "价格乘以 2.5" → `multiplier: 2.5` |

#### 内容规则

| 描述 | 示例 |
|------|------|
| 标题前缀 | "标题前加 HOT" → `title_prefix: "HOT - "` |
| 标题后缀 | "标题后加 Free Shipping" → `title_suffix: " | Free Shipping"` |
| 替换标题 | "把标题改成 xxx" → `title_override: "xxx"` |

#### 图片规则

| 描述 | 示例 |
|------|------|
| 限制图片数量 | "只保留前 5 张图" → `keep_first_n: 5` |
| 跳过首图 | "去掉第一张图" → `drop_indexes: [0]` |

---

### 9. 常见问题

#### Q: 推送失败提示 "shipping profile not found"

**原因**：目标 Shopify 店铺需要 Delivery Profile 绑定。

**解决**：现在已自动处理。系统通过专用 API 发现正确的 Shopify delivery profile 并附加到推送请求中。如果仍然看到此错误：

1. 检查 `get_rule_capabilities` — 它会显示每个 Shopify 店铺的可用运费模板
2. 尝试按名称指定：告诉 Agent 使用 `shipping_profile_name: "DSers Shipping Profile"`（或列表中的其他 profile）
3. 确保 Shopify 店铺在 DSers 网页端已配置至少一个 Delivery Profile（设置 > 运费）

#### Q: 提示凭据无效 / 登录失败

1. 检查 `.env` 中的 `DSERS_EMAIL` 和 `DSERS_PASSWORD` 是否正确
2. 确认 `DSERS_ENV` 值与你的账号环境匹配（test / production）
3. 删除 `.session-cache/` 目录后重试（清除过期的 session 缓存）

#### Q: 找不到目标店铺

1. 确认你的 DSers 账户已绑定 Shopify 店铺
2. 在对话中明确指定店铺名称或 ID
3. 调用 `get_rule_capabilities` 查看所有可用店铺

#### Q: 如何切换到生产环境

将 `.env` 中的 `DSERS_ENV` 改为 `production`：

```ini
DSERS_ENV=production
```

然后重启 MCP 服务器。

#### Q: 是否支持 AliExpress 以外的供应商

当前支持：
- **AliExpress（速卖通）** — 完整支持
- **Alibaba** — 支持
- **1688** — 支持

#### Q: 如何不使用 DSers，换成其他平台

设置环境变量切换 Provider：

```ini
IMPORT_PROVIDER_MODULE=dsers_mcp_product.mock_provider
```

`mock_provider` 是内置的离线模拟 Provider，用于开发和演示。你也可以实现自己的 Provider（参见 [ARCHITECTURE.md](ARCHITECTURE.md) 第 5 节）。

---

### 10. 故障排查清单

遇到问题时按以下顺序检查：

1. **`.env` 文件是否存在** — 必须从 `.env.example` 复制
2. **Python 版本** — 运行 `python3 --version` 确认 ≥ 3.10
3. **依赖是否安装** — 运行 `pip install -r requirements.txt`
4. **虚拟环境是否激活** — 确认终端前缀显示 `(.venv)`
5. **MCP 客户端路径** — 确认使用了虚拟环境内的 Python 路径
6. **冒烟测试** — 运行 `python smoke_dsers.py` 检查输出
7. **查看 warnings** — 所有 MCP 响应都包含 `warnings` 数组，注意其中的提示信息
