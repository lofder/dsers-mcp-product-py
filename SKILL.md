# DSers MCP Product — Skill Guide / 技能指南

> [English](#english) | [中文](#中文)

---

<a id="english"></a>

## English

### When to Use This Skill

Use this MCP when a user wants to:

- Import a product from a supplier URL (AliExpress, Alibaba, 1688) into their online store
- Batch-import multiple product URLs in one call
- Preview and edit product details before pushing to a store
- Push a prepared product to one or more connected stores (Shopify, Wix, WooCommerce)
- Check the status of a product push job
- Understand available pricing rules, content rules, push options, or Shopify shipping profiles

### Workflow Overview

The import flow follows a **prepare → preview → confirm** pattern:

1. **Discover capabilities** — call `get_rule_capabilities` to see available stores (with Shopify shipping profiles), rule families, and push options.
2. **Prepare a candidate** — call `prepare_import_candidate` with a single URL or a list of URLs, optional rules, and target store. Returns preview bundle(s) with `job_id`(s).
3. **Review the preview** — call `get_import_preview` to inspect the prepared draft (title, images, variants, pricing).
4. **Adjust visibility** — optionally call `set_product_visibility` to switch between `backend_only` and `sell_immediately`.
5. **Push to store** — call `confirm_push_to_store` with `job_id` and optional `push_options`. Supports single, batch, and multi-store push.
6. **Check status** — call `get_job_status` to verify whether the push completed.

### Tool Reference

#### get_rule_capabilities

Returns the provider's supported stores, rule families, and push options. For Shopify stores, also returns available shipping profiles (name, is_default, countries, rate) so the user can choose one.

```json
{ "target_store": "optional store name or ref" }
```

#### validate_rules

Validates a rule object before preparing a candidate. Use this to check rules without starting the full import.

```json
{
  "target_store": "optional",
  "rules": {
    "pricing": { "markup_percent": 50 },
    "content": { "title_prefix": "HOT - " },
    "images": { "max_images": 10 }
  }
}
```

#### prepare_import_candidate

Resolves source URL(s), imports products, applies rules, and saves preview bundle(s).

**Single mode:**

```json
{
  "source_url": "https://www.aliexpress.com/item/123456.html",
  "country": "US",
  "target_store": "my-store",
  "visibility_mode": "backend_only",
  "rules": { "pricing": { "markup_percent": 30 } }
}
```

**Batch mode:**

```json
{
  "source_urls": [
    "https://www.aliexpress.com/item/111.html",
    "https://www.aliexpress.com/item/222.html",
    { "url": "https://www.aliexpress.com/item/333.html", "rules": { "pricing": { "markup_percent": 80 } } }
  ],
  "country": "US",
  "target_store": "my-store"
}
```

In batch mode, each URL is processed independently — failures do not block other items. Each item in `source_urls` can be a plain URL string or an object with per-item overrides (`url`, `source_hint`, `country`, `target_store`, `rules`).

Returns `results[]` array with `job_id` and `status` per item.

#### get_import_preview

Reload a previously prepared preview by `job_id`.

#### set_product_visibility

Change the visibility mode of a prepared job before confirmation.

```json
{ "job_id": "...", "visibility_mode": "sell_immediately" }
```

#### confirm_push_to_store

Push prepared drafts to store(s). Supports three modes:

**Single mode:**

```json
{
  "job_id": "abc-123",
  "target_store": "newtestbaiyuxin03",
  "push_options": { "shipping_profile_name": "DSers Shipping Profile" }
}
```

**Batch mode:**

```json
{
  "job_ids": ["abc-123", "def-456", "ghi-789"],
  "target_store": "newtestbaiyuxin03"
}
```

Each item in `job_ids` can also be an object with per-item overrides: `{ "job_id": "...", "target_store": "...", "push_options": {...} }`.

**Multi-store mode:**

```json
{
  "job_id": "abc-123",
  "target_stores": ["newtestbaiyuxin03", "Officialteststorefor"]
}
```

Pushes one product to multiple stores. Batch + multi-store combines as N jobs x M stores.

#### get_job_status

Returns the current status of a job: `preview_ready`, `push_requested`, `completed`, or `failed`.

### Push Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `publish_to_online_store` | boolean | false | Make the product visible on the online storefront |
| `image_strategy` | string | `selected_only` | `selected_only` or `all_available` |
| `pricing_rule_behavior` | string | `keep_manual` | `keep_manual` or `apply_store_pricing_rule` |
| `auto_inventory_update` | boolean | false | Sync inventory automatically |
| `auto_price_update` | boolean | false | Sync price automatically |
| `sales_channels` | string[] | [] | Sales channel identifiers |
| `shipping_profile_name` | string | null | Shopify delivery profile name (e.g. "DSers Shipping Profile"). If omitted, the default profile is used automatically. |
| `store_shipping_profile` | object[] | null | Manual override: raw delivery profile bindings (storeId, locationId, profileId). Rarely needed — the system auto-discovers profiles for Shopify stores. |

### Rules

Rules are applied during `prepare_import_candidate` and frozen into the job state.

- **pricing** — `markup_percent`, `fixed_markup`, `compare_at_percent`
- **content** — `title_prefix`, `title_suffix`, `title_replace`, `description_mode`
- **images** — `max_images`, `skip_first`
- **instruction_text** — free-form text instructions for the AI agent

### Error Handling

- If `prepare_import_candidate` fails, check the source URL format and country code. In batch mode, individual failures are returned per-item and do not block other items.
- If `confirm_push_to_store` fails with a shipping profile error on Shopify, the system automatically discovers the correct delivery profile via API. If the store has no profile configured in DSers, a detailed warning is returned. You can manually specify `shipping_profile_name` in `push_options` to choose a specific profile.
- All responses include a `warnings` array — always surface these to the user.
- A job must be in `preview_ready` status before it can be confirmed.

### Scenario Prompts

Standard prompts for each supported scenario. AI translates these into the correct tool calls.

| Scenario | Prompt (English) | Prompt (Chinese) |
|----------|-----------------|-------------------|
| **Quick import** | "Import this product to my store, 3x the price, don't publish yet. `https://aliexpress.com/item/xxx.html`" | "导入这个商品到我的店铺，价格乘 3，先不上架。`https://aliexpress.com/item/xxx.html`" |
| **Curated listing** | "Import this product, keep first 5 images, translate title to English, publish directly." | "导入这个商品，只保留前 5 张图，标题翻译成英文，直接上架。" |
| **High-margin pricing** | "Import, 4x price, use store pricing rule, auto-sync inventory." | "导入这个商品，价格乘 4，用店铺定价规则，自动同步库存。" |
| **Test product** | "Import to backend only, don't publish, I want to check data first." | "导入到后台，不发布、不上架，我先看看数据。" |
| **Batch import** | "Import all 5 links below to my store, uniform 2.5x pricing, all to backend." | "把这 5 个链接全部导入，价格统一乘 2.5，全部先放后台。" |
| **Multi-store sync** | "Import this product and push it to both my Shopify store and my Wix store." | "导入这个商品，同时推送到我的 Shopify 店铺和 Wix 店铺。" |
| **Mixed-source batch** | "Import these links (AliExpress + 1688 mixed), push all valid ones to my store." | "导入这些链接（速卖通 + 1688 混合），把能导入的全部推送到我的店铺。" |
| **Choose shipping profile** | "Push this product using the 'General profile' shipping profile instead of the default." | "推送这个商品，使用 'General profile' 而不是默认的运费模板。" |
| **Pre-push preview** | "Show me what this product will look like after import, don't push yet." | "帮我看看这个商品导入后的效果，先不要推送。" |
| **Change visibility** | "Change this product from backend-only to published on the online store." | "把这个商品从后台改成上架到在线商店。" |
| **Check status** | "What's the status of my last product push?" | "我上次推送的商品状态是什么？" |
| **Retry after failure** | "The last push failed, try pushing again to the same store." | "上次推送失败了，再推送一次到同一个店铺。" |

---

<a id="中文"></a>

## 中文

### 何时使用本技能

当用户需要以下操作时使用本 MCP：

- 从供应商 URL（AliExpress、Alibaba、1688）导入商品到在线店铺
- 一次调用批量导入多个商品链接
- 推送前预览和编辑商品详情
- 将准备好的商品推送到一个或多个已连接的店铺（Shopify、Wix、WooCommerce）
- 检查商品推送作业的状态
- 了解可用的定价规则、内容规则、推送选项或 Shopify 运费模板

### 工作流概述

导入流程遵循 **准备 → 预览 → 确认** 模式：

1. **查询能力** — 调用 `get_rule_capabilities` 查看可用店铺（含 Shopify 运费模板列表）、规则族和推送选项。
2. **准备候选** — 调用 `prepare_import_candidate` 传入单条或多条 URL、可选规则和目标店铺。返回包含 `job_id` 的预览包。
3. **查看预览** — 调用 `get_import_preview` 检查准备好的草稿（标题、图片、变体、定价）。
4. **调整可见性** — 可选调用 `set_product_visibility` 切换 `backend_only` 和 `sell_immediately`。
5. **推送到店铺** — 调用 `confirm_push_to_store` 传入 `job_id` 和可选 `push_options`。支持单条、批量和多店铺推送。
6. **检查状态** — 调用 `get_job_status` 确认推送是否完成。

### 工具参考

#### get_rule_capabilities

返回 Provider 支持的店铺、规则族和推送选项。对于 Shopify 店铺，还会返回可用的运费模板列表（名称、是否默认、覆盖国家数、运费），供用户选择。

```json
{ "target_store": "可选的店铺名称或引用" }
```

#### validate_rules

在准备候选之前校验规则对象。可用于在不启动完整导入的情况下检查规则。

```json
{
  "target_store": "可选",
  "rules": {
    "pricing": { "markup_percent": 50 },
    "content": { "title_prefix": "HOT - " },
    "images": { "max_images": 10 }
  }
}
```

#### prepare_import_candidate

解析来源 URL，导入商品，应用规则，保存预览包。

**单条模式：**

```json
{
  "source_url": "https://www.aliexpress.com/item/123456.html",
  "country": "US",
  "target_store": "my-store",
  "visibility_mode": "backend_only",
  "rules": { "pricing": { "markup_percent": 30 } }
}
```

**批量模式：**

```json
{
  "source_urls": [
    "https://www.aliexpress.com/item/111.html",
    "https://www.aliexpress.com/item/222.html",
    { "url": "https://www.aliexpress.com/item/333.html", "rules": { "pricing": { "markup_percent": 80 } } }
  ],
  "country": "US",
  "target_store": "my-store"
}
```

批量模式下每条 URL 独立处理——单条失败不影响其他条目。`source_urls` 中的每个元素可以是纯 URL 字符串或带有逐条覆盖参数的对象（`url`、`source_hint`、`country`、`target_store`、`rules`）。

返回 `results[]` 数组，每条包含 `job_id` 和 `status`。

#### get_import_preview

通过 `job_id` 重新加载之前准备的预览。

#### set_product_visibility

在确认之前修改已准备作业的可见性模式。

```json
{ "job_id": "...", "visibility_mode": "sell_immediately" }
```

#### confirm_push_to_store

将准备好的草稿推送到店铺。支持三种模式：

**单条模式：**

```json
{
  "job_id": "abc-123",
  "target_store": "newtestbaiyuxin03",
  "push_options": { "shipping_profile_name": "DSers Shipping Profile" }
}
```

**批量模式：**

```json
{
  "job_ids": ["abc-123", "def-456", "ghi-789"],
  "target_store": "newtestbaiyuxin03"
}
```

`job_ids` 中的每个元素也可以是带逐条覆盖的对象：`{ "job_id": "...", "target_store": "...", "push_options": {...} }`。

**多店铺模式：**

```json
{
  "job_id": "abc-123",
  "target_stores": ["newtestbaiyuxin03", "Officialteststorefor"]
}
```

将一个商品推送到多个店铺。批量 + 多店铺组合为 N 个作业 x M 个店铺。

#### get_job_status

返回作业的当前状态：`preview_ready`、`push_requested`、`completed` 或 `failed`。

### Push Options

| 选项 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `publish_to_online_store` | boolean | false | 商品是否上架到在线店铺前端 |
| `image_strategy` | string | `selected_only` | `selected_only` 或 `all_available` |
| `pricing_rule_behavior` | string | `keep_manual` | `keep_manual` 或 `apply_store_pricing_rule` |
| `auto_inventory_update` | boolean | false | 自动同步库存 |
| `auto_price_update` | boolean | false | 自动同步价格 |
| `sales_channels` | string[] | [] | 销售渠道标识列表 |
| `shipping_profile_name` | string | null | Shopify 运费模板名称（如 "DSers Shipping Profile"）。不指定则自动使用默认模板。 |
| `store_shipping_profile` | object[] | null | 手动覆盖：原始 delivery profile 绑定（storeId、locationId、profileId）。极少需要——系统会自动为 Shopify 店铺发现 profile。 |

### 规则

规则在 `prepare_import_candidate` 时应用，并冻结到作业状态中。

- **pricing（定价）** — `markup_percent`、`fixed_markup`、`compare_at_percent`
- **content（内容）** — `title_prefix`、`title_suffix`、`title_replace`、`description_mode`
- **images（图片）** — `max_images`、`skip_first`
- **instruction_text（指令文本）** — AI Agent 的自由文本指令

### 错误处理

- 如果 `prepare_import_candidate` 失败，检查来源 URL 格式和国家代码。批量模式下单条失败会在对应条目中返回，不影响其他条目。
- 如果 `confirm_push_to_store` 因 Shopify shipping profile 错误失败，系统会自动通过 API 发现正确的 delivery profile。如果店铺在 DSers 中没有配置 profile，会返回详细警告。可通过 `push_options` 中的 `shipping_profile_name` 手动指定特定 profile。
- 所有响应都包含 `warnings` 数组 — 务必将这些信息展示给用户。
- 作业必须处于 `preview_ready` 状态才能被确认。

### 场景提示词

覆盖所有支持场景的标准提示词，AI 会自动翻译为正确的工具调用。

| 场景 | 中文提示词 | English Prompt |
|------|-----------|----------------|
| **快速铺货** | "导入这个商品到我的店铺，价格乘 3，先不上架。`https://aliexpress.com/item/xxx.html`" | "Import this product to my store, 3x the price, don't publish yet." |
| **精选上架** | "导入这个商品，只保留前 5 张图，标题翻译成英文，直接上架。" | "Import this product, keep first 5 images, translate title to English, publish directly." |
| **高利润定价** | "导入这个商品，价格乘 4，用店铺定价规则，自动同步库存。" | "Import, 4x price, use store pricing rule, auto-sync inventory." |
| **测品** | "导入到后台，不发布、不上架，我先看看数据。" | "Import to backend only, don't publish, I want to check data first." |
| **批量铺货** | "把这 5 个链接全部导入，价格统一乘 2.5，全部先放后台。" | "Import all 5 links, uniform 2.5x pricing, all to backend." |
| **多店铺同步** | "导入这个商品，同时推送到我的 Shopify 店铺和 Wix 店铺。" | "Import this product and push it to both my Shopify and Wix stores." |
| **混合来源批量** | "导入这些链接（速卖通 + 1688 混合），把能导入的全部推送。" | "Import these links (AliExpress + 1688 mixed), push all valid ones." |
| **指定运费模板** | "推送这个商品，使用 'General profile' 而不是默认的运费模板。" | "Push using the 'General profile' shipping profile instead of default." |
| **推送前预览** | "帮我看看这个商品导入后的效果，先不要推送。" | "Show me what this product looks like after import, don't push yet." |
| **调整可见性** | "把这个商品从后台改成上架到在线商店。" | "Change from backend-only to published on the online store." |
| **查询状态** | "我上次推送的商品状态是什么？" | "What's the status of my last product push?" |
| **失败重试** | "上次推送失败了，再推送一次到同一个店铺。" | "The last push failed, try pushing again to the same store." |
