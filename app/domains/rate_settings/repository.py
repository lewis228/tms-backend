"""RateSetting Repository."""
from __future__ import annotations

from app.core.repository import BaseRepository
from app.domains.rate_settings.models import RateSetting


class RateSettingRepository(BaseRepository[RateSetting]):
    model = RateSetting
