"""Terminal Repository."""
from __future__ import annotations

from app.core.repository import BaseRepository
from app.domains.terminals.models import Terminal


class TerminalRepository(BaseRepository[Terminal]):
    model = Terminal
