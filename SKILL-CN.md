# DSers MCP Product — 技能说明（中文）

> 本文件是 [SKILL.md](SKILL.md) 的中文说明，供人阅读。SKILL.md 本身是给 AI agent 的指令文件。

## 这个 Skill 做什么

让 AI agent 通过 DSers 平台完成商品导入全流程：从速卖通 / Alibaba / 1688 链接到 Shopify / Wix / WooCommerce 店铺上架。

## 工作流程

```
查询能力 → 导入商品 → 预览 → 推送到店铺 → 确认状态
```

| 步骤 | 工具 | 说明 |
|------|------|------|
| 1 | `get_rule_capabilities` | 获取店铺列表、运费模板、支持的规则 |
| 2 | `prepare_import_candidate` | 导入链接，应用定价/标题/图片规则 |
| 3 | `get_import_preview` | （可选）查看导入后的商品预览 |
| 4 | `set_product_visibility` | （可选）切换上架/后台 |
| 5 | `confirm_push_to_store` | 推送到店铺 |
| 6 | `get_job_status` | 确认推送结果 |

## 支持的模式

- **单条导入**：一个链接 → 一个商品
- **批量导入**：多个链接一次调用，失败不互相影响
- **多店铺推送**：一个商品推到多个店铺
- **混合来源**：速卖通 + 1688 + Alibaba 链接可以混在同一批次

## 常见场景话术

| 场景 | 你对 AI 说 |
|------|-----------|
| 快速铺货 | "导入这个商品到我的店铺，价格乘 3，先不上架" |
| 批量导入 | "把这 5 个链接全部导入，统一加价 80%，放后台" |
| 多店铺 | "导入这个商品，同时推到 Shopify 和 Wix 店铺" |
| 指定运费模板 | "推送时用 General profile 运费模板" |
| 只预览 | "帮我看看这个商品导入后的效果，先不推" |
| 精选上架 | "只保留前 5 张图，标题改成英文，直接上架" |

## 规则说明

规则在导入阶段应用，推送时不会改变。

| 类型 | 参数 | 示例 |
|------|------|------|
| 定价 | `markup_percent`, `multiplier`, `fixed_markup` | "加价 50%" / "价格乘 3" |
| 内容 | `title_prefix`, `title_suffix`, `title_override` | "标题前加 HOT" |
| 图片 | `keep_first_n`, `drop_indexes` | "只保留前 5 张图" |

## Shopify 运费模板

系统自动发现 Shopify 店铺的 delivery profile，不需要手动填 GID。默认使用 DSers 中标记为默认的模板。如果要指定其他模板，告诉 AI 用 `shipping_profile_name`。

非 Shopify 店铺（Wix、WooCommerce）不涉及运费模板。
