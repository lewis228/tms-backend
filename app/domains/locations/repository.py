"""Location Repository."""
from __future__ import annotations

from app.core.repository import BaseRepository
from app.domains.locations.models import Location


class LocationRepository(BaseRepository[Location]):
    model = Location
