---
name: dsers-mcp-product-py
description: Automate DSers product import, rules editing, SKU remapping, and push to Shopify/Wix/WooCommerce stores. Use when the user wants to import, edit, price, browse, remap, or push dropshipping products via DSers. (Python version v1.5.7 -- TypeScript version is primary)
---

# DSers MCP Product (Python) v1.5.7

## Tools

13 tools in total. Tools 1-7 cover the core import-to-push workflow. Tools 8-13 add browsing, rule updates, product search, and supplier remapping.

### Core Workflow (1-7)

| # | Tool | Description | Required Params |
|---|------|-------------|-----------------|
| 1 | `get_rule_capabilities` | Query stores (with Shopify shipping profiles), rule families, push options | -- |
| 2 | `validate_rules` | Validate and normalize a rules object; returns effective_rules_snapshot and errors | `rules` |
| 3 | `prepare_import_candidate` | Import from supplier URL(s) -- single (`source_url`) or batch (`source_urls`); apply rules, return preview with job_id | `source_url` or `source_urls` |
| 4 | `get_import_preview` | View prepared draft preview; supports compact and full variant detail | `job_id` |
| 5 | `set_product_visibility` | Toggle visibility: `backend_only` (draft) or `sell_immediately` (live) | `job_id`, `visibility_mode` |
| 6 | `confirm_push_to_store` | Push to store(s) -- single, batch (`job_ids`), or multi-store (`target_stores`); includes pre-push safety validation | `job_id` or `job_ids` |
| 7 | `get_job_status` | Query push status. Statuses: `preview_ready` / `push_requested` / `completed` / `failed` / `persist_failed` | `job_id` |

### Extended Tools (8-13)

| # | Tool | Description | Required Params |
|---|------|-------------|-----------------|
| 8 | `dsers_product_update_rules` | Update pricing, content, images, variant_overrides, or option_edits on an already-imported product. Rules merge incrementally by family. | `job_id` |
| 9 | `dsers_find_product` | Search the DSers product pool by keyword or image URL (visual search). Returns products with import_url for direct import. | `keyword` or `image_url` |
| 10 | `dsers_import_list` | Browse the DSers import list with enriched variant data, pricing, stock info, and push status. | -- |
| 11 | `dsers_my_products` | Browse products already pushed to a store. Requires store_id from get_rule_capabilities. | `store_id` |
| 12 | `dsers_product_delete` | Permanently delete a product from the import list. Irreversible. Requires explicit `confirm=true`. | `import_item_id` |
| 13 | `dsers_sku_remap` | Replace the supplier on a store product with SKU-level variant matching. Two modes: strict (provide URL) or discover (auto reverse-image search). | `dsers_product_id`, `store_id` |

## Workflow

Always follow this order for the core import flow:

1. `get_rule_capabilities` -- discover stores, shipping profiles, supported rules (required first)
2. `validate_rules` -- (optional) dry-run rule validation before importing
3. `prepare_import_candidate` -- import from URL(s), apply rules, get preview with job_id
4. `get_import_preview` -- (optional) reload a saved preview
5. `set_product_visibility` -- (optional) toggle backend_only / sell_immediately
6. `confirm_push_to_store` -- push to store(s)
7. `get_job_status` -- verify push result

Step 1 is required before any import -- it returns the store list, shipping profiles, and rule constraints.

## v1.5.7 Behavior Changes

- **Tags not written via PUT**: Tags are applied through the rules engine at import time, not through a separate PUT call. They are frozen into the job.
- **`persist_failed` status**: If rule persistence to the DSers backend fails after update, the job status is set to `persist_failed`. Push is blocked until the rule update succeeds. Retry `dsers_product_update_rules` or re-import the product.
- **HTML injection blocking**: Description fields (`description_override_html`, `description_append_html`) are sanitized. Script tags, event handlers, and other dangerous HTML patterns are stripped. The response includes a warning when content is sanitized.
- **Extreme pricing warnings**: The system warns (but does not block) when pricing values are unusual: multiplier >100x, fixed_markup >$500, fixed_price >$10,000.

## Rules

Rules are applied at `prepare_import_candidate` time and frozen into the job. They do NOT change at push time. Use `dsers_product_update_rules` to modify rules on an existing import.

### Rule Families

| Family | Keys | Notes |
|--------|------|-------|
| **pricing** | `mode` (multiplier, fixed_markup, fixed_price), `multiplier`, `fixed_markup`, `fixed_price`, `round_digits` | Three pricing modes |
| **content** | `title_prefix`, `title_suffix`, `title_override`, `description_override_html`, `description_append_html`, `tags_add` | HTML descriptions are sanitized |
| **images** | `keep_first_n`, `drop_indexes`, `reorder`, `add_urls` | |
| **variant_overrides** | Array of `{match, sell_price, compare_at_price}` | Match by variant name substring |
| **option_edits** | Array of actions: `rename_option`, `rename_value`, `remove_value`, `remove_option` | Always full replacement, not incremental |

### Natural Language Mapping

- "3x the price" -> `{ "pricing": { "mode": "multiplier", "multiplier": 3 } }`
- "add $5" -> `{ "pricing": { "mode": "fixed_markup", "fixed_markup": 5 } }`
- "set price to $19.99" -> `{ "pricing": { "mode": "fixed_price", "fixed_price": 19.99 } }`
- "add HOT before title" -> `{ "content": { "title_prefix": "HOT - " } }`
- "keep first 5 images" -> `{ "images": { "keep_first_n": 5 } }`
- "rename Color to Style" -> `{ "option_edits": [{ "action": "rename_option", "option_name": "Color", "new_name": "Style" }] }`

Use `validate_rules` to check rules before importing -- it returns `effective_rules_snapshot` (what will be applied), `warnings` (adjustments), and `errors` (blocking issues).

## Push Safety Guards

`confirm_push_to_store` runs automatic pre-push validation.

### Blocked (push rejected)

- Sell price < cost (would lose money on every sale)
- All variants have zero stock

### Warned (push proceeds, surface to user)

- Low margin (<10%)
- Low stock (<5 units on any variant)
- Very low price (<$1)
- Extreme pricing values

Use `force_push=true` to override blocks, but only after explaining the risk to the user and getting explicit confirmation.

## SKU Remap

`dsers_sku_remap` replaces the supplier on a store product with variant-level matching.

### Two Paths

| Path | Trigger | Behavior |
|------|---------|----------|
| **Strict** | Provide `new_supplier_url` | Fetches the exact supplier, matches variants by SKU attributes |
| **Discover** | Omit `new_supplier_url` | Reverse-image searches the DSers pool, ranks candidates by multi-factor scoring, auto-picks best |

### Workflow

1. Call with `mode='preview'` (default, read-only) to see match plan and diffs
2. Review the variant mapping (swapped / kept_old / unmatched counts)
3. Call again with `mode='apply'` to persist the swap

`auto_confidence` threshold defaults to 70. Variants below this confidence are kept on old supplier.

## Push Modes

- **Single**: `job_id` + `target_store`
- **Batch**: `job_ids` (array) + `target_store`
- **Multi-store**: `job_id` + `target_stores` (array)
- **Batch + multi-store**: `job_ids` + `target_stores` -> N jobs x M stores

## Push Options

| User says | Option | Value |
|-----------|--------|-------|
| "publish" / "list it" | `publish_to_online_store` | `true` |
| "draft" / "backend only" | `publish_to_online_store` | `false` |
| "push all images" | `image_strategy` | `all_available` |
| "use store pricing rule" | `pricing_rule_behavior` | `apply_store_pricing_rule` |
| "auto sync inventory" | `auto_inventory_update` | `true` |
| "auto sync price" | `auto_price_update` | `true` |
| "use specific shipping profile" | `shipping_profile_name` | `"Profile Name"` |

## Shopify Shipping Profile

Auto-discovered. No manual GIDs needed.

- Default: picks the profile marked as default in DSers
- Specific: set `push_options.shipping_profile_name`
- `get_rule_capabilities` returns `shipping_profiles` per Shopify store
- Non-Shopify stores skip shipping profile entirely

## Error Handling

All errors follow a structured format with clear error messages and actionable guidance.

| Scenario | What to do |
|----------|------------|
| Import fails | Check URL format. Bundle URLs not supported. 1688/Alibaba require DSers account to have that source enabled. |
| "shipping profile not found" | Call `get_rule_capabilities` to check available profiles, retry with explicit `shipping_profile_name`. |
| Push returns `failed` | Check `warnings` array. Common: product deleted from import list between prepare and push. |
| `persist_failed` status | Rule update failed to save to DSers backend. Retry `dsers_product_update_rules` or re-import. Push is blocked. |
| Unknown `target_store` | Error lists available stores. Use store_ref or display_name from `get_rule_capabilities`. |
| Push blocked by safety guard | Fix pricing rules or use `force_push=true` after confirming risk with user. |

Always surface `warnings` from every response to the user. A job must be `preview_ready` before it can be pushed.

## Typical Patterns

**Quick import + push:**
```
get_rule_capabilities -> prepare_import_candidate(source_url, rules) -> confirm_push_to_store(job_id, target_store)
```

**Batch with mixed sources:**
```
get_rule_capabilities -> prepare_import_candidate(source_urls: [ae_url, 1688_url]) -> confirm_push_to_store(job_ids: [...])
```

**Update rules on existing import:**
```
dsers_product_update_rules(job_id, pricing_mode="fixed_price", pricing_fixed_price=19.99) -> get_import_preview(job_id) -> confirm_push_to_store(job_id)
```

**Browse and find products:**
```
dsers_find_product(keyword="phone case") -> prepare_import_candidate(source_url=result.import_url)
```

**Replace supplier on store product:**
```
dsers_my_products(store_id) -> dsers_sku_remap(dsers_product_id, store_id, mode="preview") -> review diffs -> dsers_sku_remap(..., mode="apply")
```

**Discover replacement supplier automatically:**
```
dsers_sku_remap(dsers_product_id, store_id, mode="preview") -> review candidates -> dsers_sku_remap(..., mode="apply")
```
