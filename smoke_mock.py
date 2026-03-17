#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

from dsers_mcp_product.job_store import FileJobStore
from dsers_mcp_product.provider import load_provider
from dsers_mcp_product.service import ImportFlowService


async def main() -> None:
    os.environ.setdefault("IMPORT_PROVIDER_MODULE", "dsers_mcp_product.mock_provider")
    os.environ.setdefault("IMPORT_MCP_STATE_DIR", str(Path(__file__).resolve().parent / ".state-smoke"))

    service = ImportFlowService(load_provider(), FileJobStore(Path(os.environ["IMPORT_MCP_STATE_DIR"])))

    capabilities = await service.get_rule_capabilities({})
    validated_rules = await service.validate_rules(
        {
            "target_store": "mock-store-1",
            "rules": {
                "pricing": {"mode": "multiplier", "multiplier": 2},
                "content": {
                    "title_suffix": " | Curated",
                    "tags_add": ["prepared"],
                },
                "images": {"keep_first_n": 2},
            },
        }
    )
    prepared = await service.prepare_import_candidate(
        {
            "source_url": "https://www.aliexpress.com/item/mock-item.html",
            "country": "US",
            "target_store": "mock-store-1",
            "visibility_mode": "backend_only",
            "rules": {
                "pricing": {"mode": "multiplier", "multiplier": 2},
                "content": {
                    "title_suffix": " | Curated",
                    "tags_add": ["prepared"],
                },
                "images": {"keep_first_n": 2},
            },
        }
    )
    confirmed = await service.confirm_push_to_store(
        {
            "job_id": prepared["job_id"],
            "push_options": {
                "publish_to_online_store": False,
                "only_push_specifications": True,
                "image_strategy": "selected_only",
            },
        }
    )

    print(
        json.dumps(
            {
                "capabilities": capabilities,
                "validated_rules": validated_rules,
                "prepared": prepared,
                "confirmed": confirmed,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
