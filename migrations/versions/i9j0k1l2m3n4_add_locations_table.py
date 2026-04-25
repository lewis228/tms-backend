"""locations 마스터 테이블 + UN/LOCODE seed + shipment/container/event FK 전환

Revision ID: i9j0k1l2m3n4
Revises: h8i9j0k1l2m3
Create Date: 2026-04-21 15:00:00.000000

변경 요지:
- ``locations`` / ``location_aliases`` 전역 테이블 생성 (UN/LOCODE 기반)
- UN/LOCODE 공식 CSV 에서 ~116K row seed
- 기존 varchar 컬럼 제거 + nullable FK 로 교체:
  * ocean_shipments.pol / pod           → pol_location_id / pod_location_id
  * ocean_containers.terminal           → terminal_location_id
  * ocean_container_events.location     → location_id
- 기존 row 의 varchar 값은 이 마이그레이션에서 **버린다** (scrape_logs.result_json
  이 원본 보존 중이고, 다음 스크래핑 사이클이 FK 를 채움).
"""
from __future__ import annotations

import csv
import os
import re
from typing import Iterator, List, Sequence, Tuple, Union

from alembic import op
import sqlalchemy as sa


revision: str = "i9j0k1l2m3n4"
down_revision: Union[str, None] = "h8i9j0k1l2m3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ---------------------------------------------------------------------------
# UN/LOCODE CSV → (unlocode, name, country_code, subdivision, kind, lat, lng,
# iata) 변환 헬퍼.
# ---------------------------------------------------------------------------

# CSV 가 같이 커밋되는 위치. 이 파일(migrations/versions/...py)에서 상대 경로.
CSV_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "src", "common", "location", "data", "un_locode.csv",
)

# Function 컬럼 position → kind 매핑 (position 0 부터).
# "1" = Port (seaport). "2" = Rail terminal. "3" = Road terminal.
# "4" = Airport. "5" = Postal exchange. "6" = Inland clearance depot.
# "7" = Fixed transport functions (e.g. oil platform). "8" = Inland water port.
# "B" (9번째 자리 뒤) = Border crossing.
FUNCTION_POSITION_TO_KIND = {
    0: "seaport",
    1: "rail_terminal",
    2: "road_terminal",
    3: "airport",
    4: "postal",
    5: "inland",          # ICD
    6: "cargo_terminal",  # Fixed transport (pipelines / specialty)
    7: "inland",          # Inland water
}

# "4230N 00131E" → (42.5, 1.5166...)
COORD_RE = re.compile(r"^\s*(\d{2})(\d{2})([NS])\s+(\d{3})(\d{2})([EW])\s*$")


def _parse_coordinates(raw: str) -> Tuple[Union[float, None], Union[float, None]]:
    if not raw:
        return None, None
    m = COORD_RE.match(raw)
    if not m:
        return None, None
    lat_deg = int(m.group(1))
    lat_min = int(m.group(2))
    lat_hem = m.group(3)
    lng_deg = int(m.group(4))
    lng_min = int(m.group(5))
    lng_hem = m.group(6)
    lat = lat_deg + lat_min / 60.0
    lng = lng_deg + lng_min / 60.0
    if lat_hem == "S":
        lat = -lat
    if lng_hem == "W":
        lng = -lng
    return lat, lng


def _classify_kind(function: str) -> str:
    """UN/LOCODE Function 문자열에서 대표 kind 를 뽑는다. 여러 position 이 세팅된
    경우 우선순위: seaport > airport > rail_terminal > road_terminal > 나머지.
    """
    if not function:
        return "unknown"
    priority = ["seaport", "airport", "rail_terminal", "road_terminal", "cargo_terminal", "inland", "postal"]
    matched = set()
    for pos, kind in FUNCTION_POSITION_TO_KIND.items():
        if pos < len(function) and function[pos] not in ("-", "0", ""):
            matched.add(kind)
    # Border crossing — 9번째 자리(마지막) 가 'B'.
    if function.endswith("B"):
        matched.add("border")
    for p in priority:
        if p in matched:
            return p
    return "unknown"


def _iter_rows(batch_size: int = 5000) -> Iterator[List[dict]]:
    """CSV 를 batch 로 순회.

    - unlocode 없는 entry (Location 열 비어 있음) skip
    - Change == "X" (UNECE removal marker) skip
    - **unlocode 중복 시 마지막 승리** — 동일 LOCODE 가 여러 entry 로 중복
      표기되는 경우가 있어 (subdivision 병합 이력 등) 단일 행만 인덱싱해
      UniqueConstraint 위반을 방지.
    """
    seen: dict[str, dict] = {}
    with open(CSV_PATH, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for r in reader:
            change = (r.get("Change") or "").strip()
            if change == "X":
                continue
            country = (r.get("Country") or "").strip().upper()
            location_code = (r.get("Location") or "").strip().upper()
            name = (r.get("Name") or "").strip()
            if not country or not location_code or not name:
                continue
            unlocode = f"{country}{location_code}"
            function = (r.get("Function") or "").strip()
            lat, lng = _parse_coordinates(r.get("Coordinates") or "")
            iata = (r.get("IATA") or "").strip() or None
            subdivision = (r.get("Subdivision") or "").strip() or None
            seen[unlocode] = {
                "unlocode": unlocode,
                "name": name,
                "country_code": country,
                "subdivision": subdivision,
                "kind": _classify_kind(function),
                "latitude": lat,
                "longitude": lng,
                "iata": iata,
            }

    batch: List[dict] = []
    for row in seen.values():
        batch.append(row)
        if len(batch) >= batch_size:
            yield batch
            batch = []
    if batch:
        yield batch


def upgrade() -> None:
    # ── 1) locations 테이블 생성 ─────────────────────────────
    op.create_table(
        "locations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("unlocode", sa.String(length=5), nullable=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("name_i18n", sa.JSON(), nullable=True),
        sa.Column("country_code", sa.String(length=2), nullable=False),
        sa.Column("subdivision", sa.String(length=10), nullable=True),
        sa.Column("kind", sa.String(length=20), nullable=False, server_default="unknown"),
        sa.Column("parent_location_id", sa.Integer(), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("iata", sa.String(length=3), nullable=True),
        sa.Column("external_ref", sa.String(length=100), nullable=True),
        sa.Column("is_supported", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(now())"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(now())"), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("updated_by_user_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["user.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["updated_by_user_id"], ["user.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["parent_location_id"], ["locations.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("unlocode", name="uq_locations_unlocode"),
    )
    op.create_index("ix_locations_country", "locations", ["country_code"])
    op.create_index("ix_locations_kind", "locations", ["kind"])
    op.create_index("ix_locations_name", "locations", ["name"])
    op.create_index("ix_locations_parent", "locations", ["parent_location_id"])
    op.create_index("ix_locations_iata", "locations", ["iata"])

    # ── 2) location_aliases 테이블 생성 ─────────────────────
    op.create_table(
        "location_aliases",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("location_id", sa.Integer(), nullable=False),
        sa.Column("raw_text", sa.String(length=300), nullable=False),
        sa.Column("carrier_id", sa.Integer(), nullable=True),
        sa.Column("confidence", sa.String(length=20), nullable=False, server_default="exact"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(now())"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(now())"), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("updated_by_user_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["location_id"], ["locations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["carrier_id"], ["carriers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["user.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["updated_by_user_id"], ["user.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("raw_text", "carrier_id", name="uq_location_aliases_raw_carrier"),
    )
    op.create_index("ix_location_aliases_location", "location_aliases", ["location_id"])
    op.create_index("ix_location_aliases_raw", "location_aliases", ["raw_text"])

    # ── 3) UN/LOCODE seed ───────────────────────────────────
    bind = op.get_bind()
    insert_sql = sa.text(
        """
        INSERT INTO locations
          (unlocode, name, country_code, subdivision, kind, latitude, longitude, iata,
           is_supported, is_active)
        VALUES
          (:unlocode, :name, :country_code, :subdivision, :kind, :latitude, :longitude, :iata, 1, 1)
        """
    )
    total = 0
    for batch in _iter_rows(batch_size=5000):
        bind.execute(insert_sql, batch)
        total += len(batch)
    print(f"[migration] seeded {total} locations from UN/LOCODE")

    # ── 4) ocean_shipments: pol/pod varchar → FK ────────────
    op.add_column(
        "ocean_shipments",
        sa.Column("pol_location_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "ocean_shipments",
        sa.Column("pod_location_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_ocean_shipments_pol_location_id",
        "ocean_shipments", "locations",
        ["pol_location_id"], ["id"], ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_ocean_shipments_pod_location_id",
        "ocean_shipments", "locations",
        ["pod_location_id"], ["id"], ondelete="RESTRICT",
    )
    op.create_index(
        "ix_ocean_shipments_team_pol_location_id", "ocean_shipments",
        ["team_id", "pol_location_id"],
    )
    op.create_index(
        "ix_ocean_shipments_team_pod_location_id", "ocean_shipments",
        ["team_id", "pod_location_id"],
    )
    op.drop_column("ocean_shipments", "pol")
    op.drop_column("ocean_shipments", "pod")

    # ── 5) ocean_containers: terminal varchar → FK ─────────
    op.add_column(
        "ocean_containers",
        sa.Column("terminal_location_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_ocean_containers_terminal_location_id",
        "ocean_containers", "locations",
        ["terminal_location_id"], ["id"], ondelete="RESTRICT",
    )
    op.create_index(
        "ix_ocean_containers_team_terminal_location_id", "ocean_containers",
        ["team_id", "terminal_location_id"],
    )
    op.drop_column("ocean_containers", "terminal")

    # ── 6) ocean_container_events: location varchar → FK ───
    op.add_column(
        "ocean_container_events",
        sa.Column("location_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_ocean_container_events_location_id",
        "ocean_container_events", "locations",
        ["location_id"], ["id"], ondelete="RESTRICT",
    )
    op.create_index(
        "ix_ocean_container_events_team_location_id", "ocean_container_events",
        ["team_id", "location_id"],
    )
    op.drop_column("ocean_container_events", "location")


def downgrade() -> None:
    # ── ocean_container_events ─────────────────────────────
    op.add_column(
        "ocean_container_events",
        sa.Column("location", sa.String(length=255), nullable=True),
    )
    op.drop_index("ix_ocean_container_events_team_location_id", table_name="ocean_container_events")
    op.drop_constraint("fk_ocean_container_events_location_id", "ocean_container_events", type_="foreignkey")
    op.drop_column("ocean_container_events", "location_id")

    # ── ocean_containers ───────────────────────────────────
    op.add_column(
        "ocean_containers",
        sa.Column("terminal", sa.String(length=255), nullable=True),
    )
    op.drop_index("ix_ocean_containers_team_terminal_location_id", table_name="ocean_containers")
    op.drop_constraint("fk_ocean_containers_terminal_location_id", "ocean_containers", type_="foreignkey")
    op.drop_column("ocean_containers", "terminal_location_id")

    # ── ocean_shipments ────────────────────────────────────
    op.add_column("ocean_shipments", sa.Column("pol", sa.String(length=100), nullable=True))
    op.add_column("ocean_shipments", sa.Column("pod", sa.String(length=100), nullable=True))
    op.drop_index("ix_ocean_shipments_team_pol_location_id", table_name="ocean_shipments")
    op.drop_index("ix_ocean_shipments_team_pod_location_id", table_name="ocean_shipments")
    op.drop_constraint("fk_ocean_shipments_pol_location_id", "ocean_shipments", type_="foreignkey")
    op.drop_constraint("fk_ocean_shipments_pod_location_id", "ocean_shipments", type_="foreignkey")
    op.drop_column("ocean_shipments", "pol_location_id")
    op.drop_column("ocean_shipments", "pod_location_id")

    # ── location_aliases ───────────────────────────────────
    op.drop_index("ix_location_aliases_raw", table_name="location_aliases")
    op.drop_index("ix_location_aliases_location", table_name="location_aliases")
    op.drop_table("location_aliases")

    # ── locations ──────────────────────────────────────────
    op.drop_index("ix_locations_iata", table_name="locations")
    op.drop_index("ix_locations_parent", table_name="locations")
    op.drop_index("ix_locations_name", table_name="locations")
    op.drop_index("ix_locations_kind", table_name="locations")
    op.drop_index("ix_locations_country", table_name="locations")
    op.drop_table("locations")
