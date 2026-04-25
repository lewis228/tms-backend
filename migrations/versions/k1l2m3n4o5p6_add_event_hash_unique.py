"""ocean_container_events.event_hash + UNIQUE(team_id, container_id, event_hash)

Revision ID: k1l2m3n4o5p6
Revises: j0k1l2m3n4o5
Create Date: 2026-04-22 11:00:00.000000

변경 요지:
- ``ocean_container_events.event_hash VARCHAR(64) NOT NULL DEFAULT ''`` 추가
- 기존 row 전부 SHA-256(container_id|timestamp|description) 으로 채움 (**in migration**)
- ``UNIQUE(team_id, container_id, event_hash)`` 제약 추가
- server_default="" 제거 — NOT NULL 유지, 향후 INSERT 는 앱이 명시적으로 채움

목적:
    앱 레벨 dedup (`save_tracking_result` 의 existing_event_keys 집합) 이 이미
    동일 이벤트 재수집을 차단하지만, **동시에 같은 MBL 을 두 워커가 스크래핑**
    하는 race condition 에서는 양쪽 워커가 동일 이벤트를 INSERT 하려다
    중복 row 가 들어갈 수 있다. DB 레벨 UNIQUE 제약으로 세 번째 방어선 추가.

왜 migration 안에서 backfill 을 하는가:
    빈 문자열 default 로 컬럼만 추가한 뒤 UNIQUE 를 걸면 `event_hash=''` 가
    수백 row 에 존재하는 상태라 즉시 충돌한다. SHA-256 해시는 input 이
    (container_id, timestamp, description) 셋이 동일한 경우에만 같으므로
    이걸 먼저 채우면 실제 중복 외에는 UNIQUE 제약이 깨끗하게 통과한다.

    진짜 중복(같은 container_id + 같은 timestamp + 같은 description row 가
    2개 이상) 이 있으면 UNIQUE 생성에서 여전히 실패한다 — 그 경우엔
    `downgrade` 로 롤백 후 중복 row 를 수동 정리 (보통 is_active=False 처리)
    해야 한다.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "k1l2m3n4o5p6"
down_revision: Union[str, None] = "j0k1l2m3n4o5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1) 컬럼 추가 — 일시적으로 server_default='' 로 기존 row 를 non-null 로 채운다.
    op.add_column(
        "ocean_container_events",
        sa.Column(
            "event_hash",
            sa.String(length=64),
            nullable=False,
            server_default="",
        ),
    )

    # 2) 기존 row backfill — SHA-256(container_id|ts_epoch|description[:500])
    #
    # scraping 레포의 `_event_hash` 와 **완전히 동일한 알고리즘** 이어야 한다.
    # ts_epoch 가 NULL 이면 문자열 '0' 으로 표기 (Python 쪽과 동일).
    # description 은 NULL 이면 '' 로 치환 후 최대 500자 cut.
    #
    # MySQL 의 SHA2(string, 256) 은 hex 64자 (소문자) 반환 — Python hexdigest 와 동일.
    op.execute(
        """
        UPDATE ocean_container_events
        SET event_hash = SHA2(
            CONCAT(
                CAST(container_id AS CHAR),
                '|',
                CASE
                    WHEN timestamp IS NULL THEN '0'
                    ELSE CAST(UNIX_TIMESTAMP(timestamp) AS CHAR)
                END,
                '|',
                COALESCE(SUBSTRING(description, 1, 500), '')
            ),
            256
        )
        WHERE event_hash = '' OR event_hash IS NULL
        """
    )

    # 3) UNIQUE 제약 추가 — 이 시점엔 hash 가 모두 채워져 있으므로 진짜 중복만
    #    걸린다. 걸리면 migration 실패 → 수동 개입 필요.
    op.create_unique_constraint(
        "uq_ocean_container_events_team_container_hash",
        "ocean_container_events",
        ["team_id", "container_id", "event_hash"],
    )

    # 4) server_default 제거 — 앞으로 신규 INSERT 는 앱이 명시적으로 hash 를
    #    채운다. default 유지하면 버그가 조용히 숨을 수 있음.
    op.alter_column(
        "ocean_container_events",
        "event_hash",
        existing_type=sa.String(length=64),
        existing_nullable=False,
        server_default=None,
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_ocean_container_events_team_container_hash",
        "ocean_container_events",
        type_="unique",
    )
    op.drop_column("ocean_container_events", "event_hash")
