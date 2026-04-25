"""AIS provider 선택 팩토리.

설정 (`settings.AIS_PROVIDER`) 에 따라 provider 인스턴스를 반환.
service / task 는 이 함수만 호출 — 구현체를 직접 import 하지 않는다.

지원 값:
  - `"mock"`     (기본값, 개발)
  - `"marinetraffic"` (운영 - 계정/키 필요)
  - (향후) `"vesselfinder"`, `"spire"` ...

환경 예:
    AIS_PROVIDER=mock           # 로컬 dev
    AIS_PROVIDER=marinetraffic  # staging/prod
    AIS_API_KEY=xxxxx
"""

from __future__ import annotations

from functools import lru_cache

from common.const.settings import settings
from vessel.ais.base import AisProvider
from vessel.ais.marinetraffic import MarineTrafficProvider
from vessel.ais.mock import MockAisProvider


@lru_cache(maxsize=1)
def get_ais_provider() -> AisProvider:
    """설정에서 읽어 적합한 provider 싱글턴 반환.

    lru_cache 로 프로세스당 1개만 유지. 설정 바꾸려면 워커/앱 재시작.
    """
    name = (getattr(settings, "AIS_PROVIDER", None) or "mock").lower()
    if name == "marinetraffic":
        api_key = getattr(settings, "AIS_API_KEY", None) or ""
        return MarineTrafficProvider(api_key=api_key)
    # 기본 fallback. 실제 AIS 연결 안 된 환경에서 task 가 죽지 않게 mock.
    return MockAisProvider()
