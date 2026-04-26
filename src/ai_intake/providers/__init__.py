"""AI Intake provider 어댑터.

각 provider 는 동일한 응답 스키마를 반환:
    {"fields": dict[str, Any], "confidence": float}

router/service 는 어떤 provider 가 동작하는지 모르고 호출 가능.
환경변수 AI_INTAKE_PROVIDER 로 선택.
"""
from ai_intake.providers.base import IntakeProvider, ExtractResult

__all__ = ["IntakeProvider", "ExtractResult"]
