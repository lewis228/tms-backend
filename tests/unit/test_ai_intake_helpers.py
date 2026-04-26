# tests/unit/test_ai_intake_helpers.py
"""AIIntakeService 의 순수 헬퍼 — _strip_fences / _media_type."""
from __future__ import annotations

from ai_intake.providers.base import strip_fences, media_type


class TestStripFences:
    def test_no_fence(self):
        assert strip_fences('{"a": 1}') == '{"a": 1}'

    def test_json_fence(self):
        text = '```json\n{"a": 1}\n```'
        assert strip_fences(text) == '{"a": 1}'

    def test_plain_fence(self):
        text = '```\n{"a": 1}\n```'
        assert strip_fences(text) == '{"a": 1}'

    def test_extra_whitespace(self):
        text = '   ```json\n  {"a": 1}  \n```   '
        assert strip_fences(text) == '{"a": 1}'

    def test_multiline(self):
        text = '```json\n{\n  "a": 1,\n  "b": 2\n}\n```'
        assert '"a": 1' in strip_fences(text)


class TestMediaType:
    def test_image_passthrough(self):
        for ct in ["image/jpeg", "image/png", "image/webp", "image/gif"]:
            assert media_type(ct) == ct

    def test_uppercase_normalized(self):
        assert media_type("IMAGE/JPEG") == "image/jpeg"

    def test_heic_falls_back_to_jpeg(self):
        assert media_type("image/heic") == "image/jpeg"

    def test_pdf(self):
        assert media_type("application/pdf") == "application/pdf"

    def test_unknown_defaults_jpeg(self):
        assert media_type("application/octet-stream") == "image/jpeg"

    def test_none_or_empty(self):
        assert media_type("") == "image/jpeg"
        assert media_type(None) == "image/jpeg"
