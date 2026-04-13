# DSers MCP Product (Python) v1.5.7 -- 技能说明（中文）

> **TypeScript 版本是主要维护版本。** 请参见 [dsers-mcp-product](https://github.com/lofder/dsers-mcp-product)。

> 本文件是 [SKILL.md](SKILL.md) 的中文版本。

## 工具列表

共 13 个工具。工具 1-7 覆盖核心导入推送流程，工具 8-13 增加浏览、规则更新、商品搜索和供应商重映射功能。

### 核心流程工具 (1-7)

| # | 工具 | 说明 | 必需参数 |
|---|------|------|----------|
| 1 | `get_rule_capabilities` | 查询店铺（含 Shopify 运费模板）、规则族、推送选项 | -- |
| 2 | `validate_rules` | 校验并归一化规则对象；返回 effective_rules_snapshot 和 errors | `rules` |
| 3 | `prepare_import_candidate` | 从供应商 URL 导入 -- 单条（`source_url`）或批量（`source_urls`）；应用规则，返回带 job_id 的预览 | `source_url` 或 `source_urls` |
| 4 | `get_import_preview` | 查看已准备的草稿预览；支持简洁和完整变体详情 | `job_id` |
| 5 | `set_product_visibility` | 切换可见性：`backend_only`（草稿）或 `sell_immediately`（上架） | `job_id`, `visibility_mode` |
| 6 | `confirm_push_to_store` | 推送到店铺 -- 单条、批量（`job_ids`）或多店铺（`target_stores`）；含预推送安全校验 | `job_id` 或 `job_ids` |
| 7 | `get_job_status` | 查询推送状态。状态值：`preview_ready` / `push_requested` / `completed` / `failed` / `persist_failed` | `job_id` |

### 扩展工具 (8-13)

| # | 工具 | 说明 | 必需参数 |
|---|------|------|----------|
| 8 | `dsers_product_update_rules` | 在已导入的商品上更新定价、内容、图片、变体覆盖或选项编辑规则。规则按族增量合并。 | `job_id` |
| 9 | `dsers_find_product` | 通过关键词或图片 URL（视觉搜索）搜索 DSers 商品库。返回带 import_url 的商品，可直接导入。 | `keyword` 或 `image_url` |
| 10 | `dsers_import_list` | 浏览 DSers 导入列表，含丰富的变体数据、定价、库存信息和推送状态。 | -- |
| 11 | `dsers_my_products` | 浏览已推送到店铺的商品。需要 get_rule_capabilities 返回的 store_id。 | `store_id` |
| 12 | `dsers_product_delete` | 从导入列表永久删除商品。不可逆。需要显式 `confirm=true`。 | `import_item_id` |
| 13 | `dsers_sku_remap` | 替换已上架商品的供应商，支持变体级别 SKU 匹配。两种模式：精确模式（提供 URL）或发现模式（自动反向图片搜索）。 | `dsers_product_id`, `store_id` |

## 工作流程

核心导入流程必须按以下顺序：

1. `get_rule_capabilities` -- 获取店铺、配送方案、支持的规则（必须首先调用）
2. `validate_rules` -- （可选）导入前校验规则
3. `prepare_import_candidate` -- 从 URL 导入，应用规则，获取带 job_id 的预览
4. `get_import_preview` -- （可选）重新加载已保存的预览
5. `set_product_visibility` -- （可选）切换 backend_only / sell_immediately
6. `confirm_push_to_store` -- 推送到店铺
7. `get_job_status` -- 确认推送结果

第 1 步是必须的 -- 它返回店铺列表、配送方案和规则约束。

## v1.5.7 行为变更

- **Tags 不通过 PUT 写入**：Tags 在导入时通过规则引擎应用，不通过单独的 PUT 调用。它们被冻结到作业中。
- **`persist_failed` 状态**：如果规则更新后持久化到 DSers 后端失败，作业状态设为 `persist_failed`。推送被阻止直到规则更新成功。重试 `dsers_product_update_rules` 或重新导入商品。
- **HTML 注入拦截**：描述字段（`description_override_html`、`description_append_html`）会被清洗。Script 标签、事件处理器和其他危险 HTML 模式会被剥离。内容被清洗时响应中会包含警告。
- **极端定价警告**：系统在定价值异常时发出警告（但不阻止）：倍率 >100x、固定加价 >$500、固定价格 >$10,000。

## 规则

规则在 `prepare_import_candidate` 时应用，并冻结到作业中。推送时不会改变。使用 `dsers_product_update_rules` 修改已导入商品的规则。

### 规则族

| 族 | 键 | 备注 |
|----|-----|------|
| **pricing** | `mode`（multiplier, fixed_markup, fixed_price）、`multiplier`、`fixed_markup`、`fixed_price`、`round_digits` | 三种定价模式 |
| **content** | `title_prefix`、`title_suffix`、`title_override`、`description_override_html`、`description_append_html`、`tags_add` | HTML 描述会被清洗 |
| **images** | `keep_first_n`、`drop_indexes`、`reorder`、`add_urls` | |
| **variant_overrides** | `{match, sell_price, compare_at_price}` 数组 | 按变体名称子串匹配 |
| **option_edits** | 动作数组：`rename_option`、`rename_value`、`remove_value`、`remove_option` | 始终完整替换，非增量 |

### 自然语言映射

- "价格乘以 3" -> `{ "pricing": { "mode": "multiplier", "multiplier": 3 } }`
- "加 5 美元" -> `{ "pricing": { "mode": "fixed_markup", "fixed_markup": 5 } }`
- "设置价格为 19.99 美元" -> `{ "pricing": { "mode": "fixed_price", "fixed_price": 19.99 } }`
- "标题前加 HOT" -> `{ "content": { "title_prefix": "HOT - " } }`
- "只保留前 5 张图" -> `{ "images": { "keep_first_n": 5 } }`
- "把 Color 重命名为 Style" -> `{ "option_edits": [{ "action": "rename_option", "option_name": "Color", "new_name": "Style" }] }`

使用 `validate_rules` 在导入前检查规则 -- 它返回 `effective_rules_snapshot`（将被应用的内容）、`warnings`（调整）和 `errors`（阻止性问题）。

## 推送安全防护

`confirm_push_to_store` 自动执行预推送校验。

### 阻止（推送被拒绝）

- 售价 < 成本（每笔订单都会亏钱）
- 所有变体库存为零

### 警告（推送继续，需展示给用户）

- 低利润率（<10%）
- 低库存（任意变体 <5 件）
- 超低价格（<$1）
- 极端定价值

使用 `force_push=true` 覆盖阻止，但仅在向用户解释风险并获得明确确认后。

## SKU 重映射

`dsers_sku_remap` 在已上架商品上替换供应商，支持变体级别匹配。

### 两种路径

| 路径 | 触发方式 | 行为 |
|------|---------|------|
| **精确模式** | 提供 `new_supplier_url` | 获取指定供应商，按 SKU 属性匹配变体 |
| **发现模式** | 不提供 `new_supplier_url` | 反向图片搜索 DSers 商品库，多因素评分排名候选，自动选择最佳替代 |

### 使用流程

1. 使用 `mode='preview'`（默认，只读）调用查看匹配方案和差异
2. 审查变体映射（swapped / kept_old / unmatched 计数）
3. 使用 `mode='apply'` 再次调用以持久化替换

`auto_confidence` 阈值默认为 70。低于此置信度的变体保留原供应商。

## 推送模式

- **单条**：`job_id` + `target_store`
- **批量**：`job_ids`（数组）+ `target_store`
- **多店铺**：`job_id` + `target_stores`（数组）
- **批量 + 多店铺**：`job_ids` + `target_stores` -> N 个作业 x M 个店铺

## 推送选项

| 用户说的 | 选项 | 值 |
|---------|------|-----|
| "上架" / "发布" | `publish_to_online_store` | `true` |
| "草稿" / "放后台" | `publish_to_online_store` | `false` |
| "推送所有图片" | `image_strategy` | `all_available` |
| "用店铺定价规则" | `pricing_rule_behavior` | `apply_store_pricing_rule` |
| "自动同步库存" | `auto_inventory_update` | `true` |
| "自动同步价格" | `auto_price_update` | `true` |
| "指定配送方案" | `shipping_profile_name` | `"方案名称"` |

## Shopify 配送方案

自动发现，不需要手动填 GID。

- 默认：使用 DSers 中标记为默认的方案
- 指定：在 push_options 中设置 `shipping_profile_name`
- `get_rule_capabilities` 返回每个 Shopify 店铺的 `shipping_profiles`
- 非 Shopify 店铺完全跳过配送方案

## 错误处理

所有错误遵循结构化格式，包含清晰的错误消息和可操作的指引。

| 场景 | 处理方式 |
|------|---------|
| 导入失败 | 检查 URL 格式。捆绑商品链接不支持。1688/Alibaba 需要 DSers 账户启用了对应来源。 |
| "shipping profile not found" | 调用 `get_rule_capabilities` 查看可用方案，重试时指定 `shipping_profile_name`。 |
| 推送返回 `failed` | 检查 `warnings` 数组。常见原因：导入列表中的商品在准备和推送之间被删除。 |
| `persist_failed` 状态 | 规则更新未能保存到 DSers 后端。重试 `dsers_product_update_rules` 或重新导入。推送被阻止。 |
| 未知 `target_store` | 错误消息会列出可用店铺。使用 `get_rule_capabilities` 返回的 store_ref 或 display_name。 |
| 推送被安全防护阻止 | 修正定价规则或在用户确认风险后使用 `force_push=true`。 |

每个响应的 `warnings` 一定要展示给用户。任务必须是 `preview_ready` 状态才能推送。

## 典型流程

**快速导入推送：**
```
get_rule_capabilities -> prepare_import_candidate(source_url, rules) -> confirm_push_to_store(job_id, target_store)
```

**批量混合来源：**
```
get_rule_capabilities -> prepare_import_candidate(source_urls: [ae_url, 1688_url]) -> confirm_push_to_store(job_ids: [...])
```

**更新已导入商品的规则：**
```
dsers_product_update_rules(job_id, pricing_mode="fixed_price", pricing_fixed_price=19.99) -> get_import_preview(job_id) -> confirm_push_to_store(job_id)
```

**浏览并搜索商品：**
```
dsers_find_product(keyword="phone case") -> prepare_import_candidate(source_url=result.import_url)
```

**替换已上架商品的供应商：**
```
dsers_my_products(store_id) -> dsers_sku_remap(dsers_product_id, store_id, mode="preview") -> 审查差异 -> dsers_sku_remap(..., mode="apply")
```

**自动发现替代供应商：**
```
dsers_sku_remap(dsers_product_id, store_id, mode="preview") -> 审查候选 -> dsers_sku_remap(..., mode="apply")
```
