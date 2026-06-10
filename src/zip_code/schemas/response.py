# src/zip_code/schemas/response.py
from __future__ import annotations
from common.schemas.base import ResponseSchema


class ZipCodeResponseSchema(ResponseSchema):
    id: int
    zip: str
    city: str
    state: str
    county: str | None = None
    latitude: float | None = None
    longitude: float | None = None


class CitySuggestionSchema(ResponseSchema):
    city: str
    state: str
