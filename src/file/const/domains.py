from __future__ import annotations
from enum import StrEnum

class FileDomain(StrEnum):
    USER = "user"
    TEAM = "team"
    # Add your domain-specific file domains here
    # PRODUCT = "product"
    # PARTNER = "partner"

    @classmethod
    def values(cls) -> list[str]:
        return [v.value for v in cls]
