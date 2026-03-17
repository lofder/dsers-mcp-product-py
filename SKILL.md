---
name: dsers-mcp-product-py
description: Automate DSers product import from AliExpress/Alibaba/1688 to Shopify/Wix/WooCommerce. Use when the user wants to import, edit, price, or push dropshipping products to their store via DSers. (Python version — TypeScript version is primary)
---

# DSers MCP Product (Python)

## Workflow

Always follow this order:

1. `get_rule_capabilities` — discover stores, shipping profiles, supported rules
2. `validate_rules` — (optional) dry-run rule validation before importing
3. `prepare_import_candidate` — import from URL(s), apply rules, get preview with job_id
4. `get_import_preview` — (optional) reload a saved preview
5. `set_product_visibility` — (optional) toggle `backend_only` / `sell_immediately`
6. `confirm_push_to_store` — push to store(s)
7. `get_job_status` — verify push result

Step 1 is required before any import — it returns the store list, shipping profiles, and rule constraints.

## Key Decisions

### Single vs Batch

- User gives **one URL** → use `source_url` in `prepare_import_candidate`
- User gives **multiple URLs** → use `source_urls` (array). Each URL is processed independently; failures don't block others.
- Mixed sources (AliExpress + 1688 + Alibaba) work in the same batch call.

### Push Modes

- **Single**: `job_id` + `target_store`
- **Batch**: `job_ids` (array) + `target_store`
- **Multi-store**: `job_id` + `target_stores` (array)
- **Batch + multi-store**: `job_ids` + `target_stores` → N jobs x M stores

### Shopify Shipping Profile

The system auto-discovers delivery profiles for Shopify stores. No manual GIDs needed.

- Default behavior: picks the profile marked as default in DSers
- To use a specific profile: set `push_options.shipping_profile_name` (e.g. `"DSers Shipping Profile"`)
- `get_rule_capabilities` returns `shipping_profiles` per Shopify store — show these to the user if they ask

Non-Shopify stores (Wix, WooCommerce) skip shipping profile entirely.

### Rules

Rules are applied at `prepare_import_candidate` time and frozen into the job. They do NOT change at push time.

- **pricing**: `mode` (provider_default, multiplier, fixed_markup), `multiplier`, `fixed_markup`, `round_digits`
- **content**: `title_prefix`, `title_suffix`, `title_override`, `description_override_html`, `description_append_html`, `tags_add`
- **images**: `keep_first_n`, `drop_indexes`

Map natural language to rules:
- "3x the price" → `{ "pricing": { "mode": "multiplier", "multiplier": 3 } }`
- "add $5" → `{ "pricing": { "mode": "fixed_markup", "fixed_markup": 5 } }`
- "add HOT before title" → `{ "content": { "title_prefix": "HOT - " } }`
- "keep first 5 images" → `{ "images": { "keep_first_n": 5 } }`

Use `validate_rules` to check rules before importing — it returns `effective_rules_snapshot` (what will be applied) and `errors` (blocking issues).

### Push Options

Map user intent to `push_options`:

| User says | Option | Value |
|-----------|--------|-------|
| "publish" / "list it" | `publish_to_online_store` | `true` |
| "draft" / "backend only" | `publish_to_online_store` | `false` |
| "push all images" | `image_strategy` | `all_available` |
| "use store pricing rule" | `pricing_rule_behavior` | `apply_store_pricing_rule` |
| "auto sync inventory" | `auto_inventory_update` | `true` |
| "auto sync price" | `auto_price_update` | `true` |
| "use specific shipping profile" | `shipping_profile_name` | `"Profile Name"` |

## Return Fields

### get_rule_capabilities

- `stores`: array of `{store_ref, display_name, platform, domain, shipping_profiles}`
- `rule_families`: `{pricing, content, images, visibility}` with supported keys
- `push_options`: supported keys, valid enum values, available sales channels
- `source_support`: supported platforms (aliexpress, alibaba, 1688)

### prepare_import_candidate / get_import_preview

- `job_id`: unique identifier — needed for all subsequent operations
- `status`: `preview_ready`
- `title_before` / `title_after`: title before and after rule application
- `price_range_before` / `price_range_after`: `{min, max}` price ranges
- `images_before` / `images_after`: image count before and after
- `variant_count`: total variants
- `variant_preview`: first 5 variants with `{title, supplier_price, offer_price, sku}`
- `warnings`: array — always surface to user

### confirm_push_to_store

- `job_id`, `status`: job state after push
- `target_store`: resolved store name
- `visibility_applied`: actual visibility (backend_only or sell_immediately)
- `push_options_applied`: final push options used
- `warnings`: array — always surface to user

### get_job_status

- `status`: `preview_ready` → `push_requested` → `completed` or `failed`
- `has_push_result`: boolean — true after push attempt

## Error Handling

- **Import fails**: check URL format. AliExpress bundle URLs are not supported. 1688/Alibaba require the DSers account to have that source enabled.
- **"shipping profile not found"**: should not happen (auto-discovered). If it does, call `get_rule_capabilities` to check available profiles, then retry with explicit `shipping_profile_name`.
- **Push returns `failed`**: check `warnings` array for details. Common cause: product was deleted from import list between prepare and push.
- **Unknown target_store**: the error message lists available stores. Use store_ref or display_name from get_rule_capabilities.
- Always surface `warnings` from every response to the user.
- A job must be `preview_ready` before it can be pushed.

## Typical Patterns

**Quick import + push:**
```
get_rule_capabilities → prepare_import_candidate(source_url, rules) → confirm_push_to_store(job_id, target_store)
```

**Batch with mixed sources:**
```
get_rule_capabilities → prepare_import_candidate(source_urls: [ae_url, 1688_url, ...]) → confirm_push_to_store(job_ids: [...])
```

**Preview before push:**
```
get_rule_capabilities → prepare_import_candidate(...) → show draft to user → user confirms → confirm_push_to_store(...)
```

**Validate rules first:**
```
get_rule_capabilities → validate_rules(rules: {...}) → check errors → prepare_import_candidate(source_url, rules: same rules)
```
