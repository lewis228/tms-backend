# src/vessel/CLAUDE.md — STE 분기 모듈 (TMS 검토 필요)

> **주의: 이 모듈은 STE `backend_tracking-api` 에서 그대로 분기된 코드다.**
> 선박(AIS) 위치 추적 기능으로, TMS 도메인에서 필요 여부를 검토해야 한다.
> - 필요 없다면 모듈 전체(`vessel/`) 와 관련 migration 을 삭제한다.
> - 필요하다면 STE 버전을 기반으로 TMS 도메인에 맞게 수정한다.

---

## 모듈 개요 (STE 기준)

선박 이름 → MMSI/IMO 매핑 + 주기적 실시간 위치 갱신 + WebSocket push 파이프라인.
Mock provider 로 end-to-end 작동 가능. 실운영 전환 시 `AIS_PROVIDER=marinetraffic` 으로 변경.

## 파일 구조

```
vessel/
├── model.py          # VesselModel + VesselPositionModel (전역, Team scoped 아님)
├── repository.py
├── service.py        # resolve_by_name / refresh_positions
├── router.py         # GET /api/v1/fleet/vessels
├── schemas/response.py
├── ais/
│   ├── base.py       # AisProvider Protocol
│   ├── mock.py       # 개발/테스트용 (기본값)
│   ├── marinetraffic.py  # STUB — 실구현 필요
│   └── factory.py    # settings.AIS_PROVIDER 기반 싱글턴
└── tasks/
    ├── resolve_vessel.py       # on-demand: 선박 이름 해석
    └── poll_fleet_positions.py # 주기적: MMSI 위치 일괄 갱신 + WS push
```

## 주요 설계 결정

| 결정 | 이유 |
| --- | --- |
| vessels 전역 마스터 (Team scoped 아님) | 같은 배를 여러 팀이 참조 → AIS API 비용 절감 |
| vessel_positions 1:1 (최신만) | 현재 위치 표시가 주목적 |
| Provider 추상화 (Protocol) | 업체 교체 시 도메인 코드 무수정 |
| 팀별 WS push | 타 팀 선박 위치 누출 방지 |

## TMS 전환 체크리스트

- [ ] TMS 도메인에서 vessel/AIS 기능 필요 여부 결정
- [ ] 불필요하면: `vessel/` 삭제, `models_registry.py` import 제거, `celery_app.py` beat task 제거, migration 작성
- [ ] 필요하면: TMS 도메인 맞게 수정 후 이 CLAUDE.md 업데이트
