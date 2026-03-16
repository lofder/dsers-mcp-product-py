# Dropship Import MCP — Skill Guide / 技能指南

> [English](#english) | [中文](#中文)

---

<a id="english"></a>

## English

### When to Use This Skill

Use this MCP when a user wants to:

- Import a product from a supplier URL (AliExpress, Alibaba, 1688, etc.) into their online store
- Preview and edit product details before pushing to a store
- Push a prepared product to a connected store (Shopify, etc.)
- Check the status of a product push job
- Understand available pricing rules, content rules, or push options

### Workflow Overview

The import flow follows a **prepare → preview → confirm** pattern:

1. **Discover capabilities** — call `get_rule_capabilities` to see available stores, rule families, and push options.
2. **Prepare a candidate** — call `prepare_import_candidate` with a source URL, optional rules, and target store. Returns a preview bundle with a `job_id`.
3. **Review the preview** — call `get_import_preview` to inspect the prepared draft (title, images, variants, pricing).
4. **Adjust visibility** — optionally call `set_product_visibility` to switch between `backend_only` and `sell_immediately`.
5. **Push to store** — call `confirm_push_to_store` with the `job_id` and optional `push_options`.
6. **Check status** — call `get_job_status` to verify whether the push completed.

### Tool Reference

#### get_rule_capabilities

Returns the provider's supported stores, rule families, and push options.

```
{ "target_store": "optional store name or ref" }
```

#### validate_rules

Validates a rule object before preparing a candidate. Use this to check rules without starting the full import.

```
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

Resolves a source URL, imports the product, applies rules, and saves a preview bundle.

```
{
  "source_url": "https://www.aliexpress.com/item/123456.html",
  "country": "US",
  "target_store": "my-store",
  "visibility_mode": "backend_only",
  "rules": { "pricing": { "markup_percent": 30 } }
}
```

Returns a preview with `job_id`, title/image/variant diffs, and warnings.

#### get_import_preview

Reload a previously prepared preview by `job_id`.

#### set_product_visibility

Change the visibility mode of a prepared job before confirmation.

```
{ "job_id": "...", "visibility_mode": "sell_immediately" }
```

#### confirm_push_to_store

Push the prepared draft to the target store.

```
{
  "job_id": "...",
  "push_options": {
    "publish_to_online_store": true,
    "image_strategy": "all_available",
    "pricing_rule_behavior": "keep_manual",
    "auto_inventory_update": true,
    "auto_price_update": false,
    "store_shipping_profile": [
      {
        "storeId": "...",
        "locationId": "gid://shopify/DeliveryLocationGroup/...",
        "profileId": "gid://shopify/DeliveryProfile/..."
      }
    ]
  }
}
```

#### get_job_status

Returns the current status of a job (preview_ready, push_requested, completed, failed).

### Push Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `publish_to_online_store` | boolean | false | Make the product visible on the online storefront |
| `image_strategy` | string | `selected_only` | `selected_only` or `all_available` |
| `pricing_rule_behavior` | string | `keep_manual` | `keep_manual` or `apply_store_pricing_rule` |
| `auto_inventory_update` | boolean | false | Sync inventory automatically |
| `auto_price_update` | boolean | false | Sync price automatically |
| `sales_channels` | string[] | [] | Sales channel identifiers |
| `store_shipping_profile` | object[] | null | Platform delivery profile bindings (storeId, locationId, profileId) |

### Rules

Rules are applied during `prepare_import_candidate` and frozen into the job state.

- **pricing** — `markup_percent`, `fixed_markup`, `compare_at_percent`
- **content** — `title_prefix`, `title_suffix`, `title_replace`, `description_mode`
- **images** — `max_images`, `skip_first`
- **instruction_text** — free-form text instructions for the AI agent

### Error Handling

- If `prepare_import_candidate` fails, check the source URL format and country code.
- If `confirm_push_to_store` fails with a shipping profile error, provide `store_shipping_profile` in `push_options`.
- All responses include a `warnings` array — always surface these to the user.
- A job must be in `preview_ready` status before it can be confirmed.

---

<a id="中文"></a>

## 中文

### 何时使用本技能

当用户需要以下操作时使用本 MCP：

- 从供应商 URL（AliExpress、Alibaba、1688 等）导入商品到在线店铺
- 推送前预览和编辑商品详情
- 将准备好的商品推送到已连接的店铺（Shopify 等）
- 检查商品推送作业的状态
- 了解可用的定价规则、内容规则或推送选项

### 工作流概述

导入流程遵循 **准备 → 预览 → 确认** 模式：

1. **查询能力** — 调用 `get_rule_capabilities` 查看可用店铺、规则族和推送选项。
2. **准备候选** — 调用 `prepare_import_candidate` 传入来源 URL、可选规则和目标店铺。返回包含 `job_id` 的预览包。
3. **查看预览** — 调用 `get_import_preview` 检查准备好的草稿（标题、图片、变体、定价）。
4. **调整可见性** — 可选调用 `set_product_visibility` 切换 `backend_only` 和 `sell_immediately`。
5. **推送到店铺** — 调用 `confirm_push_to_store` 传入 `job_id` 和可选 `push_options`。
6. **检查状态** — 调用 `get_job_status` 确认推送是否完成。

### 工具参考

#### get_rule_capabilities

返回 Provider 支持的店铺、规则族和推送选项。

```
{ "target_store": "可选的店铺名称或引用" }
```

#### validate_rules

在准备候选之前校验规则对象。可用于在不启动完整导入的情况下检查规则。

```
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

```
{
  "source_url": "https://www.aliexpress.com/item/123456.html",
  "country": "US",
  "target_store": "my-store",
  "visibility_mode": "backend_only",
  "rules": { "pricing": { "markup_percent": 30 } }
}
```

返回包含 `job_id`、标题/图片/变体差异和警告的预览。

#### get_import_preview

通过 `job_id` 重新加载之前准备的预览。

#### set_product_visibility

在确认之前修改已准备作业的可见性模式。

```
{ "job_id": "...", "visibility_mode": "sell_immediately" }
```

#### confirm_push_to_store

将准备好的草稿推送到目标店铺。

```
{
  "job_id": "...",
  "push_options": {
    "publish_to_online_store": true,
    "image_strategy": "all_available",
    "pricing_rule_behavior": "keep_manual",
    "auto_inventory_update": true,
    "auto_price_update": false,
    "store_shipping_profile": [
      {
        "storeId": "...",
        "locationId": "gid://shopify/DeliveryLocationGroup/...",
        "profileId": "gid://shopify/DeliveryProfile/..."
      }
    ]
  }
}
```

#### get_job_status

返回作业的当前状态（preview_ready、push_requested、completed、failed）。

### Push Options

| 选项 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `publish_to_online_store` | boolean | false | 商品是否上架到在线店铺前端 |
| `image_strategy` | string | `selected_only` | `selected_only` 或 `all_available` |
| `pricing_rule_behavior` | string | `keep_manual` | `keep_manual` 或 `apply_store_pricing_rule` |
| `auto_inventory_update` | boolean | false | 自动同步库存 |
| `auto_price_update` | boolean | false | 自动同步价格 |
| `sales_channels` | string[] | [] | 销售渠道标识列表 |
| `store_shipping_profile` | object[] | null | 平台 Delivery Profile 绑定（storeId、locationId、profileId） |

### 规则

规则在 `prepare_import_candidate` 时应用，并冻结到作业状态中。

- **pricing（定价）** — `markup_percent`、`fixed_markup`、`compare_at_percent`
- **content（内容）** — `title_prefix`、`title_suffix`、`title_replace`、`description_mode`
- **images（图片）** — `max_images`、`skip_first`
- **instruction_text（指令文本）** — AI Agent 的自由文本指令

### 错误处理

- 如果 `prepare_import_candidate` 失败，检查来源 URL 格式和国家代码。
- 如果 `confirm_push_to_store` 因 shipping profile 错误失败，在 `push_options` 中提供 `store_shipping_profile`。
- 所有响应都包含 `warnings` 数组 — 务必将这些信息展示给用户。
- 作业必须处于 `preview_ready` 状态才能被确认。
