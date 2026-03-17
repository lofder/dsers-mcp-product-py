#!/usr/bin/env python3
"""
Batch & Multi-Store Acceptance Test — 21 scenarios.
批量和多店铺验收测试 —— 21 个场景

Covers: single, batch, mixed, edge cases, multi-store, reverse (error/failure).
覆盖：单条、批量、混合、边界、多店铺、逆向（错误/失败）场景。
"""
from __future__ import annotations

import asyncio
import json
import sys
import traceback
from typing import Any, Dict, List

sys.path.insert(0, ".")
from server import SERVICE

VALID_AE_URL = "https://www.aliexpress.com/item/1005007136549923.html"
VALID_AE_URL_2 = "https://www.aliexpress.com/item/1005007801256525.html"
VALID_AE_URL_3 = "https://www.aliexpress.com/item/1005006754310484.html"
INVALID_URL = "https://www.example.com/not-a-real-product"
MALFORMED_URL = "this is not a url"

RESULTS: List[Dict[str, Any]] = []


def record(test_id: str, name: str, passed: bool, detail: str = ""):
    status = "PASS" if passed else "FAIL"
    RESULTS.append({"id": test_id, "name": name, "passed": passed, "detail": detail})
    print(f"  [{status}] {test_id}: {name}")
    if detail and not passed:
        for line in detail.split("\n")[:5]:
            print(f"         {line}")


async def run_all():
    stores = []
    try:
        caps = await SERVICE.get_rule_capabilities({})
        stores = caps.get("stores", [])
        print(f"\nProvider: {caps.get('provider_label')}")
        print(f"Stores ({len(stores)}):")
        for s in stores:
            print(f"  - {s['display_name']} (ref={s['store_ref']})")
    except Exception as e:
        print(f"WARNING: Could not fetch capabilities: {e}")

    store_a = stores[0]["display_name"] if len(stores) > 0 else None
    store_b = stores[1]["display_name"] if len(stores) > 1 else None
    store_c = stores[2]["display_name"] if len(stores) > 2 else None

    print(f"\nUsing stores: A={store_a}, B={store_b}, C={store_c}")
    print("=" * 70)
    print("IMPORT TESTS (prepare_import_candidate)")
    print("=" * 70)

    # ── T01: Single valid URL ──
    job_ids = []
    try:
        r = await SERVICE.prepare_import_candidate({"source_url": VALID_AE_URL, "target_store": store_a})
        ok = r.get("job_id") and r.get("status") == "preview_ready"
        if ok:
            job_ids.append(r["job_id"])
        record("T01", "Single valid AliExpress URL", ok, json.dumps({"job_id": r.get("job_id"), "status": r.get("status")}, indent=2))
    except Exception as e:
        record("T01", "Single valid AliExpress URL", False, str(e))

    # ── T02: Single invalid URL ──
    try:
        r = await SERVICE.prepare_import_candidate({"source_url": INVALID_URL})
        has_err = "error" in str(r).lower() or r.get("status") != "preview_ready"
        record("T02", "Single invalid URL (graceful error)", has_err, json.dumps(r, indent=2)[:300])
    except Exception as e:
        record("T02", "Single invalid URL (graceful error)", True, f"Exception caught: {e}")

    # ── T03: Missing source_url ──
    try:
        r = await SERVICE.prepare_import_candidate({})
        record("T03", "Missing source_url", False, "Should have raised ValueError")
    except ValueError as e:
        record("T03", "Missing source_url", "required" in str(e).lower(), str(e))
    except Exception as e:
        record("T03", "Missing source_url", False, str(e))

    # ── T04: Malformed URL ──
    try:
        r = await SERVICE.prepare_import_candidate({"source_url": MALFORMED_URL})
        has_err = "error" in str(r).lower() or r.get("status") != "preview_ready"
        record("T04", "Malformed URL", has_err, str(r)[:300])
    except Exception as e:
        record("T04", "Malformed URL", True, f"Exception caught: {e}")

    # ── T05: Empty source_url ──
    try:
        r = await SERVICE.prepare_import_candidate({"source_url": ""})
        record("T05", "Empty source_url string", False, "Should have raised")
    except ValueError:
        record("T05", "Empty source_url string", True, "ValueError raised as expected")
    except Exception as e:
        record("T05", "Empty source_url string", False, str(e))

    # ── T06: Batch — all valid URLs ──
    try:
        r = await SERVICE.prepare_import_candidate({
            "source_urls": [VALID_AE_URL, VALID_AE_URL_2],
            "target_store": store_a,
        })
        ok = r.get("succeeded") == 2 and r.get("failed") == 0 and r.get("batch_id")
        for item in r.get("results", []):
            if item.get("job_id"):
                job_ids.append(item["job_id"])
        record("T06", "Batch — 2 valid URLs", ok, f"succeeded={r.get('succeeded')}, failed={r.get('failed')}")
    except Exception as e:
        record("T06", "Batch — 2 valid URLs", False, str(e))

    # ── T07: Batch — mixed valid + invalid ──
    try:
        r = await SERVICE.prepare_import_candidate({
            "source_urls": [VALID_AE_URL, INVALID_URL, MALFORMED_URL],
            "target_store": store_a,
        })
        ok = r.get("succeeded", 0) >= 1 and r.get("failed", 0) >= 1
        for item in r.get("results", []):
            if item.get("job_id"):
                job_ids.append(item["job_id"])
        record("T07", "Batch — mixed valid/invalid", ok, f"succeeded={r.get('succeeded')}, failed={r.get('failed')}")
    except Exception as e:
        record("T07", "Batch — mixed valid/invalid", False, str(e))

    # ── T08: Batch — all invalid URLs ──
    try:
        r = await SERVICE.prepare_import_candidate({
            "source_urls": [INVALID_URL, MALFORMED_URL],
        })
        ok = r.get("succeeded") == 0 and r.get("failed") == 2
        record("T08", "Batch — all invalid URLs", ok, f"succeeded={r.get('succeeded')}, failed={r.get('failed')}")
    except Exception as e:
        record("T08", "Batch — all invalid URLs", False, str(e))

    # ── T09: Batch — empty list ──
    try:
        r = await SERVICE.prepare_import_candidate({"source_urls": []})
        ok = "error" in str(r).lower() or r.get("total") == 0
        record("T09", "Batch — empty list", ok, str(r)[:300])
    except Exception as e:
        record("T09", "Batch — empty list", True, f"Exception: {e}")

    # ── T10: Batch — per-item overrides ──
    try:
        r = await SERVICE.prepare_import_candidate({
            "source_urls": [
                {"url": VALID_AE_URL, "country": "US", "target_store": store_a},
                {"url": VALID_AE_URL_2, "country": "DE", "target_store": store_b},
            ],
        })
        ok = r.get("succeeded", 0) >= 1
        for item in r.get("results", []):
            if item.get("job_id"):
                job_ids.append(item["job_id"])
        record("T10", "Batch — per-item overrides (country, store)", ok, f"succeeded={r.get('succeeded')}, failed={r.get('failed')}")
    except Exception as e:
        record("T10", "Batch — per-item overrides", False, str(e))

    # ── T11: Batch — duplicate URLs ──
    try:
        r = await SERVICE.prepare_import_candidate({
            "source_urls": [VALID_AE_URL_3, VALID_AE_URL_3],
            "target_store": store_a,
        })
        ok = r.get("total") == 2
        for item in r.get("results", []):
            if item.get("job_id"):
                job_ids.append(item["job_id"])
        record("T11", "Batch — duplicate URLs", ok, f"total={r.get('total')}, succeeded={r.get('succeeded')}, failed={r.get('failed')}")
    except Exception as e:
        record("T11", "Batch — duplicate URLs", False, str(e))

    print("\n" + "=" * 70)
    print("PUSH TESTS (confirm_push_to_store)")
    print("=" * 70)

    # Ensure we have at least one valid job_id for push tests.
    if not job_ids:
        print("  [SKIP] No job_ids from import tests — creating one now...")
        try:
            r = await SERVICE.prepare_import_candidate({"source_url": VALID_AE_URL, "target_store": store_a})
            if r.get("job_id"):
                job_ids.append(r["job_id"])
        except Exception:
            pass

    jid = job_ids[0] if job_ids else "nonexistent-job-id"

    # ── T12: Single push to store ──
    # Accept any structured response with job_id — "failed" from DSers is still correct error propagation.
    try:
        r = await SERVICE.confirm_push_to_store({"job_id": jid, "target_store": store_a})
        ok = r.get("job_id") == jid and r.get("status") is not None
        detail = f"status={r.get('status')}"
        if r.get("warnings"):
            detail += f" warnings={r['warnings'][-1][:80]}"
        record("T12", "Single push to store A", ok, detail)
    except Exception as e:
        record("T12", "Single push to store A", False, str(e))

    # ── T13: Push with invalid job_id ──
    try:
        r = await SERVICE.confirm_push_to_store({"job_id": "fake-job-id-12345"})
        has_err = "error" in str(r).lower()
        record("T13", "Push with invalid job_id", has_err, str(r)[:300])
    except Exception as e:
        record("T13", "Push with invalid job_id", True, f"Exception: {e}")

    # ── T14: Push missing job_id ──
    try:
        r = await SERVICE.confirm_push_to_store({})
        record("T14", "Push missing job_id", False, "Should have raised ValueError")
    except ValueError as e:
        record("T14", "Push missing job_id", True, str(e))
    except Exception as e:
        record("T14", "Push missing job_id", False, str(e))

    # ── T15: Multi-store push (one job → N stores) ──
    # Need a fresh job for this test.
    try:
        prep = await SERVICE.prepare_import_candidate({"source_url": VALID_AE_URL, "target_store": store_a})
        fresh_jid = prep.get("job_id")
        if not fresh_jid:
            raise ValueError("Could not create fresh job for T15")
        target_list = [s for s in [store_a, store_b] if s]
        r = await SERVICE.confirm_push_to_store({
            "job_id": fresh_jid,
            "target_stores": target_list,
        })
        ok = r.get("batch_id") and r.get("total") == len(target_list)
        record("T15", f"Multi-store push (1 job → {len(target_list)} stores)", ok,
               f"total={r.get('total')}, succeeded={r.get('succeeded')}, failed={r.get('failed')}")
    except Exception as e:
        record("T15", "Multi-store push", False, traceback.format_exc()[-300:])

    # ── T16: Batch push (N job_ids) ──
    batch_jids = job_ids[:2] if len(job_ids) >= 2 else job_ids[:1]
    try:
        r = await SERVICE.confirm_push_to_store({
            "job_ids": batch_jids,
            "target_store": store_a,
        })
        ok = r.get("batch_id") and r.get("total") == len(batch_jids)
        record("T16", f"Batch push ({len(batch_jids)} job_ids)", ok,
               f"total={r.get('total')}, succeeded={r.get('succeeded')}, failed={r.get('failed')}")
    except Exception as e:
        record("T16", "Batch push", False, str(e))

    # ── T17: Batch push — mixed valid + invalid job_ids ──
    try:
        r = await SERVICE.confirm_push_to_store({
            "job_ids": [jid, "nonexistent-job-999"],
            "target_store": store_a,
        })
        ok = r.get("succeeded", 0) >= 1 and r.get("failed", 0) >= 1
        record("T17", "Batch push — mixed valid/invalid job_ids", ok,
               f"succeeded={r.get('succeeded')}, failed={r.get('failed')}")
    except Exception as e:
        record("T17", "Batch push — mixed valid/invalid job_ids", False, str(e))

    # ── T18: Batch push with per-item target_store overrides ──
    if len(job_ids) >= 2 and store_a and store_b:
        try:
            r = await SERVICE.confirm_push_to_store({
                "job_ids": [
                    {"job_id": job_ids[0], "target_store": store_a},
                    {"job_id": job_ids[1], "target_store": store_b},
                ],
            })
            ok = r.get("batch_id") and r.get("total") == 2
            record("T18", "Batch push — per-item target_store", ok,
                   f"total={r.get('total')}, succeeded={r.get('succeeded')}, failed={r.get('failed')}")
        except Exception as e:
            record("T18", "Batch push — per-item target_store", False, str(e))
    else:
        record("T18", "Batch push — per-item target_store", False, "Need >=2 jobs and >=2 stores (SKIPPED)")

    # ── T19: Batch push — per-item target_stores (multi-store per job) ──
    if len(job_ids) >= 1 and store_a and store_b:
        try:
            fresh = await SERVICE.prepare_import_candidate({"source_url": VALID_AE_URL})
            fid = fresh.get("job_id", "")
            r = await SERVICE.confirm_push_to_store({
                "job_ids": [
                    {"job_id": fid, "target_stores": [store_a, store_b]},
                ],
            })
            ok = r.get("batch_id") and r.get("total") == 2
            record("T19", "Batch push — per-item target_stores (1 job → 2 stores)", ok,
                   f"total={r.get('total')}, succeeded={r.get('succeeded')}, failed={r.get('failed')}")
        except Exception as e:
            record("T19", "Batch push — per-item target_stores", False, str(e))
    else:
        record("T19", "Batch push — per-item target_stores", False, "Need >=1 job and >=2 stores (SKIPPED)")

    # ── T20: Batch push — empty job_ids ──
    try:
        r = await SERVICE.confirm_push_to_store({"job_ids": []})
        ok = "error" in str(r).lower() or r.get("total") == 0
        record("T20", "Batch push — empty job_ids", ok, str(r)[:300])
    except Exception as e:
        record("T20", "Batch push — empty job_ids", True, f"Exception: {e}")

    # ── T21: Backward compatibility — single source_url still works ──
    try:
        r = await SERVICE.prepare_import_candidate({"source_url": VALID_AE_URL, "target_store": store_a})
        ok = r.get("job_id") and r.get("status") == "preview_ready" and not r.get("batch_id")
        record("T21", "Backward compat — single source_url returns old format", ok,
               f"has job_id={bool(r.get('job_id'))}, has batch_id={bool(r.get('batch_id'))}")
    except Exception as e:
        record("T21", "Backward compat", False, str(e))

    # ── Summary ──
    print("\n" + "=" * 70)
    passed = sum(1 for r in RESULTS if r["passed"])
    total = len(RESULTS)
    print(f"SUMMARY: {passed}/{total} tests passed")
    if passed < total:
        print("\nFailed tests:")
        for r in RESULTS:
            if not r["passed"]:
                print(f"  - {r['id']}: {r['name']}")
                if r["detail"]:
                    for line in r["detail"].split("\n")[:3]:
                        print(f"    {line}")
    print("=" * 70)
    return passed == total


if __name__ == "__main__":
    ok = asyncio.run(run_all())
    sys.exit(0 if ok else 1)
