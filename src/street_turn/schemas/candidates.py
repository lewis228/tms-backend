# src/street_turn/schemas/candidates.py
"""H-11 Street Turn 추천 후보 응답 스키마."""
from __future__ import annotations
from decimal import Decimal
from typing import List

from common.schemas.base import ResponseSchema


class StreetTurnCandidate(ResponseSchema):
    import_order_id: int
    export_order_id: int
    container_id: int | None
    container_number: str | None
    customer_id: int
    container_size: str | None
    score: int
    estimated_saving: Decimal


class StreetTurnCandidatesResponse(ResponseSchema):
    candidates: List[StreetTurnCandidate]
    total: int
    saving_per_turn: Decimal
