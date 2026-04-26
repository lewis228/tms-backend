# src/common/schemas/base.py
from __future__ import annotations
from typing import Any
from pydantic import BaseModel, ConfigDict, model_serializer
from pydantic.alias_generators import to_camel


# ─────────────────────────────────────────────
# 요청/응답 베이스
# ─────────────────────────────────────────────
class RequestSchema(BaseModel):
    """
    클라이언트 → 서버 요청 바디의 공통 베이스.
    """
    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
        validate_assignment=False,
        alias_generator=to_camel,   
        populate_by_name=True,     
    )


class ResponseSchema(BaseModel):
    """
    서버 → 클라이언트 응답 바디의 공통 베이스.
    - ORM 객체를 model_validate로 바로 변환 가능(from_attributes=True)
    - 여분 필드는 무시
    - 직렬화 시 snake_case → camelCase 자동 변환 (alias_generator)
    - datetime은 UTC + Z 접미사로 직렬화
    """
    model_config = ConfigDict(
        from_attributes=True,
        extra="ignore",
        validate_assignment=False,
        alias_generator=to_camel,
        populate_by_name=True,
    )

    @model_serializer(mode='wrap')
    def _serialize_with_utc_datetime(self, handler) -> dict[str, Any]:
        """직렬화 — camelCase alias 적용 + datetime UTC+Z 접미사."""
        result = handler(self)
        if isinstance(result, dict):
            result = self._apply_alias(result)
        return self._add_z_suffix(result)

    @classmethod
    def _apply_alias(cls, data: dict[str, Any]) -> dict[str, Any]:
        """필드명을 alias 로 매핑 (alias_generator=to_camel 결과 사용)."""
        out: dict[str, Any] = {}
        for k, v in data.items():
            field = cls.model_fields.get(k)
            alias = field.alias if (field and field.alias) else k
            out[alias] = v
        return out

    @staticmethod
    def _add_z_suffix(obj: Any) -> Any:
        """재귀적으로 datetime 문자열에 Z 접미사 추가"""
        if isinstance(obj, dict):
            return {k: ResponseSchema._add_z_suffix(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [ResponseSchema._add_z_suffix(item) for item in obj]
        elif isinstance(obj, str):
            # ISO 8601 datetime 형식인지 확인
            if len(obj) >= 19 and obj[4:5] == '-' and obj[7:8] == '-' and obj[10:11] == 'T':
                if not obj.endswith('Z') and '+' not in obj:
                    return f"{obj}Z"
        return obj