"""Vessel Repository."""
from __future__ import annotations

from app.core.repository import BaseRepository
from app.domains.vessels.models import Vessel


class VesselRepository(BaseRepository[Vessel]):
    model = Vessel
