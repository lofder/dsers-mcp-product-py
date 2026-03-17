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
    os.environ.setdefault("IMPORT_PROVIDER_MODULE", "dsers_provider.provider")
    os.environ.setdefault("IMPORT_MCP_STATE_DIR", str(Path(__file__).resolve().parent / ".state-smoke"))
    service = ImportFlowService(load_provider(), FileJobStore(Path(os.environ["IMPORT_MCP_STATE_DIR"])))

    capabilities = await service.get_rule_capabilities({})
    output = {"capabilities": capabilities}

    sample_url = os.getenv("SAMPLE_IMPORT_URL", "").strip()
    sample_rules = {
        "pricing": {"mode": "multiplier", "multiplier": 1.8},
        "content": {"title_suffix": " | Test"},
        "images": {"keep_first_n": 3},
    }
    output["validated_rules"] = await service.validate_rules({"rules": sample_rules})
    if sample_url:
        prepared = await service.prepare_import_candidate(
            {
                "source_url": sample_url,
                "country": os.getenv("SAMPLE_IMPORT_COUNTRY", "US"),
                "visibility_mode": "backend_only",
                "rules": sample_rules,
            }
        )
        output["prepared"] = prepared
        if os.getenv("SAMPLE_CONFIRM_PUSH", "").strip().lower() in {"1", "true", "yes"}:
            output["confirmed"] = await service.confirm_push_to_store(
                {
                    "job_id": prepared["job_id"],
                    "push_options": {
                        "publish_to_online_store": False,
                        "only_push_specifications": True,
                        "image_strategy": "selected_only",
                    },
                }
            )

    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
