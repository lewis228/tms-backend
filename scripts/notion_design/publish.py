# scripts/notion_design/publish.py
"""TMS 시스템 로직 설명서를 Notion 'TMS' 페이지 아래에 발행.

실행: PYTHONPATH=scripts/notion_design python3 scripts/notion_design/publish.py
재실행 멱등: 기존 'TMS 시스템 로직 설명서' 트리를 archive 후 새로 생성.

문서 원칙: 테이블 나열 X. 흐름(이야기) + 숫자 예시 + mermaid 다이어그램. 전 코드 로직 커버.
"""
from __future__ import annotations
import notion_api as N
import content as C

PARENT_TITLE = "TMS 시스템 로직 설명서"

CHILDREN = [
    ("01. 시스템 개요 · 멀티테넌시 · 공통 규약", C.page_architecture),
    ("02. 마스터 데이터 — 운송의 재료", C.page_master),
    ("03. 1단계 — 운송 의뢰(D/O)가 들어온다", C.page_do_intake),
    ("04. 2단계 — 컨테이너 · 정차점 · work_state", C.page_container),
    ("05. 3단계 — Leg(운송 구간) 자동 생성", C.page_leg_gen),
    ("06. 4단계 — 배차 (기사 할당 · 자동 파생 · 스트리트턴)", C.page_dispatch),
    ("07. 5단계 — 운행 (상태머신 · 빠꾸 · 모바일)", C.page_runtime),
    ("08. 요율 — 얼마를 줄지 정하는 4가지 방식 ⭐", C.page_rate),
    ("09. 6단계 — 정산: leg 단위로 기사에게 지급 ⭐", C.page_settlement),
    ("10. 7단계 — 청구: 고객 인보이스 + 마진", C.page_invoice),
    ("11. 실시간 · 알림 · 감사 · 분석", C.page_realtime),
    ("12. 모바일 앱 백엔드 (BFF)", C.page_mobile),
    ("13. 인증 · 권한 · API · 파일", C.page_authz),
    ("14. 상태 머신 한눈에 (다이어그램 모음)", C.page_statemachines),
    ("15. 개선 제안 — 더 채우면 좋은 것", C.page_improvements),
]


def main():
    archived = N.archive_children_titled(N.TMS_PAGE_ID, PARENT_TITLE)
    print(f"archived old: {archived}")
    parent = N.create_page(N.TMS_PAGE_ID, PARENT_TITLE, C.page_overview())
    pid = parent["id"]
    print(f"PARENT: {parent['url']}")
    for title, builder in CHILDREN:
        page = N.create_page(pid, title, builder())
        print(f"  ✓ {title}  ->  {page['url']}")
    print("DONE")


if __name__ == "__main__":
    main()
