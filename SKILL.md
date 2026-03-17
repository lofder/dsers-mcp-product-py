---
name: dsers-mcp-product
description: Automate DSers product import from AliExpress/Alibaba/1688 to Shopify/Wix/WooCommerce. Use when the user wants to import, edit, price, or push dropshipping products to their store via DSers.
---

# DSers MCP Product

## Workflow

Always follow this order:

1. `get_rule_capabilities` — discover stores, shipping profiles, supported rules
2. `prepare_import_candidate` — import from URL(s), apply rules, get preview
3. `get_import_preview` — (optional) reload a saved preview
4. `set_product_visibility` — (optional) toggle `backend_only` / `sell_immediately`
5. `confirm_push_to_store` — push to store(s)
6. `get_job_status` — verify push result

Step 1 is required before any import — it returns the store list and available shipping profiles.

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

- **pricing**: `markup_percent`, `fixed_markup`, `multiplier`, `compare_at_percent`
- **content**: `title_prefix`, `title_suffix`, `title_override`, `description_override_html`
- **images**: `keep_first_n`, `drop_indexes`

Map natural language to rules:
- "mark up 50%" → `{ "pricing": { "markup_percent": 50 } }`
- "3x the price" → `{ "pricing": { "multiplier": 3 } }`
- "add HOT before title" → `{ "content": { "title_prefix": "HOT - " } }`
- "keep first 5 images" → `{ "images": { "keep_first_n": 5 } }`

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

## Error Handling

- **Import fails**: check URL format. AliExpress bundle URLs are not supported. 1688/Alibaba require the DSers account to have that source enabled.
- **"shipping profile not found"**: should not happen (auto-discovered). If it does, call `get_rule_capabilities` to check available profiles, then retry with explicit `shipping_profile_name`.
- **Push returns `failed`**: check `warnings` array for details. Common cause: product was deleted from import list between prepare and push.
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
