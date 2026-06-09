# scripts/notion_design/publish.py
"""TMS 현재 설계 문서를 Notion 'TMS' 페이지 아래에 발행.

실행: PYTHONPATH=scripts/notion_design python3 scripts/notion_design/publish.py
재실행 멱등: 기존 'TMS 현재 설계' 트리를 archive 후 새로 생성.
"""
from __future__ import annotations
import notion_api as N
import content as C

PARENT_TITLE = "TMS 현재 설계 (구현 기준)"

CHILDREN = [
    ("01. 아키텍처 & 멀티테넌시 & 공통 규약", C.page_architecture),
    ("02. 도메인 카탈로그 ① 마스터 데이터", C.page_master),
    ("03. 도메인 카탈로그 ② 실행 (D/O · Container · Leg)", C.page_execution),
    ("04. 도메인 카탈로그 ③ 요율 서브시스템", C.page_rate),
    ("05. 도메인 카탈로그 ④ 정산 · 청구", C.page_settlement),
    ("06. 도메인 카탈로그 ⑤ 모바일·실시간·AI·시스템·RBAC", C.page_system),
    ("07. 상태 머신 & 파생 엔진", C.page_statemachine),
    ("08. 요율 해석 + 머니 체인 ⭐", C.page_money),
    ("09. 프론트엔드 IA", C.page_frontend),
    ("10. 마이그레이션 · 테스트 · 재설계 결정", C.page_migration),
]


def main():
    archived = N.archive_children_titled(N.TMS_PAGE_ID, "TMS 현재 설계")
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
