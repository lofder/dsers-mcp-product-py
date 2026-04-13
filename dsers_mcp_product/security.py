"""
Security utilities — input validation, HTML sanitization, error scrubbing.
"""

import re

_UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE)
_BATCH_ID_RE = re.compile(r"^batch-[0-9a-f]{1,36}$", re.IGNORECASE)


def validate_job_id(job_id: str) -> str:
    """Validate job_id is a UUID or batch ID. Prevents path traversal."""
    if _UUID_RE.match(job_id) or _BATCH_ID_RE.match(job_id):
        return job_id
    raise ValueError(f'Invalid job_id format: expected UUID, got "{job_id[:40]}"')


def contains_dangerous_html(html: str) -> bool:
    """Detect script injection patterns in HTML content."""
    if re.search(r"<\s*(script|iframe|object|embed|form)\b", html, re.IGNORECASE):
        return True
    if re.search(r"\bon[a-z]+\s*=", html, re.IGNORECASE):
        return True
    if re.search(r"(?:href|src|action)\s*=\s*[\"']?\s*javascript:", html, re.IGNORECASE):
        return True
    return False


def sanitize_html(html: str) -> str:
    """Strip dangerous tags and attributes from HTML."""
    s = html
    s = re.sub(r"<\s*script\b[^>]*>[\s\S]*?<\s*/\s*script\s*>", "", s, flags=re.IGNORECASE)
    s = re.sub(r"<\s*iframe\b[^>]*>[\s\S]*?<\s*/\s*iframe\s*>", "", s, flags=re.IGNORECASE)
    s = re.sub(r"<\s*object\b[^>]*>[\s\S]*?<\s*/\s*object\s*>", "", s, flags=re.IGNORECASE)
    s = re.sub(r"<\s*embed\b[^>]*\/?>", "", s, flags=re.IGNORECASE)
    s = re.sub(r"<\s*form\b[^>]*>[\s\S]*?<\s*/\s*form\s*>", "", s, flags=re.IGNORECASE)
    s = re.sub(r"""\s+on[a-z]+\s*=\s*(?:"[^"]*"|'[^']*'|[^\s>]*)""", "", s, flags=re.IGNORECASE)
    s = re.sub(r"""((?:href|src|action)\s*=\s*["']?\s*)javascript:[^"'\s>]*""", r"\1#", s, flags=re.IGNORECASE)
    return s


_SENSITIVE_RE = re.compile(
    r"(?:token|key|secret|password|authorization)[=:]\s*[\"']?[^\s\"',;]{4,}",
    re.IGNORECASE,
)
_SESSION_RE = re.compile(
    r"(?:session[_-]?id|state)\s*[=:]\s*[\"']?[a-zA-Z0-9_-]{8,}",
    re.IGNORECASE,
)


def sanitize_error(msg: str) -> str:
    """Remove tokens, keys, and session IDs from error messages."""
    s = _SENSITIVE_RE.sub("[REDACTED]", msg)
    s = _SESSION_RE.sub("[SESSION_REDACTED]", s)
    return s[:500]


def validate_url(url: str) -> str:
    """Validate URL scheme (whitelist http/https) and block private IPs."""
    import ipaddress
    from urllib.parse import urlparse

    stripped = url.strip()
    lower = stripped.lower()
    if not (lower.startswith("http://") or lower.startswith("https://")):
        raise ValueError(f"Only http:// and https:// URLs are allowed, got: {stripped[:30]}")
    # Block private / loopback / link-local IPs to prevent SSRF
    try:
        host = urlparse(stripped).hostname
        if host:
            try:
                addr = ipaddress.ip_address(host)
            except ValueError:
                pass  # hostname, not IP literal — OK
            else:
                if addr.is_private or addr.is_loopback or addr.is_link_local:
                    raise ValueError(f"Private/loopback IP not allowed: {host}")
    except ValueError:
        raise  # re-raise validation errors
    except Exception:
        pass  # urlparse failures — let the URL through
    return stripped
