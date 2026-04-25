"""Page-based 페이징."""
from __future__ import annotations

from math import ceil
from typing import Generic, Sequence, TypeVar

from fastapi import Query
from pydantic import Field

from app.core.schema import BaseSchema

T = TypeVar("T")


class PageParams(BaseSchema):
    page: int = Field(default=1, ge=1)
    size: int = Field(default=20, ge=1, le=100)

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.size

    @property
    def limit(self) -> int:
        return self.size


def page_params(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
) -> PageParams:
    return PageParams(page=page, size=size)


class PagedResponse(BaseSchema, Generic[T]):
    items: Sequence[T]
    total: int
    page: int
    size: int
    pages: int

    @classmethod
    def of(cls, items: Sequence[T], total: int, params: PageParams) -> "PagedResponse[T]":
        pages = max(1, ceil(total / params.size)) if total else 0
        return cls(items=items, total=total, page=params.page, size=params.size, pages=pages)
