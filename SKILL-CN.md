# DSers MCP Product (Python) — 技能说明（中文）

> **注意：** TypeScript 版本现在是主要维护版本。请参见 [dsers-mcp-product](https://github.com/lofder/dsers-mcp-product)。

> 本文件是 [SKILL.md](SKILL.md) 的中文说明，供人阅读。SKILL.md 本身是给 AI agent 的指令文件。

## 这个 Skill 做什么

让 AI agent 通过 DSers 平台完成商品导入全流程：从速卖通 / Alibaba / 1688 链接到 Shopify / Wix / WooCommerce 店铺上架。

## 工作流程

| 步骤 | 工具 | 说明 |
|------|------|------|
| 1 | `get_rule_capabilities` | 获取店铺列表、配送方案、支持的规则 |
| 2 | `validate_rules` | （可选）校验规则是否合法 |
| 3 | `prepare_import_candidate` | 导入链接，应用定价/标题/图片规则，获取 job_id |
| 4 | `get_import_preview` | （可选）查看导入后的商品预览 |
| 5 | `set_product_visibility` | （可选）切换上架/后台 |
| 6 | `confirm_push_to_store` | 推送到店铺 |
| 7 | `get_job_status` | 确认推送结果 |

第 1 步是必须的，返回店铺列表、配送方案和规则约束。

## 支持的模式

- **单条导入**：一个链接 → 一个商品
- **批量导入**：多个链接一次调用，失败不互相影响
- **多店铺推送**：一个商品推到多个店铺
- **混合来源**：速卖通 + 1688 + Alibaba 链接可以混在同一批次

## 常见场景话术

| 场景 | 你对 AI 说 |
|------|-----------|
| 快速铺货 | "导入这个商品到我的店铺，价格乘 3，先不上架" |
| 批量导入 | "把这 5 个链接全部导入，统一加 5 美元，放后台" |
| 多店铺 | "导入这个商品，同时推到所有店铺" |
| 指定配送方案 | "推送时用 DSers Shipping Profile 配送方案" |
| 只预览 | "帮我看看这个商品导入后的效果，先不推" |
| 精选上架 | "只保留前 5 张图，标题前加 Premium，直接上架" |

## 规则说明

规则在导入阶段应用，推送时不会改变。用 `validate_rules` 可以先校验规则再导入。

| 类型 | 参数 | 示例 |
|------|------|------|
| 定价 | `mode` (provider_default, multiplier, fixed_markup), `multiplier`, `fixed_markup`, `round_digits` | "价格乘 3" / "加 5 美元" |
| 内容 | `title_prefix`, `title_suffix`, `title_override`, `description_override_html`, `description_append_html`, `tags_add` | "标题前加 HOT" |
| 图片 | `keep_first_n`, `drop_indexes` | "只保留前 5 张图" |

自然语言映射：
- "价格乘以 3" → `{"pricing": {"mode": "multiplier", "multiplier": 3}}`
- "加 5 美元" → `{"pricing": {"mode": "fixed_markup", "fixed_markup": 5}}`
- "标题前加 HOT" → `{"content": {"title_prefix": "HOT - "}}`
- "只保留前 5 张图" → `{"images": {"keep_first_n": 5}}`

## 推送选项

| 用户说的 | 键名 | 值 |
|---------|------|-----|
| "上架" / "发布" | `publish_to_online_store` | `true` |
| "草稿" | `publish_to_online_store` | `false` |
| "推送所有图片" | `image_strategy` | `"all_available"` |
| "用店铺定价规则" | `pricing_rule_behavior` | `"apply_store_pricing_rule"` |
| "自动同步库存" | `auto_inventory_update` | `true` |
| "自动同步价格" | `auto_price_update` | `true` |
| "指定配送方案" | `shipping_profile_name` | `"方案名称"` |

## 返回字段

### prepare_import_candidate / get_import_preview

- `job_id`：导入任务的唯一标识 — 后续操作都需要它
- `status`：`preview_ready`
- `title_before` / `title_after`：规则应用前后的标题
- `price_range_before` / `price_range_after`：`{min, max}` 价格区间
- `images_before` / `images_after`：图片数量
- `variant_count`：变体总数
- `variant_preview`：前 5 个变体的 `{title, supplier_price, offer_price, sku}`
- `warnings`：提示信息数组 — 一定要展示给用户

### confirm_push_to_store

- `job_id`、`status`：推送后的状态
- `visibility_applied`：实际可见性（backend_only 或 sell_immediately）
- `push_options_applied`：最终使用的推送选项
- `warnings`：提示信息 — 一定要展示给用户

### get_job_status

- `status`：`preview_ready` → `push_requested` → `completed` 或 `failed`
- `has_push_result`：布尔值 — 推送执行后为 true

## Shopify 配送方案

系统自动发现 Shopify 店铺的 delivery profile，不需要手动填 GID。默认使用 DSers 中标记为默认的方案。如果要指定其他方案，在 push_options 中设置 `shipping_profile_name`。

非 Shopify 店铺（Wix、WooCommerce）不涉及配送方案。

## 错误处理

- **导入失败**：检查 URL 格式。速卖通捆绑商品链接不支持。1688/Alibaba 需要 DSers 账户启用了对应来源。
- **"shipping profile not found"**：一般不会出现（自动发现）。如果出现，调用 `get_rule_capabilities` 查看可用方案，然后重试时指定 `shipping_profile_name`。
- **推送返回 `failed`**：检查 `warnings` 数组。常见原因：导入列表中的商品在准备和推送之间被删除。
- **未知 target_store**：错误消息会列出可用店铺。用 `get_rule_capabilities` 返回的 store_ref 或 display_name。
- 每个响应的 `warnings` 一定要展示给用户。
- 任务必须是 `preview_ready` 状态才能推送。

## 典型流程

**快速导入推送：**
```
get_rule_capabilities → prepare_import_candidate(source_url, rules) → confirm_push_to_store(job_id, target_store)
```

**批量混合来源：**
```
get_rule_capabilities → prepare_import_candidate(source_urls: [ae_url, 1688_url]) → confirm_push_to_store(job_ids: [...])
```

**先预览再推送：**
```
get_rule_capabilities → prepare_import_candidate(...) → 展示草稿给用户 → 用户确认 → confirm_push_to_store(...)
```

**先校验规则：**
```
get_rule_capabilities → validate_rules(rules: {...}) → 检查 errors → prepare_import_candidate(source_url, rules: 同样的规则)
```
