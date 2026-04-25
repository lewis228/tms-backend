"""carriers 마스터 테이블 추가 + ocean_shipments.carrier varchar → carrier_id FK

Revision ID: g7h8i9j0k1l2
Revises: f6g7h8i9j0k1
Create Date: 2026-04-21 09:00:00.000000

변경 요지:
- ``carriers`` 전역(non-team-scoped) 테이블 생성 + 초기 선사 목록 seed (SCAC 기준).
- ``ocean_shipments`` 에 ``carrier_id`` FK 추가 (nullable).
- 기존 ``ocean_shipments.carrier`` VARCHAR 값을 carrier 이름/SCAC 매칭으로
  ``carrier_id`` 로 backfill. 매칭 실패 시 NULL.
- ``carrier`` VARCHAR 컬럼과 ``ix_ocean_shipments_team_carrier`` 인덱스 제거.
- 새 인덱스 ``ix_ocean_shipments_team_carrier_id`` 추가.

다운그레이드 시: carrier VARCHAR 부활 → carrier_id JOIN 해서 이름 복원 →
FK / 인덱스 / 테이블 제거 순.
"""
from __future__ import annotations

import json
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "g7h8i9j0k1l2"
down_revision: Union[str, None] = "f6g7h8i9j0k1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ---------------------------------------------------------------------------
# Seed data — (scac, name, mbl_prefixes, scraper_key, display_order, is_supported)
#
# display_order 낮을수록 피커 상단. 스크래퍼 구현 여부와 별개로 SCAC 목록은
# 풍부하게 유지 (사용자가 MBL 입력 시 선사 선택을 제한받지 않도록). scraper_key
# 가 NULL 인 선사도 등록은 가능하지만 자동 추적은 failed 처리.
# ---------------------------------------------------------------------------
SEED_CARRIERS = [
    # ── Top global alliances ───────────────────────────────────
    ("MAEU", "Maersk",                              ["MAEU", "MSK", "MRKU"], "maersk",    10,  True),
    ("MSCU", "MSC (Mediterranean Shipping Company)", ["MSCU", "MEDU"],       "msc",       20,  True),
    ("CMDU", "CMA CGM",                             ["CMDU", "CPJQ"],        None,        30,  True),
    ("COSU", "COSCO Shipping Lines",                ["COSU"],                "cosco",     40,  True),
    ("HLCU", "Hapag-Lloyd",                         ["HLCU"],                "hapag",     50,  True),
    ("ONEY", "Ocean Network Express (ONE)",         ["ONEY"],                "one",       60,  True),
    ("EGLV", "Evergreen Marine",                    ["EGLV"],                "evergreen", 70,  True),
    ("YMLU", "Yang Ming Marine Transport",          ["YMLU", "YMJA"],        "yangming",  80,  True),
    ("HMMU", "HMM (Hyundai Merchant Marine)",       ["HMMU", "HDMU"],        "hmm",       90,  True),
    ("ZIMU", "ZIM Integrated Shipping",             ["ZIMU"],                "zim",       100, True),

    # ── Major global carriers ──────────────────────────────────
    ("OOLU", "OOCL (Orient Overseas Container Line)", ["OOLU"],              None,        110, True),
    ("APLU", "American President Lines (APL)",       ["APLU"],               None,        120, True),
    ("PABV", "PIL (Pacific International Lines)",    ["PABV", "PCIU"],       "pil",       130, True),
    ("WHLC", "Wan Hai Lines",                        ["WHLC"],               "wanhai",    140, True),
    ("SUDU", "Hamburg Süd",                          ["SUDU", "HSDG"],       "maersk",    150, True),  # Maersk 계열 — 같은 스크래퍼
    ("SAFM", "Safmarine",                            ["SAFM"],               None,        160, True),
    ("SEAU", "Sealand (Maersk)",                     ["SEAU"],               None,        170, True),
    ("MCCQ", "MCC Transport",                        ["MCCQ"],               None,        180, True),
    ("MATS", "Matson",                               ["MATS"],               "matson",    190, True),

    # ── Intra-Asia & regional Asian lines ──────────────────────
    ("SMLM", "SM Line",                              ["SMLM"],               "smline",    200, True),
    ("SITC", "SITC Container Lines",                 ["SITC"],               None,        210, True),
    ("KMTU", "KMTC (Korea Marine Transport)",        ["KMTU"],               None,        220, True),
    ("HASL", "Heung-A Shipping",                     ["HASL"],               None,        230, True),
    ("SMLU", "Sinokor Merchant Marine",              ["SMLU"],               None,        240, True),
    ("TSLU", "T.S. Lines",                           ["TSLU"],               None,        250, True),
    ("IALU", "Interasia Lines",                      ["IALU"],               None,        260, True),
    ("RCLE", "RCL (Regional Container Lines)",       ["RCLE"],               None,        270, True),
    ("DJSU", "Dongjin Shipping",                     ["DJSU"],               None,        280, True),
    ("GOSU", "Goldstar Line",                        ["GOSU"],               None,        290, True),
    ("DYLT", "Dong Young Shipping",                  ["DYLT"],               None,        300, True),
    ("NAMS", "Namsung Shipping",                     ["NAMS"],               None,        310, True),
    ("PEGU", "Pegasus Shipping",                     ["PEGU"],               None,        320, True),

    # ── Pacific / Japan regional ───────────────────────────────
    ("SNKO", "Sinokor Japan",                        ["SNKO"],               None,        330, True),
    ("KLKU", "K Line (Korea)",                       ["KLKU"],               None,        340, True),
    ("SJHH", "Sea Lead",                             ["SJHH", "SEAL"],       "sealead",   350, True),
    ("SSBF", "Westwood",                             ["SSBF", "WWSU"],       "westwood",  360, True),

    # ── European / Mediterranean ───────────────────────────────
    ("ARKU", "Arkas Line",                           ["ARKU"],               None,        400, True),
    ("TRHU", "Turkon Line",                          ["TRHU"],               None,        410, True),
    ("GRIU", "Grimaldi Lines",                       ["GRIU"],               None,        420, True),

    # ── Middle East ────────────────────────────────────────────
    ("EMKU", "Emirates Shipping Line",               ["EMKU"],               None,        430, True),
    ("MILU", "Milaha",                               ["MILU"],               None,        440, True),

    # ── Americas / niche ───────────────────────────────────────
    ("CRLU", "Crowley Liner Services",               ["CRLU"],               None,        450, True),
    ("KNLU", "King Ocean Services",                  ["KNLU"],               None,        460, True),
    ("TLPU", "Tropical Shipping",                    ["TLPU"],               None,        470, True),
    ("BWLE", "BWL Logistics",                        ["BWLE"],               None,        480, True),

    # ── African / Oceania ──────────────────────────────────────
    ("NILU", "Nile Dutch",                           ["NILU"],               None,        490, True),
    ("SWWL", "Swire Shipping",                       ["SWWL"],               None,        500, True),
    ("CHNL", "China Navigation",                     ["CHNL"],               None,        510, True),
    ("SPNU", "SPIL (Samudera Shipping)",             ["SPNU"],               None,        520, True),
    ("CULU", "CULines (China United Lines)",         ["CULU"],               None,        530, True),
    ("BALU", "BAL Container Line",                   ["BALU"],               None,        540, True),
    ("ANNU", "Antong Holdings (QASC)",               ["ANNU"],               None,        550, True),
    ("IRSU", "IRISL",                                ["IRSU"],               None,        560, True),
    ("ASCU", "Asean Seas Line",                      ["ASCU"],               None,        570, True),
    ("FDCU", "FDC Container Lines",                  ["FDCU"],               None,        580, True),
    ("FESO", "FESCO",                                ["FESO"],               None,        590, True),

    # ── Legacy / merged carriers (여전히 MBL 에 등장) ─────────
    ("KKLU", "K Line (merged into ONE)",             ["KKLU"],               None,        900, False),
    ("NYKS", "NYK Line (merged into ONE)",           ["NYKS"],               None,        910, False),
    ("MOLU", "MOL (merged into ONE)",                ["MOLU"],               None,        920, False),
    ("UASC", "UASC (merged into Hapag-Lloyd)",       ["UASC"],               None,        930, False),
    ("HJMU", "Hanjin Shipping (defunct)",            ["HJMU"],               None,        940, False),
]


def upgrade() -> None:
    # ── 1) carriers 테이블 생성 ─────────────────────────────────
    op.create_table(
        "carriers",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("scac", sa.String(length=8), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("mbl_prefixes", sa.JSON(), nullable=True),
        sa.Column("scraper_key", sa.String(length=50), nullable=True),
        sa.Column("tracking_url", sa.String(length=500), nullable=True),
        sa.Column("logo_url", sa.String(length=500), nullable=True),
        sa.Column("display_order", sa.Integer(), nullable=False, server_default="1000"),
        sa.Column("is_supported", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(now())"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(now())"), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("updated_by_user_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["user.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["updated_by_user_id"], ["user.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("scac", name="uq_carriers_scac"),
    )
    op.create_index("ix_carriers_scac", "carriers", ["scac"], unique=False)
    op.create_index("ix_carriers_scraper_key", "carriers", ["scraper_key"], unique=False)
    op.create_index("ix_carriers_display_order", "carriers", ["display_order"], unique=False)

    # ── 2) Seed 초기 선사 ─────────────────────────────────────
    bind = op.get_bind()
    for scac, name, prefixes, scraper_key, display_order, is_supported in SEED_CARRIERS:
        bind.execute(
            sa.text(
                """
                INSERT INTO carriers
                  (scac, name, mbl_prefixes, scraper_key, display_order, is_supported, is_active)
                VALUES
                  (:scac, :name, :mbl_prefixes, :scraper_key, :display_order, :is_supported, 1)
                """
            ),
            {
                "scac": scac,
                "name": name,
                "mbl_prefixes": json.dumps(prefixes),
                "scraper_key": scraper_key,
                "display_order": display_order,
                "is_supported": is_supported,
            },
        )

    # ── 3) ocean_shipments.carrier_id 컬럼 추가 (nullable) ────
    op.add_column(
        "ocean_shipments",
        sa.Column("carrier_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_ocean_shipments_carrier_id",
        "ocean_shipments",
        "carriers",
        ["carrier_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_ocean_shipments_team_carrier_id",
        "ocean_shipments",
        ["team_id", "carrier_id"],
        unique=False,
    )

    # ── 4) Backfill: 기존 carrier VARCHAR → carrier_id FK ────
    # (a) 이름 정확 일치 (case-insensitive)
    bind.execute(
        sa.text(
            """
            UPDATE ocean_shipments s
            JOIN carriers c
              ON LOWER(TRIM(c.name)) = LOWER(TRIM(s.carrier))
            SET s.carrier_id = c.id
            WHERE s.carrier IS NOT NULL AND s.carrier_id IS NULL
            """
        )
    )
    # (b) SCAC 일치 (carrier 문자열이 SCAC 그 자체로 들어간 경우)
    bind.execute(
        sa.text(
            """
            UPDATE ocean_shipments s
            JOIN carriers c ON c.scac = UPPER(TRIM(s.carrier))
            SET s.carrier_id = c.id
            WHERE s.carrier IS NOT NULL AND s.carrier_id IS NULL
            """
        )
    )
    # (c) MBL prefix 기반 추정 — 이름/SCAC 둘 다 실패한 레거시 row 만. 가장 긴
    # 매칭 prefix 가 우선이도록 SCAC 길이 내림차순으로 순회.
    bind.execute(
        sa.text(
            """
            UPDATE ocean_shipments s
            JOIN carriers c
              ON UPPER(TRIM(s.mbl)) LIKE CONCAT(c.scac, '%')
            SET s.carrier_id = c.id
            WHERE s.carrier_id IS NULL
            """
        )
    )

    # ── 5) 기존 carrier 컬럼 + 인덱스 제거 ─────────────────────
    op.drop_index("ix_ocean_shipments_team_carrier", table_name="ocean_shipments")
    op.drop_column("ocean_shipments", "carrier")


def downgrade() -> None:
    # ── 1) carrier VARCHAR 복구 + backfill from carrier_id ───
    op.add_column(
        "ocean_shipments",
        sa.Column("carrier", sa.String(length=100), nullable=True),
    )
    op.create_index(
        "ix_ocean_shipments_team_carrier",
        "ocean_shipments",
        ["team_id", "carrier"],
        unique=False,
    )
    bind = op.get_bind()
    bind.execute(
        sa.text(
            """
            UPDATE ocean_shipments s
            JOIN carriers c ON c.id = s.carrier_id
            SET s.carrier = c.name
            WHERE s.carrier_id IS NOT NULL
            """
        )
    )

    # ── 2) carrier_id FK / 컬럼 / 인덱스 제거 ─────────────────
    op.drop_index("ix_ocean_shipments_team_carrier_id", table_name="ocean_shipments")
    op.drop_constraint(
        "fk_ocean_shipments_carrier_id",
        "ocean_shipments",
        type_="foreignkey",
    )
    op.drop_column("ocean_shipments", "carrier_id")

    # ── 3) carriers 테이블 제거 ─────────────────────────────
    op.drop_index("ix_carriers_display_order", table_name="carriers")
    op.drop_index("ix_carriers_scraper_key", table_name="carriers")
    op.drop_index("ix_carriers_scac", table_name="carriers")
    op.drop_table("carriers")
