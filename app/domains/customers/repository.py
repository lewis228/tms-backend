"""Customer Repository."""
from __future__ import annotations

from app.core.repository import BaseRepository
from app.domains.customers.models import Customer


class CustomerRepository(BaseRepository[Customer]):
    model = Customer
