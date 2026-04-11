"""
Structured error mapping — converts raw DSers errors into agent-friendly format.
"""

from typing import Any
from .security import sanitize_error

DSERS_REASON_MAP: dict[str, dict[str, str]] = {
    "SELLER_NOT_FOUND": {
        "summary": "Product not found",
        "cause": "The supplier product ID does not exist or has been removed from the platform.",
        "action": "Verify the product URL is correct and the product is still available.",
    },
    "PRODUCT_EXIST": {
        "summary": "Product already imported",
        "cause": "This product is already in the DSers import list.",
        "action": "Use dsers_import_list to find the existing import, or delete it first with dsers_product_delete.",
    },
    "LIMIT_EXCEEDED": {
        "summary": "Import limit reached",
        "cause": "The DSers plan limit for imported products has been reached.",
        "action": "Delete unused products from the import list, or upgrade the DSers plan.",
    },
    "AUTH_REQUIRED": {
        "summary": "Authentication required",
        "cause": "DSers session has expired or credentials are invalid.",
        "action": "Re-authenticate with DSers.",
    },
}


def format_error_for_agent(err: Any) -> str:
    """Format an exception into an agent-friendly error string."""
    msg = str(err) if not isinstance(err, str) else err
    safe = sanitize_error(msg)

    for reason, mapped in DSERS_REASON_MAP.items():
        if reason.lower() in safe.lower():
            return f"Error: {mapped['summary']}\nCause: {mapped['cause']}\nAction: {mapped['action']}"

    return f"Error: {safe[:200]}"
