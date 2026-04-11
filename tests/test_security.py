"""Tests for security utilities."""
import pytest
from dsers_mcp_product.security import (
    validate_job_id,
    contains_dangerous_html,
    sanitize_html,
    sanitize_error,
    validate_url,
)


class TestValidateJobId:
    def test_valid_uuid(self):
        assert validate_job_id("550e8400-e29b-41d4-a716-446655440000") == "550e8400-e29b-41d4-a716-446655440000"

    def test_valid_batch_id(self):
        assert validate_job_id("batch-abc123def456") == "batch-abc123def456"

    def test_path_traversal_rejected(self):
        with pytest.raises(ValueError, match="Invalid job_id format"):
            validate_job_id("../../etc/passwd")

    def test_empty_rejected(self):
        with pytest.raises(ValueError):
            validate_job_id("")

    def test_arbitrary_string_rejected(self):
        with pytest.raises(ValueError):
            validate_job_id("not-a-uuid-at-all")


class TestDangerousHtml:
    def test_script_tag(self):
        assert contains_dangerous_html('<script>alert("xss")</script>') is True

    def test_iframe_tag(self):
        assert contains_dangerous_html('<iframe src="evil.com"></iframe>') is True

    def test_onclick_handler(self):
        assert contains_dangerous_html('<div onclick="steal()">Click</div>') is True

    def test_javascript_url(self):
        assert contains_dangerous_html('<a href="javascript:alert(1)">link</a>') is True

    def test_safe_html(self):
        assert contains_dangerous_html("<p>Safe <strong>content</strong></p>") is False

    def test_sanitize_removes_script(self):
        result = sanitize_html('<p>OK</p><script>bad()</script>')
        assert "<script>" not in result
        assert "<p>OK</p>" in result

    def test_sanitize_removes_onclick(self):
        result = sanitize_html('<div onclick="x()">text</div>')
        assert "onclick" not in result


class TestSanitizeError:
    def test_redacts_tokens(self):
        result = sanitize_error("token=abc123secretvalue some error")
        assert "abc123secretvalue" not in result
        assert "REDACTED" in result

    def test_redacts_session_ids(self):
        result = sanitize_error("session_id=abc12345678 failed")
        assert "abc12345678" not in result

    def test_truncates_long_messages(self):
        result = sanitize_error("x" * 1000)
        assert len(result) <= 500


class TestValidateUrl:
    def test_http_passes(self):
        assert validate_url("https://example.com") == "https://example.com"

    def test_file_protocol_blocked(self):
        with pytest.raises(ValueError, match="Unsafe URL"):
            validate_url("file:///etc/passwd")

    def test_data_protocol_blocked(self):
        with pytest.raises(ValueError, match="Unsafe URL"):
            validate_url("data:text/html,<script>alert(1)</script>")
